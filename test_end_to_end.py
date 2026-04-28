"""
End-to-end test: Airtable hot leads -> Hunter enrichment -> GEO Snapshot -> Outreach email.
Prints a summary of the full pipeline for manual review before sending.
"""

import os, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, '/Users/scottkrauss/Desktop/Claude Code Test/web-research-agent')

from shared.airtable import AirtableClient
from shared.hunter_client import HunterClient
from shared.enrichment import pick_best_contact
from shared.outreach_email import generate_outreach_email
from pathlib import Path

# ── 1. Pull hot leads from Airtable ──────────────────────────────────────────
client = AirtableClient()
base_id = os.environ.get("AIRTABLE_BASE_ID")
table = os.environ.get("AIRTABLE_TABLE_NAME", "Prospects")

import httpx, urllib.parse
formula = "{priority}='hot'"
enc = urllib.parse.quote(formula, safe='')
url = f"https://api.airtable.com/v0/{base_id}/{urllib.parse.quote(table)}?filterByFormula={enc}&maxRecords=20"
resp = httpx.get(url, headers={"Authorization": f"Bearer {client.token}"})
records = resp.json().get("records", [])

print(f"\n{'='*70}")
print("  END-TO-END TEST: Hot Lead Outreach Pipeline")
print(f"{'='*70}")
print(f"\nPulled {len(records)} hot leads from Airtable: {table}")

# ── 2. Enrich + Generate for each ────────────────────────────────────────────
hunter = HunterClient()
proposals_dir = Path("/Users/scottkrauss/Desktop/Claude Code Test/web-research-agent/proposals/2026-04-27")

for r in records:
    fields = r["fields"]
    company = fields.get("company_name", "Unknown")
    website = fields.get("website", "")
    if not website:
        continue

    domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

    # Enrich with Hunter
    result = hunter.domain_search(domain, limit=10)
    best = pick_best_contact(result.contacts)

    enriched = None
    if best:
        enriched = {
            "name": best.full_name,
            "position": best.position,
            "email": best.email,
            "confidence": best.confidence,
            "linkedin": best.linkedin,
        }

    # Generate outreach email
    email = generate_outreach_email(fields, enriched_contact=enriched)

    # Find matching snapshot PDF
    pdf_path = None
    for f in proposals_dir.glob("*.pdf"):
        if domain.replace(".", "_") in f.name or company.lower().replace(" ", "_") in f.name.lower():
            pdf_path = f
            break

    print(f"\n{'─'*70}")
    print(f"  {company}")
    print(f"{'─'*70}")
    print(f"  Website:      {website}")
    print(f"  Contact:      {enriched['name'] if enriched else 'N/A'} ({enriched['position'] if enriched else 'N/A'})")
    print(f"  Email:        {enriched['email'] if enriched else fields.get('contacts.emails', 'N/A')}")
    print(f"  Snapshot PDF: {pdf_path.name if pdf_path else 'NOT FOUND'}")
    print(f"  Subject:      {email.subject}")
    print(f"\n  --- EMAIL BODY ---")
    print(email.text_body)

hunter.close()
print(f"\n{'='*70}")
print("  End-to-end test complete.")
print(f"{'='*70}")
