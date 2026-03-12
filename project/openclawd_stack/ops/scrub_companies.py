#!/usr/bin/env python3
"""
ops/scrub_companies.py -- Company List Quality Scrubber
=======================================================
Reads the 'companies' tab in Google Sheets, validates each URL,
and writes a STATUS column back. NON-DESTRUCTIVE: never deletes rows.

Columns expected (1-indexed):
  B (2) = URL
  C (3) = Title (already scraped, used as a hint)

Columns written:
  D (4) = STATUS
  E (5) = STATUS_REASON

STATUS values:
  KEEP              -- functional site, M&A/PE/finance relevant
  DISCARD_FORSALE   -- domain for sale
  DISCARD_PERSONAL  -- personal page / blog
  DISCARD_BIG_CORP  -- large firm outside scope
  DISCARD_IRRELEVANT-- site up but not M&A/finance/investment
  ERROR             -- HTTP error, unreachable, timeout

Usage (on VPS):
  cd ~/openclawd_stack
  set -a && source .env && set +a
  export GOOGLE_APPLICATION_CREDENTIALS=/home/albi_agent/.secrets/google/credentials.json

  # Dry-run (no Sheets write):
  python3 ops/scrub_companies.py --dry-run

  # Resume from row 169:
  python3 ops/scrub_companies.py --start 169

  # Range:
  python3 ops/scrub_companies.py --start 2 --end 50
"""

import os
import sys
import time
import argparse
import requests
from bs4 import BeautifulSoup
import gspread
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials

# -- Config ------------------------------------------------------------------
CREDS_PATH     = os.getenv("GOOGLE_APPLICATION_CREDENTIALS",
                            "/home/albi_agent/.secrets/google/credentials.json")
SPREADSHEET_ID = os.getenv("SHEETS_SPREADSHEET_ID",
                            "1_GwMkz8niCS8Uz_yh8fTU9AFVOGfzDFkd4L8glzfrUM")
COMPANIES_TAB  = os.getenv("SHEETS_TAB_COMPANIES", "companies")

COL_URL    = 2   # B
COL_TITLE  = 3   # C
COL_STATUS = 4   # D
COL_REASON = 5   # E

REQUEST_TIMEOUT = 15    # seconds per URL
SLEEP_BETWEEN   = 0.4   # polite delay between requests
BATCH_SIZE      = 10    # flush to Sheets every N rows
BATCH_SLEEP     = 3.0   # seconds to wait after each Sheets batch write

# -- Big Corp Blacklist -------------------------------------------------------
BIG_CORPS = {
    "blackstone", "bain capital", "bainandcompany",
    "wellsfargo", "wells fargo", "jpmorgan", "jp morgan", "chase",
    "goldman sachs", "goldmansachs", "morgan stanley", "morganstanley",
    "kkr", "carlyle", "apollo global", "warburg pincus",
    "tpg capital", "advent international",
    "bank of america", "bofa", "citibank", "citi.com", "citigroup",
    "berkshire hathaway", "blackrock.com", "vanguard.com", "fidelity.com",
    "mckinsey", "boston consulting group",
    "sequoia capital", "andreessen horowitz",
    "softbank", "temasek",
}

# -- For-Sale Signals --------------------------------------------------------
FOR_SALE_SIGNALS = [
    "domain is for sale", "this domain may be for sale",
    "domain for sale", "buy this domain", "purchase this domain",
    "hugedomains.com", "sedo.com", "godaddy.com/domainsearch",
    "afternic.com", "flippa.com", "dan.com",
    "make an offer", "inquire about this domain",
    "this domain is parked", "domain parking", "parked by",
    "domain available", "register this domain",
]

# -- Personal Page Signals ---------------------------------------------------
PERSONAL_SIGNALS = [
    "my blog", "personal blog", "personal website", "personal portfolio",
    "this is my site", "welcome to my", "hello, i'm", "hi, i'm",
    "blogspot.com", "wordpress.com/blog", "wix.com/site",
    "squarespace.com", "weebly.com", "angelfire.com",
]

# -- M&A / Finance Relevance Keywords ----------------------------------------
RELEVANT_KEYWORDS = [
    "mergers and acquisitions", "m&a", "private equity", "investment bank",
    "investment banking", "capital markets", "asset management",
    "fund management", "portfolio company", "deal advisory",
    "corporate finance", "leveraged buyout", "lbo", "buyout",
    "growth equity", "venture capital", "vc fund",
    "financial advisory", "financial services",
    "acquisitions", "divestitures", "restructuring",
    "middle market", "lower middle market",
    "buy-side", "sell-side",
    "family office", "single family office", "multi-family office",
    "wealth management", "holding company", "investment firm",
    "investment group", "deal flow", "transaction advisory", "due diligence",
]

# -- Helpers -----------------------------------------------------------------

def init_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    return sh.worksheet(COMPANIES_TAB)


