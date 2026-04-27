"""sheets_integration.py — GEO scanner Google Sheets tracker connector."""

import json
import os
from pathlib import Path
from datetime import date
from typing import Optional

import gspread
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

TOKEN_PATH = Path.home() / ".hermes" / "google_sheets_token.json"
TRACKER_ID_PATH = Path.home() / ".hermes" / "geo_sheets_tracker_id.txt"
CLIENT_SECRET_PATHS = [
    Path.home() / "Desktop" / "client_secret_347962967117-mmaob4or2vbh0k3fli2t6te25oke87fp.apps.googleusercontent.com.json",
    Path.home() / "Downloads" / "client_secret_347962967117-mmaob4or2vbh0k3fli2t6te25oke87fp.apps.googleusercontent.com.json",
]


def _get_credentials():
    if TOKEN_PATH.exists():
        info = json.loads(TOKEN_PATH.read_text())
        return Credentials.from_authorized_user_info(info, SCOPES)
    # No token — try client secret flow
    for p in CLIENT_SECRET_PATHS:
        if p.exists():
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(str(p), SCOPES)
            creds = flow.run_local_server(port=0)
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_PATH.write_text(json.dumps({
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes,
                'universe_domain': creds.universe_domain,
                'account': '',
                'expiry': creds.expiry.isoformat() if creds.expiry else '',
            }))
            return creds
    raise FileNotFoundError("No Google auth token or client_secret found.")


def _get_tracker_id(tracker_id: Optional[str] = None) -> str:
    if tracker_id:
        return tracker_id
    if TRACKER_ID_PATH.exists():
        return TRACKER_ID_PATH.read_text().strip()
    raise FileNotFoundError(f"No tracker ID provided and {TRACKER_ID_PATH} not found.")


def _init_client():
    creds = _get_credentials()
    return gspread.authorize(creds)


def _get_or_create_tracker(gc, tracker_id: str, sheet_title: Optional[str] = None):
    try:
        doc = gc.open_by_key(tracker_id)
    except gspread.exceptions.SpreadsheetNotFound:
        # Create new
        title = sheet_title or "GEO Prospect Tracker"
        doc = gc.create(title)
        ws = doc.sheet1
        ws.append_row([
            "Date", "Rank", "URL", "Company", "Vertical",
            "Overall Score", "Grade", "LLM Readiness",
            "Word Count", "Error",
            "Structured Data", "AI Crawl", "Sitemap",
            "Content Depth", "FAQ", "Headings",
            "Semantic HTML", "Social Meta",
            "Gaps", "Recommendations",
        ])
        ws.format('A1:T1', {'textFormat': {'bold': True}})
        # Save ID for future use
        TRACKER_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
        TRACKER_ID_PATH.write_text(doc.id)
    return doc


def append_to_tracker(results, new_sheet=False, quiet=False, sheet_title=None, tracker_id=None):
    """
    Append GEO scanner results to the Google Sheets tracker.
    Returns the tracker sheet URL.
    """
    gc = _init_client()
    tid = _get_tracker_id(tracker_id)

    if new_sheet:
        title = sheet_title or f"GEO Prospect Tracker {date.today().isoformat()}"
        doc = gc.create(title)
        ws = doc.sheet1
        ws.append_row([
            "Date", "Rank", "URL", "Company", "Vertical",
            "Overall Score", "Grade", "LLM Readiness",
            "Word Count", "Error",
            "Structured Data", "AI Crawl", "Sitemap",
            "Content Depth", "FAQ", "Headings",
            "Semantic HTML", "Social Meta",
            "Gaps", "Recommendations",
        ])
        ws.format('A1:T1', {'textFormat': {'bold': True}})
        TRACKER_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
        TRACKER_ID_PATH.write_text(doc.id)
    else:
        doc = _get_or_create_tracker(gc, tid, sheet_title)

    ws = doc.sheet1
    today = date.today().isoformat()
    scored = [r for r in results if r.get("overall_score") is not None]
    errors = [r for r in results if r.get("overall_score") is None]
    rows = []
    for i, r in enumerate(scored, start=1):
        dims = r.get("dimensions", {})
        rows.append([
            today,
            i,
            r.get("url", ""),
            r.get("company", ""),
            r.get("vertical", ""),
            r.get("overall_score", ""),
            r.get("grade", ""),
            r.get("llm_readiness", ""),
            r.get("word_count", ""),
            r.get("error", ""),
            dims.get("structured_data", {}).get("score", ""),
            dims.get("ai_crawl_access", {}).get("score", ""),
            dims.get("sitemap_quality", {}).get("score", ""),
            dims.get("content_depth", {}).get("score", ""),
            dims.get("faq_content", {}).get("score", ""),
            dims.get("heading_structure", {}).get("score", ""),
            dims.get("semantic_html", {}).get("score", ""),
            dims.get("social_meta", {}).get("score", ""),
            " | ".join(r.get("gaps", [])),
            " | ".join(r.get("recommendations", [])),
        ])
    for r in errors:
        rows.append([
            today,
            "",
            r.get("url", ""),
            r.get("company", ""),
            r.get("vertical", ""),
            "",
            "",
            "",
            "",
            r.get("error", ""),
            "", "", "", "", "", "", "", "",
            "", "",
        ])

    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")

    if not quiet:
        print(f"   Appended {len(rows)} rows to tracker.")

    return f"https://docs.google.com/spreadsheets/d/{doc.id}/edit"
