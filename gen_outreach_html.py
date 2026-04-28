import os, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, '/Users/scottkrauss/Desktop/Claude Code Test/web-research-agent')

from shared.hunter_client import HunterClient
from shared.enrichment import pick_best_contact
from shared.outreach_email import generate_outreach_email

hot_leads = [
    {'company_name': 'RSM US', 'website': 'https://rsmus.com', 'geo_score': 1, 'priority': 'hot', 'contacts.emails': '', 'geo_analysis.gaps': 'No FAQ section -- LLMs lose Q&A-structured context...\nNo sitemap.xml or incomplete sitemap'},
    {'company_name': 'Wiss & Company', 'website': 'https://wiss.com', 'geo_score': 1, 'priority': 'hot', 'contacts.emails': '', 'geo_analysis.gaps': 'AI bots blocked in robots.txt (chatgpt-user)\nNo sitemap.xml or incomplete sitemap\nNo FAQ section -- LLMs lose Q&A-structured context'},
    {'company_name': 'Kasowitz Benson Torres LLP', 'website': 'https://www.kasowitz.com', 'geo_score': 1, 'priority': 'hot', 'contacts.emails': 'infonewyork@kasowitz.com', 'geo_analysis.gaps': 'No JSON-LD schema\nNo FAQ content\nThin homepage content'},
]

client = HunterClient()
for lead in hot_leads:
    domain = lead['website'].replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
    result = client.domain_search(domain, limit=10)
    best = pick_best_contact(result.contacts)
    enriched = {'name': best.full_name, 'position': best.position, 'email': best.email, 'confidence': best.confidence, 'linkedin': best.linkedin} if best else None
    email = generate_outreach_email(lead, enriched_contact=enriched)
    fname = domain.replace('.', '_')
    path = f'/Users/scottkrauss/Desktop/Claude Code Test/web-research-agent/outreach_{fname}.html'
    with open(path, 'w') as f:
        f.write(email.html_body)
    print(f'Wrote {path} ({len(email.html_body)} bytes)')
    print(f'  Subject: {email.subject}')
    print(f'  To: {enriched["name"] if enriched else "N/A"} <{enriched["email"] if enriched else "N/A"}>')
    print()
client.close()
