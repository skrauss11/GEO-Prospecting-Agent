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
        "I was mapping the AI search landscape for {city} {search_context}s and noticed {company} isn't being recommended by ChatGPT or Perplexity. The underlying issue is technical: your site lacks the structured data (Schema.org) these models need to confidently cite your services and locations.",
        "When buyers ask AI assistants for '{search_context} near me', the models scan for structured data to decide who to recommend. Right now {company} has zero JSON-LD markup. This means your competitors are effectively capturing the AI citations you should be getting."
    ],
    "sitemap": [
        "I noticed {company} is missing from key AI search recommendations on platforms like ChatGPT and Perplexity. The root cause appears structural — without a complete sitemap.xml, AI crawlers can't fully index your practice areas or team bios to cite them.",
        "I was reviewing {company}'s AI search visibility and found that AI crawlers are struggling to index your site due to a missing or incomplete sitemap. When buyers research {search_context}s via LLMs, your firm's depth of expertise is largely invisible to the models."
    ],
    "faq": [
        "When buyers ask AI assistants about {search_context} services, the models heavily favor Q&A-formatted content. Because {company}'s site lacks a structured FAQ, competitors are currently controlling the AI-generated answers in your space.",
        "I noticed {company} doesn't have an FAQ section. In the era of AI search, that's a missed opportunity: LLMs like ChatGPT pull directly from Q&A formats to answer complex buyer questions. Without it, you're absent from those early-stage research conversations."
    ],
    "bot_blocked": [
        "I noticed {company} is actively blocking AI crawlers (like GPTBot) in your robots.txt. While this protects IP, it also completely removes your firm from the consideration set when executives use ChatGPT or Copilot to research {city} {search_context}s.",
        "Your site is currently blocking major AI crawlers. The trade-off for protecting your content is total invisibility in generative search. When a buyer asks Perplexity to recommend a {search_context}, {company} simply cannot be suggested."
    ],
    "thin_content": [
        "AI models (like ChatGPT and Perplexity) rely on content depth to establish authority. Right now, {company}'s homepage is too light on context (~{word_count} words) for these models to confidently recommend you over competitors for {vertical} queries.",
        "I was analyzing {company}'s AI visibility and noticed the homepage content is quite sparse. LLMs use depth as a proxy for expertise; without richer context about your services, the models will default to recommending your more verbose competitors."
    ],
    "heading": [
        "I ran an AI visibility parse on {company} and noticed the page heading structure is broken. Because AI models rely heavily on H1/H2 hierarchy to understand what a firm actually does, this technical gap is preventing LLMs from accurately citing your services."
    ],
    "social_meta": [
        "I noticed {company} is missing OpenGraph meta tags. While it seems minor, LLMs synthesize results for '{search_context} in {city}' by evaluating technical discipline and metadata. Missing tags act as a negative signal, pushing your firm lower in AI-generated recommendations."
    ],
    "llms.txt": [
        "I was looking at {company}'s site and noticed you haven't implemented an llms.txt file yet. It's still early, but forward-thinking {search_context}s are adding these to explicitly tell AI crawlers how to summarize their firm. It's a low-effort way to control your brand narrative in ChatGPT."
    ],
    "generic": [
        "I ran an AI visibility audit on {company} and found several infrastructure gaps preventing LLMs from understanding and recommending the firm. In a market where buyers are shifting from traditional search to AI assistants, this directly impacts top-of-funnel discovery.",
        "Most {search_context}s haven't optimized for AI search yet — {company} included. The window to establish a first-mover advantage is open, but it requires fixing the technical signals that AI crawlers rely on to cite your firm."
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
