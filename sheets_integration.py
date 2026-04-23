#!/usr/bin/env python3
"""
Google Sheets integration for GEO Scanner.

Handles:
  - OAuth2 authentication with the client_secret JSON file
  - Creating new spreadsheets
  - Opening/appending to a persistent tracker spreadsheet
  - Writing prospect rows and summary stats

Spreadsheet ID is persisted at SHEETS_TRACKER_ID_FILE so subsequent runs
append to the same tracker sheet.
"""

import json
import os
from pathlib import Path
from typing import Optional

import gspread
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Path where the spreadsheet ID is persisted between runs
SHEETS_TRACKER_ID_FILE = Path.home() / '.hermes' / 'geo_sheets_tracker_id.txt'
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
]


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------


def _get_client_secret_path() -> Optional[Path]:
    """Look for the OAuth client secret JSON in common locations."""
    candidates = [
        Path.home() / 'Desktop' / 'client_secret_347962967117-mmaob4or2vbh0k3fli2t6te25oke87fp.apps.googleusercontent.com.json',
        Path.home() / 'Downloads' / 'client_secret_347962967117-mmaob4or2vbh0k3fli2t6te25oke87fp.apps.googleusercontent.com.json',
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def get_sheets_client() -> gspread.Client:
    """Authenticate and return a gspread client."""
    cred_path = _get_client_secret_path()
    if not cred_path:
        raise FileNotFoundError(
            'OAuth client secret JSON not found. '
            'Place it on Desktop or Downloads as '
            'client_secret_347962...apps.googleusercontent.com.json'
        )

    token_path = Path.home() / '.hermes' / 'google_sheets_token.json'

    # Try to load existing token
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_info(
                json.loads(token_path.read_text()), SCOPES
            )
            if creds and creds.valid:
                return gspread.authorize(creds)
        except Exception:
            pass

    # Do the OAuth flow using browser-based redirect
    flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
    creds = flow.run_local_server(port=0)

    # Persist token
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())

    return gspread.authorize(creds)


# -----------------------------------------------------------------------------
# Spreadsheet management
# -----------------------------------------------------------------------------


def get_tracker_id() -> Optional[str]:
    """Return the persisted tracker spreadsheet ID, or None if not set."""
    if SHEETS_TRACKER_ID_FILE.exists():
        return SHEETS_TRACKER_ID_FILE.read_text().strip() or None
    return None


def save_tracker_id(spreadsheet_id: str) -> None:
    """Persist the tracker spreadsheet ID."""
    SHEETS_TRACKER_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    SHEETS_TRACKER_ID_FILE.write_text(spreadsheet_id)


def get_or_create_tracker(client: gspread.Client, new_sheet: bool = False,
                          sheet_title: Optional[str] = None) -> gspread.Spreadsheet:
    """
    Return the tracker spreadsheet.
    If new_sheet=True, always creates a fresh spreadsheet.
    Otherwise opens the existing tracker or creates one named 'GEO Prospect Tracker'.
    If sheet_title is provided, uses it as the title for new spreadsheets.
    """
    if new_sheet:
        if sheet_title:
            title = sheet_title
        else:
            title = f"GEO Prospect Tracker — {__import__('datetime').date.today().strftime('%b %d %Y')}"
        ss = client.create(title)
        save_tracker_id(ss.id)
        _setup_spreadsheet(ss)
        return ss

    tracker_id = get_tracker_id()
    if tracker_id:
        try:
            ss = client.open_by_key(tracker_id)
            return ss
        except gspread.SpreadsheetNotFound:
            pass

    # Create fresh tracker if none exists
    title = 'GEO Prospect Tracker'
    try:
        ss = client.create(title)
    except Exception:
        # Might fail if client doesn't have Drive scope — create with a timestamp
        title = f"GEO Prospect Tracker — {__import__('datetime').date.today().strftime('%b %d %Y')}"
        ss = client.create(title)
    save_tracker_id(ss.id)
    _setup_spreadsheet(ss)
    return ss


def _setup_spreadsheet(ss: gspread.Spreadsheet) -> None:
    """Set up the spreadsheet tabs and headers."""
    # Rename default sheet to Prospects
    try:
        sheet = ss.sheet1
        sheet.update_title('Prospects')
    except Exception:
        pass

    # Ensure Summary tab exists
    try:
        ss.add_worksheet('Summary', rows=30, cols=10)
    except Exception:
        pass

    # Write headers
    headers = [
        'Rank', 'URL', 'Company', 'Vertical', 'Overall Score', 'Grade',
        'LLM Readiness', 'Word Count',
        'Structured Data', 'AI Crawl Access', 'Sitemap Quality',
        'Content Depth', 'FAQ Content', 'Heading Structure',
        'Semantic HTML', 'Social Meta',
        'Top Gaps', 'Recommendations', 'Date Scanned',
    ]
    try:
        ss.sheet1.insert_row(headers, 1)
    except Exception:
        pass

    try:
        summary = ss.worksheet('Summary')
        summary.update(values=[
            ['GEO Prospect Summary', ''],
            ['Generated', ''],
            ['Total Sites Scored', ''],
            ['Average Score', ''],
            ['Score Range', ''],
            ['Grade Distribution', ''],
            ['', ''],
            ['Top Gaps (count)', ''],
        ], range_name='A1')
        summary.update(values='GEO Prospect Summary', range_name='A1')
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Writing results
# -----------------------------------------------------------------------------


