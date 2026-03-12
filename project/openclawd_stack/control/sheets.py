"""
Minimal Google Sheets logger for oc_control.
Appends one row to the 'events' tab per interaction.
"""

import os
import logging

log = logging.getLogger("oc_control.sheets")

# Lazy-init: only connect when first called
_sheet = None
_init_done = False


def _get_sheet():
    """Lazy-init gspread client and return the events worksheet."""
    global _sheet, _init_done
    if _init_done:
        return _sheet

    _init_done = True
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID")
        tab_name = os.getenv("SHEETS_TAB_EVENTS", "events")

        if not creds_path or not spreadsheet_id:
            log.warning("Sheets not configured — GOOGLE_APPLICATION_CREDENTIALS or SHEETS_SPREADSHEET_ID missing")
            return None

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(spreadsheet_id)
        _sheet = sh.worksheet(tab_name)
        log.info("Sheets connected: %s / %s", spreadsheet_id[:12], tab_name)
    except Exception as e:
        log.error("Sheets init failed (non-fatal): %s", e)
        _sheet = None

    return _sheet


def log_event_to_sheets(row: list):
    """Append a single row to the events tab. Non-blocking, non-fatal."""
    ws = _get_sheet()
    if ws is None:
        return
    try:
        ws.append_row(row, value_input_option="RAW")
    except Exception as e:
        log.error("Sheets append failed: %s", e)