def is_big_corp(url, title):
    text = (url + " " + title).lower()
    for corp in BIG_CORPS:
        if corp in text:
            return True, "big corp: " + corp
    return False, ""


def fetch_url(url):
    """Returns (status_code, title, body_text). status_code=0 on error."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; OpenClawd-Scrubber/1.0)"}
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers,
                         allow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        meta = soup.find("meta", attrs={"name": "description"})
        meta_desc = meta.get("content", "") if meta else ""
        h1 = soup.find("h1")
        h1_text = h1.get_text(strip=True) if h1 else ""
        body = (title + " " + meta_desc + " " + h1_text + " " + r.text[:2000]).lower()
        return r.status_code, title, body
    except requests.exceptions.Timeout:
        return 0, "", "timeout"
    except requests.exceptions.SSLError:
        return 0, "", "ssl_error"
    except requests.exceptions.ConnectionError:
        return 0, "", "connection_error"
    except Exception as e:
        return 0, "", str(e)[:100]


def classify(url, existing_title):
    """Returns (STATUS, REASON)."""
    url = url.strip()
    if not url or not url.startswith("http"):
        return "ERROR", "invalid url"

    big, reason = is_big_corp(url, existing_title)
    if big:
        return "DISCARD_BIG_CORP", reason

    existing_lower = existing_title.lower()
    for signal in FOR_SALE_SIGNALS:
        if signal in existing_lower:
            return "DISCARD_FORSALE", "title: " + signal

    status_code, fetched_title, body = fetch_url(url)

    if status_code == 0:
        return "ERROR", body or "unreachable"
    if status_code >= 400:
        return "ERROR", "http " + str(status_code)

    for signal in FOR_SALE_SIGNALS:
        if signal in body:
            return "DISCARD_FORSALE", "content: " + signal

    for signal in PERSONAL_SIGNALS:
        if signal in body:
            return "DISCARD_PERSONAL", "personal: " + signal

    matches = [kw for kw in RELEVANT_KEYWORDS if kw in body]
    if matches:
        return "KEEP", "keywords: " + ", ".join(matches[:3])

    title_display = (fetched_title or existing_title)[:60]
    return "DISCARD_IRRELEVANT", "no M&A keywords | title: " + title_display


# -- Main --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Company URL scrubber")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't write to Sheets")
    parser.add_argument("--start", type=int, default=2,
                        help="Start row 1-indexed (default=2 to skip header)")
    parser.add_argument("--end", type=int, default=None,
                        help="End row inclusive (default=all rows)")
    args = parser.parse_args()

    print("[scrub] Connecting to Sheets: " + SPREADSHEET_ID + " / " + COMPANIES_TAB)
    ws = init_sheets()

    all_values = ws.get_all_values()
    total_rows = len(all_values)
    start_idx  = args.start - 1
    end_idx    = args.end or total_rows

    print("[scrub] Sheet has " + str(total_rows) + " rows. Processing " +
          str(args.start) + " to " + str(end_idx) + ".")

    stats = {
        "KEEP": 0, "DISCARD_FORSALE": 0, "DISCARD_PERSONAL": 0,
        "DISCARD_BIG_CORP": 0, "DISCARD_IRRELEVANT": 0, "ERROR": 0,
    }

    pending = []  # list of {"range": "D5", "values": [["STATUS"]]}

    def flush():
        if not args.dry_run and pending:
            ws.batch_update(pending)
            time.sleep(BATCH_SLEEP)
            pending.clear()

    for i, row in enumerate(all_values[start_idx:end_idx], start=args.start):
        url = row[COL_URL - 1] if len(row) >= COL_URL else ""
        existing_title = row[COL_TITLE - 1] if len(row) >= COL_TITLE else ""

        if not url:
            continue

        status, reason = classify(url, existing_title)
        stats[status] = stats.get(status, 0) + 1

        icons = {
            "KEEP": "OK  ", "DISCARD_FORSALE": "SALE", "DISCARD_PERSONAL": "PRIV",
            "DISCARD_BIG_CORP": "CORP", "DISCARD_IRRELEVANT": "IRRL", "ERROR": "ERR ",
        }
        icon = icons.get(status, "?   ")
        print("  [" + icon + "] Row " + str(i).rjust(3) + " | " +
              status.ljust(22) + " | " + url[:50].ljust(50) + " | " + reason[:60])

        if not args.dry_run:
            pending.append({"range": rowcol_to_a1(i, COL_STATUS), "values": [[status]]})
            pending.append({"range": rowcol_to_a1(i, COL_REASON), "values": [[reason[:200]]]})
            if len(pending) >= BATCH_SIZE * 2:
                flush()

        time.sleep(SLEEP_BETWEEN)

    flush()
    print("\n[scrub] Done. Summary: " + str(stats))


if __name__ == "__main__":
    main()
