"""
Outreach email generation for MadTech Growth.

Takes an enriched prospect (from Airtable + Hunter + GEO analysis) and produces
personalized HTML / text cold email copy.  Uses the brand design system v2:
  • Cream / Sage / Clay palette
  • DM Serif Display + Outfit typography
  • Personalized hook based on their top GEO gap

Usage:
    from shared.outreach_email import generate_outreach_email
    email_body, subject = generate_outreach_email(prospect, snapshot_pdf_path)
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ── Brand palette (design v2) ─────────────────────────────────────────────────
BRAND = {
    "cream": "#FAF7F2",
    "card": "#FFFDF8",
    "ink": "#1A1D1E",
    "ink_soft": "#3B3F42",
    "muted": "#7A7568",
    "line": "#E6DFD0",
    "sage": "#7A9B76",
    "sage_deep": "#4A6B46",
    "sage_soft": "#E8F0E6",
    "clay": "#C45D3E",
    "clay_deep": "#9C4527",
    "clay_soft": "#F5E0DA",
}

# ── Hook templates by gap category ──────────────────────────────────────────
# Each hook is specific to the gap, references real search queries a buyer
# would type, and ties the problem directly to lost deal flow.
HOOKS = {
    "schema": [
        "I checked how AI search engines see {company} and found zero Schema.org / JSON-LD markup. That matters because when someone asks ChatGPT or Perplexity for 'the best {search_context} firm in {city}' the AI needs structured data to understand your services, locations, and ratings. Without it, {company} simply doesn't show up in those answers \u2014 even though your reputation offline is strong.",
        "When prospects ask AI assistants for '{search_context} firm near me' the model scans for structured data to decide who to recommend. {company}'s site has none \u2014 no LocalBusiness schema, no service markup, no attorney/organization markup. That means your competitors with basic JSON-LD are getting the citations you should be getting.",
    ],
    "sitemap": [
        "{company}'s site is missing a proper sitemap.xml. That matters because AI crawlers like GPTBot and PerplexityBot rely on sitemaps to discover service pages, attorney bios, and location pages. Without one, those pages may never get indexed by AI search \u2014 which means when someone searches '{search_context} firm {city}' the model has no record of {company}'s depth.",
        "I noticed {company}'s sitemap is either missing or incomplete. For a firm with {company}'s practice breadth, that's a bottleneck: AI crawlers can only surface what they can find, and if your service pages, thought leadership, and team pages aren't in the sitemap, they're invisible to LLMs.",
    ],
    "faq": [
        "{company} has no FAQ content. That's a direct visibility loss because LLMs prioritize Q&A format when answering searches like 'how much does {article} {search_context} firm cost in {city}' or 'what should I look for in {article} {search_context} firm.' Firms with FAQ pages get quoted verbatim in AI-generated answers. {company} is missing from those conversations entirely.",
        "Buyers now ask AI assistants specific questions before they ever call a firm: 'what's the difference between audit and assurance' or 'do I need {article} {search_context} firm for X.' Without an FAQ section, {company} has no content in the format LLMs prefer to cite. Competitors who do are effectively answering your prospects before you get a chance to.",
    ],
    "bot_blocked": [
        "{company} is blocking AI crawlers in robots.txt \u2014 specifically GPTBot and ClaudeBot. That may feel like protecting IP, but the trade-off is total exclusion from ChatGPT search, Perplexity, and Copilot. These platforms are now where senior buyers research firms before RFPs. Blocking them means {company} isn't even in the consideration set when someone asks 'who are the top {search_context} firms.'",
        "I saw that {company} blocks major AI crawlers. The risk isn't content theft \u2014 it's invisibility. When a CFO asks Perplexity 'which {search_context} firm has the best reputation in {city}' and {company} isn't indexed, the AI simply recommends your competitors. You're not losing a click; you're losing the query entirely.",
    ],
    "thin_content": [
        "{company}'s homepage is only ~{word_count} words. For an LLM trying to understand what {company} does, who you serve, and why you're different, that's barely a signal. When buyers ask AI 'which {search_context} firm specializes in {vertical}' the model needs content depth to make the connection. A thin homepage means {company} doesn't make the shortlist.",
        "The homepage has ~{word_count} words. Compare that to competitors who have 1,500+ words describing services, case studies, and team credentials. LLMs use content depth as a proxy for authority. A sparse homepage signals to AI that {company} isn't a primary source \u2014 so it recommends firms with richer pages instead.",
    ],
    "heading": [
        "{company}'s heading structure is broken \u2014 missing H1s or multiple conflicting ones. LLMs use heading hierarchy to understand page importance and topic focus. When someone asks 'what services does {company} offer' the AI can't extract a clear answer because the headings don't structure the information. Competitors with clean hierarchy get the featured citation.",
    ],
    "social_meta": [
        "No OpenGraph tags on {company}'s site. That hurts social sharing, but more importantly it signals to AI that page context hasn't been curated. When LLMs synthesize results for 'best {search_context} firm in {city}' they prefer pages with complete metadata because it indicates editorial attention. Missing OG tags is a small signal of a larger content discipline gap.",
    ],
    "llms.txt": [
        "{company} doesn't have an llms.txt file. It's early, but forward-thinking firms are adding them now to tell AI crawlers exactly what they do, who they serve, and how to contact them. It's like a robots.txt for the AI era. Firms that adopt it early will have a structured advantage before it becomes standard.",
    ],
    "generic": [
        "I ran an AI visibility audit on {company} and found several infrastructure gaps that are making it harder for LLMs to understand and recommend the firm. The issue isn't content quality \u2014 it's that the technical signals AI crawlers rely on are either missing or misconfigured. In a market where buyers now ask AI before they ask Google, that's a real funnel problem.",
        "Most professional services firms haven't optimized for AI search yet \u2014 {company} included. The window to establish first-mover advantage is open because your competitors are in the same position. But the window closes as firms wake up to the fact that AI search is now a primary discovery channel for enterprise buyers.",
    ],
}

# ── CTA variants ──────────────────────────────────────────────────────────────
CTAS = [
    "I built a free 8-dimension GEO Snapshot that shows exactly where {company} stands and what to fix first. Happy to send it over — no pitch, just signal.",
    "I put together a complimentary GEO Snapshot for {company} — 8 dimensions, scored, with a prioritized fix list. Want me to send it?",
    "I can send a free GEO Snapshot that breaks down {company}'s AI visibility across all 8 dimensions. Takes two minutes to read, gives you a 90-day roadmap. Interested?",
]

# ── Signatures ────────────────────────────────────────────────────────────────────────
SIG = """Scott Krauss
Founder, MadTech Growth
AI Visibility for Professional Services
scott@madtechgrowth.com | madtechgrowth.com
"""

SIG_HTML = f"""<div style="margin-top:32px;padding-top:20px;border-top:1px solid {BRAND['line']};">
  <p style="margin:0;font-size:14px;color:{BRAND['ink']};font-weight:600;">Scott Krauss</p>
  <p style="margin:4px 0 0;font-size:13px;color:{BRAND['muted']};">Founder, MadTech Growth</p>
  <p style="margin:2px 0 0;font-size:13px;color:{BRAND['muted']};">AI Visibility for Professional Services</p>
  <p style="margin:8px 0 0;font-size:13px;"><a href="mailto:scott@madtechgrowth.com" style="color:{BRAND['sage_deep']};text-decoration:none;">scott@madtechgrowth.com</a>&nbsp;&nbsp;|&nbsp;&nbsp;<a href="https://madtechgrowth.com" style="color:{BRAND['sage_deep']};text-decoration:none;">madtechgrowth.com</a></p>