def write_results(ss: gspread.Spreadsheet, results: list[dict], quiet: bool = False) -> None:
    """Append scored results to the Prospects tab and update Summary."""
    scored = [r for r in results if r.get('overall_score') is not None]
    if not scored:
        return

    today = __import__('datetime').date.today().strftime('%Y-%m-%d')

    # Build rows for Prospects sheet
    rows = []
    for i, r in enumerate(scored, 1):
        dims = r.get('dimensions', {})
        row = [
            i,                                          # Rank
            r.get('url', ''),                          # URL
            r.get('company', ''),                      # Company
            r.get('vertical', ''),                     # Vertical
            r.get('overall_score', ''),                # Overall Score
            r.get('grade', ''),                        # Grade
            r.get('llm_readiness', ''),                # LLM Readiness
            r.get('word_count', ''),                   # Word Count
            dims.get('structured_data', {}).get('score', ''),
            dims.get('ai_crawl_access', {}).get('score', ''),
            dims.get('sitemap_quality', {}).get('score', ''),
            dims.get('content_depth', {}).get('score', ''),
            dims.get('faq_content', {}).get('score', ''),
            dims.get('heading_structure', {}).get('score', ''),
            dims.get('semantic_html', {}).get('score', ''),
            dims.get('social_meta', {}).get('score', ''),
            ' | '.join(r.get('gaps', [])[:3]),          # Top Gaps
            ' | '.join(r.get('recommendations', [])[:3]),  # Recommendations
            today,                                       # Date
        ]
        rows.append(row)

    # Append to Prospects sheet
    try:
        prospects = ss.sheet1 if ss.sheet1.title == 'Prospects' else ss.worksheet('Prospects')
        prospects.append_rows(rows)
        if not quiet:
            print(f"  → Appended {len(rows)} rows to 'Prospects' tab")
    except Exception as e:
        print(f"  ⚠ Could not write to Prospects tab: {e}")

    # Update Summary tab
    _update_summary(ss, scored, today, quiet)


def _update_summary(ss: gspread.Spreadsheet, scored: list[dict], today: str, quiet: bool) -> None:
    try:
        summary = ss.worksheet('Summary')
    except Exception:
        return

    total = len(scored)
    avg = sum(r['overall_score'] for r in scored) / total
    scores = [r['overall_score'] for r in scored]
    grades = {}
    for r in scored:
        g = r.get('grade', '?')
        grades[g] = grades.get(g, 0) + 1

    grade_dist = ', '.join(f"{g}: {c}" for g, c in sorted(grades.items()))

    # Count all gaps
    gap_counts: dict[str, int] = {}
    for r in scored:
        for gap in r.get('gaps', []):
            # Normalize gap to first 60 chars for grouping
            short = gap[:60]
            gap_counts[short] = gap_counts.get(short, 0) + 1
    top_gaps = sorted(gap_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    gap_lines = [f"{g[:55]}... ({c})" if len(g) > 55 else f"{g} ({c})" for g, c in top_gaps]

    summary_data = [
        ['GEO Prospect Summary', ''],
        ['Generated', today],
        ['Total Sites Scored', total],
        ['Average Score', round(avg, 1)],
        ['Score Range', f"{min(scores)} – {max(scores)}"],
        ['Grade Distribution', grade_dist],
        ['', ''],
        ['Top Gaps', 'Sites Affected'],
        *[[g, c] for g, c in top_gaps],
    ]

    try:
        summary.clear()
        summary.update('A1', summary_data)
        if not quiet:
            print(f"  → Updated 'Summary' tab")
    except Exception as e:
        print(f"  ⚠ Could not update Summary tab: {e}")


# -----------------------------------------------------------------------------
# Convenience
# -----------------------------------------------------------------------------


def append_to_tracker(results: list[dict], new_sheet: bool = False,
                      quiet: bool = False, sheet_title: Optional[str] = None,
                      tracker_id: Optional[str] = None) -> str:
    """
    Main entry point from geo_scanner.py.
    Authenticates, opens (or creates) the tracker, writes results.
    Returns the spreadsheet URL.
    If sheet_title is provided, uses it as the spreadsheet title (for new sheets).
    If tracker_id is provided, writes directly to that spreadsheet (bypasses default tracker).
    """
    client = get_sheets_client()
    if tracker_id:
        ss = client.open_by_key(tracker_id)
        if not quiet:
            print(f"  → Writing to spreadsheet: {ss.url}")
    else:
        ss = get_or_create_tracker(client, new_sheet=new_sheet, sheet_title=sheet_title)
    write_results(ss, results, quiet=quiet)
    return ss.url


if __name__ == '__main__':
    # Test: create a dummy result
    client = get_sheets_client()
    print(f'Authenticated OK')

    ss = get_or_create_tracker(client, new_sheet=False)
    print(f'Tracker: {ss.url}')
