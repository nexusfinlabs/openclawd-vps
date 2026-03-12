"""Google Sheets writer using gspread + service account."""

import os
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client: gspread.Client | None = None


def get_client() -> gspread.Client:
    """Return a cached gspread client (created on first call)."""
    global _client
    if _client is None:
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def get_spreadsheet() -> gspread.Spreadsheet:
    """Open the configured spreadsheet."""
    sid = os.getenv("SHEETS_SPREADSHEET_ID")
    return get_client().open_by_key(sid)


def append_rows(tab_name: str, rows: list[list[str]]) -> int:
    """Append rows to the given tab. Returns number of rows appended."""
    if not rows:
        return 0
    sheet = get_spreadsheet()
    ws = sheet.worksheet(tab_name)
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)


def sheet_health_check() -> bool:
    """Quick check: can we open the spreadsheet?"""
    try:
        get_spreadsheet()
        return True
    except Exception:
        return False
