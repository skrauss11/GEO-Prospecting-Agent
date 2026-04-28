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
# Executive/Consultative Tone. Focuses on the strategic impact (brand presence, 
# AI search share-of-voice) rather than just technical SEO jargon.
HOOKS = {
    "schema": [
        "I was mapping the AI search landscape for {city} {search_context}s and noticed {company} has zero Schema.org / JSON-LD markup. This is where established firms are paying an 'AI bureaucracy tax' — agile competitors are moving fast to add this structured data, making it much easier for ChatGPT and Perplexity to parse and recommend their services over yours for highly specific queries.",
        "When buyers ask AI assistants for '{search_context} near me', the models scan the live web for structured data to decide who fits best. {company}'s site currently has no JSON-LD markup. In AI search, legacy brand recognition is losing ground to technical agility, and faster-moving competitors are capturing the citations you should be getting."
    ],
    "sitemap": [
        "I noticed {company}'s sitemap is missing or incomplete. In the AI search era, we're seeing smaller, faster-moving competitors use optimized sitemaps to spoon-feed their service pages directly to Perplexity and ChatGPT. Because your site lacks this structure, AI models are increasingly citing these agile competitors for deep expertise queries instead of you.",
        "I was reviewing {company}'s AI search visibility and found that AI crawlers are struggling to index your site due to an incomplete sitemap. While large firms often move slower to fix technical debt, nimble competitors are exploiting this exact gap to steal share-of-voice in AI-generated answers."
    ],
    "faq": [
        "When buyers ask AI assistants complex questions about {search_context} services, the models heavily favor Q&A-formatted content. Because {company} lacks a structured FAQ, we're seeing faster-moving competitors exploit this gap — providing the exact format LLMs prefer to cite, and stealing visibility from established market leaders.",
        "I noticed {company} doesn't have an FAQ section. In AI search, brand equity doesn't automatically win. Instead, LLMs like ChatGPT pull directly from structured Q&A formats to answer buyer questions. Without it, you are absent from those early-stage research conversations while agile competitors take the citations."
    ],
    "bot_blocked": [
        "I noticed {company} is actively blocking AI crawlers (like GPTBot) in your robots.txt. While this protects IP, it blinds AI engines to your current expertise. Agile competitors are making sure platforms like Perplexity can crawl their latest capabilities, meaning they win the live queries while established firms get skipped.",
        "Your site is currently blocking major AI crawlers. The trade-off for protecting your content is that AI engines fall back to citing whatever they can read right now. We're seeing faster-moving competitors keep their sites open to these bots, allowing them to capture the AI recommendations that should go to industry leaders."
    ],
    "thin_content": [
        "AI models (like ChatGPT and Perplexity) rely on content depth to confidently recommend a firm. Right now, {company}'s homepage is quite light on context (~{word_count} words). We're seeing a shift where nimble competitors out-rank established giants in AI search simply by structuring deep, rich context that the LLMs can easily digest.",
        "I was analyzing {company}'s AI visibility and noticed the core pages are quite sparse. LLMs use content depth as a primary proxy for expertise. While established firms lean on reputation, agile competitors are winning AI citations by providing the exhaustive detail that generative engines are specifically looking for."
    ],
    "heading": [
        "I ran an AI visibility parse on {company} and noticed the page heading structure is broken. Because AI models rely heavily on H1/H2 hierarchy to understand a firm's core offerings, this technical debt creates a 'bureaucracy tax' where faster competitors with clean code are easily grabbing the featured citations."
    ],
    "social_meta": [
        "I noticed {company} is missing OpenGraph meta tags. While it seems minor, LLMs synthesize results for '{search_context} in {city}' by evaluating technical discipline. Missing tags act as a negative signal. Right now, faster-moving competitors are optimizing these technical details and pulling ahead in AI-generated recommendations."
    ],
    "llms.txt": [
        "I was looking at {company}'s site and noticed you haven't implemented an llms.txt file yet. It's early, but agile {search_context}s are already adding these to explicitly tell AI crawlers how to summarize their firm. It's a low-effort way to bypass the 'bureaucracy tax' and control your brand narrative in ChatGPT before the giants catch up."
    ],
    "generic": [
        "I ran an AI visibility audit on {company} and found several infrastructure gaps. Right now, there is a serious 'bureaucracy tax' in AI search: agile competitors are adapting their sites for ChatGPT and Perplexity in weeks, while established firms lag. Those faster firms are capturing the early-stage buyer recommendations that should belong to you.",
        "Most legacy {search_context}s haven't optimized for AI search yet — {company} included. The window to establish a first-mover advantage is open. While large competitors wait for committee approvals, fixing the technical signals that AI crawlers rely on is the fastest way to steal disproportionate share-of-voice."
    ],
}

# ── CTA variants ──────────────────────────────────────────────────────────────
CTAS = [
    "I put together a brief GEO (Generative Engine Optimization) snapshot showing exactly how AI models view {company} today, along with a roadmap to fix it. Worth sending over?",
    "I mapped {company}'s exact AI visibility across our 8-point GEO framework. I have a PDF showing where you rank and what to fix. Should I send it your way?",
    "I packaged these insights into a quick, free GEO Snapshot showing your scores across all 8 dimensions and a 90-day fix roadmap. Happy to share the PDF if it's helpful."
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
    # Ensure search_context includes 'firm', 'group', etc. if it's just 'accounting' or 'law'
    display_context = search_context
    if display_context in ["accounting", "law", "consulting"]:
        display_context += " firm"
        
    for gap in gaps[:2]:
        key = _map_gap_to_key(gap)
        templates = HOOKS.get(key, HOOKS["generic"])
        tmpl = random.choice(templates)
        try:
            return tmpl.format(
                company=company,
                word_count=word_count,
                search_context=display_context,
                article=article,
                city=city,
                vertical=vertical,
            )
        except KeyError:
            continue
    return random.choice(HOOKS["generic"]).format(
        company=company,
        word_count=word_count,
        search_context=display_context,
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
