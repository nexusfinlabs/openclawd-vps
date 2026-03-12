#!/usr/bin/env python3
"""
ops/linkedin_search.py
======================
Standalone LinkedIn profile finder using SerpAPI.
Reads companies from Google Sheets (payments tab), finds decision-maker
LinkedIn profiles for each firm, writes results back to the sheet.

Usage:
    python3 ops/linkedin_search.py --tab payments --top-rows 5
    python3 ops/linkedin_search.py --tab payments --start-row 2 --end-row 10
    python3 ops/linkedin_search.py --tab payments --dry-run

Env vars (from ~/openclawd_stack/.env):
    GOOGLE_APPLICATION_CREDENTIALS
    SHEETS_SPREADSHEET_ID
    SERPAPI_KEY
"""
import os, sys, time, re, argparse, requests
from pathlib import Path

# Load .env
def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_env()

import gspread
from google.oauth2.service_account import Credentials

# ── Config ──────────────────────────────────────────────────────────────────
CREDS_PATH  = os.getenv("GOOGLE_APPLICATION_CREDENTIALS",
                         "/home/albi_agent/.secrets/google/credentials.json")
SHEET_ID    = os.getenv("SHEETS_SPREADSHEET_ID",
                         "1_GwMkz8niCS8Uz_yh8fTU9AFVOGfzDFkd4L8glzfrUM")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SERPAPI_URL = "https://serpapi.com/search"

# Sheet column indices (1-based)
COL_ENTITY  = 2   # B — Entidad (HQ)
COL_TIPO    = 3   # C — Tipo
COL_LI_1    = 9   # I — Linkedin-1   (through O = Linkedin-7)
NUM_LI_COLS = 7

# Roles by company type — who signs the cheque
ROLES_CORPORATE = [
    "Head of M&A",
    "VP Corporate Development",
    "VP Strategy",
    "M&A Director",
    "Head of Payments Strategy",
    "Head of LatAm",
    "Business Development Director LatAm",
]
ROLES_VC_PE = [
    "Partner",
    "General Partner",
    "Managing Director",
    "Principal",
    "Investment Director",
    "Investment Partner",
    "Portfolio Manager",
]
ROLES_BANCA = [
    "Head of LatAm Coverage",
    "M&A Director",
    "Managing Director",
    "Head of Corporate Finance",
    "VP Investment Banking",
]

def _get_roles(tipo: str) -> list[str]:
    t = tipo.lower()
    if any(x in t for x in ["vc", "growth", "pe", "private equity"]):
        return ROLES_VC_PE
    if any(x in t for x in ["banca", "bank"]):
        return ROLES_BANCA
    return ROLES_CORPORATE


# ── SerpAPI ─────────────────────────────────────────────────────────────────
def serp_search(query: str, num: int = 5) -> list[dict]:
    params = {"q": query, "api_key": SERPAPI_KEY, "num": num, "hl": "en", "gl": "us"}
    try:
        r = requests.get(SERPAPI_URL, params=params, timeout=20)
        r.raise_for_status()
        return r.json().get("organic_results", [])
    except Exception as e:
        print(f"  [serp] ERROR: {e}")
        return []


def extract_li_url(result: dict) -> str | None:
    link = result.get("link", "")
    if "linkedin.com/in/" in link:
        m = re.match(r"(https?://[a-z\w.]*linkedin\.com/in/[^/?#]+)", link)
        return m.group(1) if m else link
    return None


def find_profiles(company: str, tipo: str, max_profiles: int = 7) -> list[str]:
    """Returns up to max_profiles LinkedIn URLs for the given company."""
    roles = _get_roles(tipo)[:max_profiles]
    seen: set[str] = set()
    urls: list[str] = []

    for role in roles:
        if len(urls) >= max_profiles:
            break
        query = f'site:linkedin.com/in "{company}" "{role}"'
        results = serp_search(query, num=3)
        time.sleep(0.8)
        for r in results:
            url = extract_li_url(r)
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
                name = re.sub(r"[\-|]?\s*LinkedIn.*$", "", r.get("title", "")).strip()
                print(f"  [OK] {name[:35]:35s} | {url[:55]}")
                break  # 1 profile per role keeps variety

    return urls


# ── Sheets ───────────────────────────────────────────────────────────────────
def init_sheets(tab: str):
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ])
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID).worksheet(tab)


def run(tab: str, top_rows: int | None, start_row: int, end_row: int | None,
        dry_run: bool):
    if not SERPAPI_KEY:
        print("[ERROR] SERPAPI_KEY not set")
        sys.exit(1)

    print(f"[linkedin_search] Connecting to Sheets: {SHEET_ID} / {tab}")
    ws = init_sheets(tab)
    all_rows = ws.get_all_values()
    total = len(all_rows)

    rows_to_process = all_rows[1:]   # skip header
    if top_rows:
        rows_to_process = rows_to_process[:top_rows]
    elif end_row:
        rows_to_process = rows_to_process[start_row-2 : end_row-1]
    else:
        rows_to_process = rows_to_process[start_row-2:]

    stats = {"processed": 0, "found": 0, "skipped": 0}
    pending = []

    for sheet_row_idx, row in enumerate(rows_to_process, start=start_row if not top_rows else 2):
        entity = row[COL_ENTITY - 1] if len(row) >= COL_ENTITY else ""
        tipo   = row[COL_TIPO - 1]   if len(row) >= COL_TIPO   else ""
        if not entity:
            continue

        # Skip if all 7 linkedin cols already filled
        existing_li = [row[COL_LI_1 - 1 + i] if len(row) >= COL_LI_1 + i else ""
                        for i in range(NUM_LI_COLS)]
        if all(v.strip() for v in existing_li):
            print(f"  [SKIP] Row {sheet_row_idx}: {entity} (already has LinkedIn)")
            stats["skipped"] += 1
            continue

        print(f"\n[Row {sheet_row_idx}] {entity} ({tipo})")
        urls = find_profiles(entity, tipo, max_profiles=NUM_LI_COLS)
        stats["processed"] += 1
        stats["found"] += len(urls)

        if not dry_run and urls:
            for i, url in enumerate(urls):
                col_letter = chr(ord("I") + i)   # I, J, K, L, M, N, O
                cell = f"{col_letter}{sheet_row_idx}"
                pending.append({"range": cell, "values": [[url]]})

            # Flush every 5 companies to avoid rate limits
            if len(pending) >= 35:
                ws.batch_update(pending)
                pending.clear()
                time.sleep(3)

    # Final flush
    if not dry_run and pending:
        ws.batch_update(pending)

    print(f"\n[linkedin_search] Done — {stats}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="LinkedIn profile finder via SerpAPI")
    parser.add_argument("--tab",        default="payments", help="Sheet tab name")
    parser.add_argument("--top-rows",   type=int, default=None, help="Process first N rows")
    parser.add_argument("--start-row",  type=int, default=2,    help="Start row (1-indexed)")
    parser.add_argument("--end-row",    type=int, default=None, help="End row (1-indexed)")
    parser.add_argument("--dry-run",    action="store_true",    help="Don't write to Sheets")
    args = parser.parse_args()
    run(args.tab, args.top_rows, args.start_row, args.end_row, args.dry_run)


if __name__ == "__main__":
    main()