</div>"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _map_gap_to_key(gap: str) -> str:
    """Map a raw gap string to a template category key."""
    gap_lower = gap.lower()
    if "schema" in gap_lower or "json-ld" in gap_lower or "structured data" in gap_lower:
        return "schema"
    if "sitemap" in gap_lower:
        return "sitemap"
    if "faq" in gap_lower:
        return "faq"
    if "bot" in gap_lower or "robots.txt" in gap_lower or "blocked" in gap_lower:
        return "bot_blocked"
    if "thin" in gap_lower or "word" in gap_lower or "content" in gap_lower and "depth" in gap_lower:
        return "thin_content"
    if "heading" in gap_lower or "h1" in gap_lower:
        return "heading"
    if "opengraph" in gap_lower or "social" in gap_lower or "og " in gap_lower:
        return "social_meta"
    if "llms.txt" in gap_lower:
        return "llms.txt"
    return "generic"


def _infer_context(company: str, website: str) -> tuple[str, str, str, str]:
    """Infer search context base noun, article, city, and vertical from company/website."""
    comp_lower = company.lower()
    site_lower = website.lower()

    # Known firm mappings (base noun only, no "firm" suffix)
    known = {
        "rsm": "accounting",
        "wiss": "accounting",
        "anchin": "accounting",
        "deloitte": "accounting",
        "pwc": "accounting",
        "ey ": "accounting",
        "kpmg": "accounting",
        "bdo": "accounting",
        "grant thornton": "accounting",
        "kasowitz": "law",
        "skadden": "law",
        "sullivan": "law",
        "cravath": "law",
        "latham": "law",
        "kirkland": "law",
        "capco": "consulting",
        "mckinsey": "consulting",
        "bain": "consulting",
        "bcg": "consulting",
    }

    base = None
    for key, ctx in known.items():
        if key in comp_lower or key in site_lower:
            base = ctx
            break

    if not base:
        if "law" in comp_lower or "llp" in comp_lower or "torres" in comp_lower:
            base = "law"
        elif "cpa" in site_lower or "accounting" in comp_lower or "audit" in comp_lower:
            base = "accounting"
        elif "consult" in comp_lower or "advisory" in comp_lower:
            base = "consulting"
        elif "wealth" in comp_lower or "financial" in comp_lower:
            base = "wealth management"
        else:
            base = "professional services"

    article = "an" if base[0] in "aeiou" else "a"

    # Vertical (for thin_content template)
    if base == "law":
        vertical = "real estate litigation"
    elif base == "accounting":
        vertical = "tax advisory"
    elif base == "consulting":
        vertical = "digital transformation"
    else:
        vertical = "advisory"

    city = "New York"
    return base, article, city, vertical


