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

# ── Hook templates by gap category ────────────────────────────────────────────
# Each hook references a specific GEO gap.  2-3 variants per category so we
# can randomize and avoid robotic repetition.
HOOKS = {
    "schema": [
        "I ran a quick audit of {company}'s AI visibility and noticed the site has zero structured data markup. LLMs typically skip sites they can't parse — which means {company} may be invisible in AI search results despite the brand recognition.",
        "I checked how AI agents see {company}'s site and found no Schema.org / JSON-LD markup. That makes it hard for LLMs to understand services, practice areas, or geography — three things buyers ask about.",
    ],
    "sitemap": [
        "{company}'s site doesn't appear to have a complete sitemap.xml. Without one, AI crawlers struggle to discover and index content depth — especially important for a firm with {company}'s breadth.",
        "I noticed {company}'s sitemap is either missing or thin. For a firm of your size, that's a signal AI crawlers use to deprioritize you in generated answers.",
    ],
    "faq": [
        "{company} has no FAQ section. That's a problem because LLMs prioritize Q&A content when generating answers to 'best [service] in [city]' queries — exactly the queries your clients are typing.",
        "There's no FAQ content on {company}'s site. Competitors with structured Q&A are more likely to be cited by AI agents answering prospect questions.",
    ],
    "bot_blocked": [
        "{company} is blocking AI crawlers in robots.txt. I get the instinct, but it also removes you from Perplexity, ChatGPT search, and every emerging AI search engine.",
        "I saw that {company} blocks GPTBot and ClaudeBot. That protects content but also guarantees zero visibility in AI-driven search — a fast-growing traffic source for professional services.",
    ],
    "thin_content": [
        "{company}'s homepage is light on content — only ~{word_count} words. LLMs reward depth; a thin page reduces the chance you'll be quoted or recommended.",
        "The homepage copy is only ~{word_count} words. For LLMs trying to understand what {company} does, that's not enough signal to rank you above competitors with richer pages.",
    ],
    "heading": [
        "{company}'s heading structure needs work. Missing or duplicated H1s make it hard for AI to understand page hierarchy — and that's how it decides priority in answers.",
    ],
    "social_meta": [
        "No OpenGraph tags on {company}'s site. That hurts sharing, but more importantly it signals to AI that page context is weak.",
    ],
    "llms_txt": [
        "{company} doesn't have an llms.txt file. It's still early, but firms that add one now are building a moat before it becomes standard.",
    ],
    "generic": [
        "I ran an AI visibility audit on {company} and found several gaps that are making it harder for LLMs to understand and recommend the firm.",
        "Most professional services firms haven't optimized for AI search yet — {company} included. The good news is that the window to lead is still open.",
    ],
}

# ── CTA variants ──────────────────────────────────────────────────────────────
CTAS = [
    "I built a free 8-dimension GEO Snapshot that shows exactly where {company} stands and what to fix first. Happy to send it over — no pitch, just signal.",
    "I put together a complimentary GEO Snapshot for {company} — 8 dimensions, scored, with a prioritized fix list. Want me to send it?",
    "I can send a free GEO Snapshot that breaks down {company}'s AI visibility across all 8 dimensions. Takes two minutes to read, gives you a 90-day roadmap. Interested?",
]

# ── Signatures ────────────────────────────────────────────────────────────────
SIG = """Scott Krauss
Founder, MadTech Growth
Agentic Commerce Advisory for Professional Services
hello@madtechgrowth.com | madtechgrowth.com
"""

SIG_HTML = f"""<div style="margin-top:32px;padding-top:20px;border-top:1px solid {BRAND['line']};">
  <p style="margin:0;font-size:14px;color:{BRAND['ink']};font-weight:600;">Scott Krauss</p>
  <p style="margin:4px 0 0;font-size:13px;color:{BRAND['muted']};">Founder, MadTech Growth</p>
  <p style="margin:2px 0 0;font-size:13px;color:{BRAND['muted']};">Agentic Commerce Advisory for Professional Services</p>
  <p style="margin:8px 0 0;font-size:13px;"><a href="mailto:hello@madtechgrowth.com" style="color:{BRAND['sage_deep']};text-decoration:none;">hello@madtechgrowth.com</a>&nbsp;&nbsp;|&nbsp;&nbsp;<a href="https://madtechgrowth.com" style="color:{BRAND['sage_deep']};text-decoration:none;">madtechgrowth.com</a></p>
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


def _build_hook(gaps: list[str], company: str, word_count: int = 0) -> str:
    """Pick the most specific hook from the first 2 gaps."""
    for gap in gaps[:2]:
        key = _map_gap_to_key(gap)
        templates = HOOKS.get(key, HOOKS["generic"])
        tmpl = random.choice(templates)
        try:
            return tmpl.format(company=company, word_count=word_count)
        except KeyError:
            continue
    return random.choice(HOOKS["generic"]).format(company=company)


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

    # Hook
    word_count = prospect.get("word_count", 0)
    hook = _build_hook(gaps, company, word_count)
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
        <p style="font-size:11px;color:{BRAND['muted']};margin:0;line-height:1.6;">MadTech Growth · New York, NY<br/>You're receiving this because your firm matches our target profile for AI visibility optimization.</p>
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
