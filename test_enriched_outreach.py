import os, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, '/Users/scottkrauss/Desktop/Claude Code Test/web-research-agent')

from shared.hunter_client import HunterClient
from shared.enrichment import pick_best_contact
from shared.outreach_email import generate_outreach_email

hot_leads = [
    {"company_name": "RSM US", "website": "https://rsmus.com", "geo_score": 1, "priority": "hot", "contacts.emails": "", "geo_analysis.gaps": "No FAQ section -- LLMs lose Q&A-structured context...\nNo sitemap.xml or incomplete sitemap"},
    {"company_name": "Wiss & Company", "website": "https://wiss.com", "geo_score": 1, "priority": "hot", "contacts.emails": "", "geo_analysis.gaps": "AI bots blocked in robots.txt (chatgpt-user)\nNo sitemap.xml or incomplete sitemap\nNo FAQ section -- LLMs lose Q&A-structured context"},
    {"company_name": "Kasowitz Benson Torres LLP", "website": "https://www.kasowitz.com", "geo_score": 1, "priority": "hot", "contacts.emails": "infonewyork@kasowitz.com", "geo_analysis.gaps": "No JSON-LD schema\nNo FAQ content\nThin homepage content"},
]

client = HunterClient()

for lead in hot_leads:
    domain = lead["website"].replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    print(f"\n{'='*60}")
    print(f"  ENRICHING: {lead['company_name']} ({domain})")
    print(f"{'='*60}")

    result = client.domain_search(domain, limit=10)
    best = pick_best_contact(result.contacts)

    if best:
        print(f"  Found: {best.full_name} | {best.position} | {best.email}")
        enriched = {
            "name": best.full_name,
            "position": best.position,
            "email": best.email,
            "confidence": best.confidence,
            "linkedin": best.linkedin,
        }
    else:
        print(f"  No suitable contact found")
        enriched = None

    email = generate_outreach_email(lead, enriched_contact=enriched)
    print(f"\n  Subject: {email.subject}")
    print(f"\n  --- BODY ---")
    print(email.text_body)

client.close()
