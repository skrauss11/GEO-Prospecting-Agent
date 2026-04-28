import json, sys
sys.path.insert(0, '/Users/scottkrauss/Desktop/Claude Code Test/web-research-agent')
from shared.outreach_email import generate_outreach_email

prospects = [
    {
        'company_name': 'RSM US',
        'website': 'https://rsmus.com',
        'geo_score': 1,
        'priority': 'hot',
        'contacts.emails': '',
        'geo_analysis.gaps': 'No FAQ section -- LLMs lose Q&A-structured context...\nNo sitemap.xml or incomplete sitemap',
    },
    {
        'company_name': 'Wiss & Company',
        'website': 'https://wiss.com',
        'geo_score': 1,
        'priority': 'hot',
        'contacts.emails': '',
        'geo_analysis.gaps': 'AI bots blocked in robots.txt (chatgpt-user)\nNo sitemap.xml or incomplete sitemap\nNo FAQ section -- LLMs lose Q&A-structured context',
    },
    {
        'company_name': 'Kasowitz Benson Torres LLP',
        'website': 'https://www.kasowitz.com',
        'geo_score': 1,
        'priority': 'hot',
        'contacts.emails': 'infonewyork@kasowitz.com',
        'geo_analysis.gaps': 'No JSON-LD schema\nNo FAQ content\nThin homepage content',
    },
]

for p in prospects:
    print(f"\n{'='*60}")
    print(f"  EMAIL FOR: {p['company_name']}")
    print(f"{'='*60}")
    result = generate_outreach_email(p)
    print(f"\nSubject: {result.subject}")
    print(f"\n--- TEXT BODY ---")
    print(result.text_body)