def _build_hook(gaps: list[str], company: str, word_count: int = 0, search_context: str = "", article: str = "a", city: str = "", vertical: str = "") -> str:
    """Pick the most specific hook from the first 2 gaps."""
    for gap in gaps[:2]:
        key = _map_gap_to_key(gap)
        templates = HOOKS.get(key, HOOKS["generic"])
        tmpl = random.choice(templates)
        try:
            return tmpl.format(
                company=company,
                word_count=word_count,
                search_context=search_context,
                article=article,
                city=city,
                vertical=vertical,
            )
        except KeyError:
            continue
    return random.choice(HOOKS["generic"]).format(
        company=company,
        word_count=word_count,
        search_context=search_context,
        article=article,
        city=city,
        vertical=vertical,
    )


def _build_subject(company: str, gap_key: str) -> str:
    """Subject line tailored to the top gap."""
    subjects = {
        "schema": [
            f"Why AI search can't read {company}'s site yet",
            f"Quick thing I noticed about {company} + LLMs",
        ],
        "sitemap": [
            f"{company}'s sitemap and AI visibility",
            f"One technical gap at {company}",
        ],
        "faq": [
            f"{company} is missing an FAQ — here's why that matters for AI",
            f"AI search + {company}: one gap",
        ],
        "bot_blocked": [
            f"You're blocking AI crawlers at {company}",
            f"{company}'s robots.txt and AI search",
        ],
        "thin_content": [
            f"{company}'s homepage is thin for LLMs",
            f"One content gap hurting {company} in AI search",
        ],
        "generic": [
            f"Quick AI visibility note on {company}",
            f"Something I noticed about {company} + AI search",
        ],
    }
    return random.choice(subjects.get(gap_key, subjects["generic"]))


# ── Core function ─────────────────────────────────────────────────────────────

@dataclass
class OutreachResult:
    subject: str
    text_body: str
    html_body: str
    personalization: dict  # what data was used


