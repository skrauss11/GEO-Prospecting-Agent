import sys
sys.path.insert(0, '/Users/scottkrauss/Desktop/Claude Code Test/web-research-agent')
from shared.outreach_email import generate_outreach_email

# RSM US
lead = {'company_name': 'RSM US', 'website': 'https://rsmus.com', 'geo_score': 1, 'priority': 'hot', 'contacts.emails': '', 'geo_analysis.gaps': 'No FAQ section -- LLMs lose Q&A-structured context...\nNo sitemap.xml or incomplete sitemap'}
enriched = {'name': 'Patrick Kitchen', 'position': 'Partner', 'email': 'patrick.kitchen@rsmus.com', 'confidence': 99, 'linkedin': ''}
email = generate_outreach_email(lead, enriched_contact=enriched)
print('=== RSM US -> Patrick Kitchen ===')
print('Subject:', email.subject)
print()
print(email.text_body)
print()
print('=== END ===')
print()

# Wiss
lead = {'company_name': 'Wiss & Company', 'website': 'https://wiss.com', 'geo_score': 1, 'priority': 'hot', 'contacts.emails': '', 'geo_analysis.gaps': 'AI bots blocked in robots.txt (chatgpt-user)\nNo sitemap.xml or incomplete sitemap\nNo FAQ section -- LLMs lose Q&A-structured context'}
enriched = {'name': 'Brian Kloza', 'position': 'Partner', 'email': 'bkloza@wiss.com', 'confidence': 99, 'linkedin': ''}
email = generate_outreach_email(lead, enriched_contact=enriched)
print('=== WISS -> Brian Kloza ===')
print('Subject:', email.subject)
print()
print(email.text_body)
print()
print('=== END ===')
print()

# Kasowitz
lead = {'company_name': 'Kasowitz Benson Torres LLP', 'website': 'https://www.kasowitz.com', 'geo_score': 1, 'priority': 'hot', 'contacts.emails': 'infonewyork@kasowitz.com', 'geo_analysis.gaps': 'No JSON-LD schema\nNo FAQ content\nThin homepage content'}
enriched = {'name': 'Matthew McElroy', 'position': 'Real Estate Partner', 'email': 'mmcelroy@kasowitz.com', 'confidence': 99, 'linkedin': ''}
email = generate_outreach_email(lead, enriched_contact=enriched)
print('=== KASOWITZ -> Matthew McElroy ===')
print('Subject:', email.subject)
print()
print(email.text_body)
print()
print('=== END ===')