def generate_outreach_email(
    prospect: dict,
    *,
    snapshot_pdf_path: Optional[Path] = None,
    enriched_contact: Optional[dict] = None,
) -> OutreachResult:
    """
    Generate personalized outreach email for an Airtable prospect.

    Args:
        prospect: Airtable record fields dict with keys:
            - company_name
            - website
            - geo_score
            - priority
            - geo_analysis.gaps (newline-separated string or list)
            - contacts.emails
        snapshot_pdf_path: Optional local path to attach / reference
        enriched_contact: Optional dict from Hunter enrichment:
            - name, position, email, confidence, linkedin

    Returns:
        OutreachResult with subject, text, HTML, and personalization metadata.
    """
    company = prospect.get("company_name", "Your Company")
    website = prospect.get("website", "")
    geo_score = prospect.get("geo_score", 0)

    # Parse gaps
    gaps_raw = prospect.get("geo_analysis.gaps", "")
    gaps = [g.strip() for g in str(gaps_raw).split("\n") if g.strip()] if isinstance(gaps_raw, str) else list(gaps_raw or [])

    # Contact
    contact = enriched_contact or {}
    contact_name = contact.get("name", "")
    contact_position = contact.get("position", "")
    contact_email = contact.get("email") or prospect.get("contacts.emails", "")

    first_name = contact_name.split()[0] if contact_name else "there"

    # Infer search context from company/website
    search_context, article, city, vertical = _infer_context(company, website)

    # Hook
    word_count = prospect.get("word_count", 0)
    hook = _build_hook(gaps, company, word_count, search_context, article, city, vertical)
    gap_key = _map_gap_to_key(gaps[0]) if gaps else "generic"

    # CTA
    cta = random.choice(CTAS).format(company=company)

    # Subject
    subject = _build_subject(company, gap_key)

    # --- TEXT BODY ---
    text_lines = [
        f"Hi {first_name},",
        "",
        hook,
        "",
        cta,
        "",
        "—",
        SIG,
    ]
    text_body = "\n".join(text_lines)

    # --- HTML BODY ---
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title></head>
<body style="margin:0;padding:0;background:{BRAND['cream']};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:{BRAND['ink']};">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BRAND['cream']};">
  <tr><td align="center" style="padding:40px 20px 28px;">
    <table width="560" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;width:100%;">
      <!-- Header -->
      <tr><td style="text-align:center;padding-bottom:28px;">
        <p style="font-family:Georgia,'Times New Roman',serif;font-size:20px;font-weight:700;color:{BRAND['ink']};margin:0;letter-spacing:-0.02em;">MadTech<span style="color:{BRAND['sage_deep']};">Growth</span></p>
        <p style="font-size:10px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:{BRAND['sage_deep']};margin:6px 0 0;">AI Visibility for Professional Services</p>
      </td></tr>

      <!-- Body card -->
      <tr><td style="background:{BRAND['card']};border:1px solid {BRAND['line']};border-radius:14px;padding:32px;">
        <p style="font-size:15px;color:{BRAND['ink']};margin:0 0 16px;line-height:1.7;">Hi {first_name},</p>

        <p style="font-size:15px;color:{BRAND['ink_soft']};margin:0 0 16px;line-height:1.7;">{hook}</p>

        <p style="font-size:15px;color:{BRAND['ink_soft']};margin:0 0 20px;line-height:1.7;">{cta}</p>

        {SIG_HTML}
      </td></tr>

      <!-- Footer -->
      <tr><td style="text-align:center;padding:24px 0 0;">
        <p style="font-size:11px;color:{BRAND['muted']};margin:0;line-height:1.6;">MadTech Growth · New York, NY</p>
      </td></tr>
    </table>
  </td></tr>
</table></body></html>"""

    return OutreachResult(
        subject=subject,
        text_body=text_body,
        html_body=html,
        personalization={
            "company": company,
            "contact": contact_name,
            "position": contact_position,
            "email": contact_email,
            "top_gap": gaps[0] if gaps else None,
            "gap_key": gap_key,
            "geo_score": geo_score,
            "snapshot_pdf": str(snapshot_pdf_path) if snapshot_pdf_path else None,
        },
    )


# ── CLI helper ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python3 shared/outreach_email.py '<json-prospect>'")
        sys.exit(1)

    prospect = json.loads(sys.argv[1])
    result = generate_outreach_email(prospect)
    print(f"Subject: {result.subject}\n")
    print("--- TEXT ---")
    print(result.text_body)
    print("\n--- HTML (preview) ---")
    print(result.html_body[:800] + "...")
