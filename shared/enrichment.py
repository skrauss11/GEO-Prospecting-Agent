"""
Lead enrichment orchestration for MadTech Growth.

Takes a Prospect, calls Hunter.io, picks the best marketing/growth contact,
and mutates the Prospect in place.  No email verification — we trust
Hunter's confidence at low volume.

Usage:
    from shared.enrichment import enrich_prospect
    enrich_prospect(prospect)  # mutates prospect.emails, prospect.linkedin
"""

from __future__ import annotations

import re
from typing import Optional

from shared.base import Prospect
from shared.hunter_client import HunterClient, HunterContact

# ── Role priority tiers ───────────────────────────────────────────
# Tier 1 — Marketing / Growth / Revenue (our ideal buyer)
_TIER_1_KEYWORDS = [
    "cmo",
    "chief marketing",
    "chief growth",
    "vp marketing",
    "vp growth",
    "head of marketing",
    "head of growth",
    "director of marketing",
    "director of growth",
    "marketing director",
    "growth director",
    "marketing lead",
    "growth lead",
    "marketing manager",
    "growth manager",
    "demand gen",
    "demand generation",
    "performance marketing",
    "seo",
    "content marketing",
    "brand",
    "revenue",
    "sales",
    "business development",
]

# Tier 2 — CEO / Founder (fallback, final resort)
_TIER_2_KEYWORDS = [
    "ceo",
    "chief executive",
    "founder",
    "co-founder",
    "cofounder",
    "president",
    "managing director",
]

# Explicitly excluded — never pick these
_EXCLUDE_KEYWORDS = [
    "cfo",
    "chief financial",
    "cto",
    "chief technology",
    "chief technical",
    "cio",
    "chief information",
    "chief legal",
    "general counsel",
    "hr",
    "human resources",
    "recruiting",
    "talent",
    "support",
    "customer service",
    "help desk",
    "admin",
    "assistant",
    "intern",
    "coordinator",
]

_MIN_CONFIDENCE = 60   # Below this we ignore the contact entirely


def _score_contact(contact: HunterContact) -> tuple[int, int]:
    """
    Score a contact for selection priority.

    Returns:
        (tier, confidence) where lower tier = higher priority.
        Tier 1 (marketing/growth) > Tier 2 (CEO) > Tier 999 (excluded).
    """
    if not contact.is_personal:
        return (999, 0)

    if contact.confidence < _MIN_CONFIDENCE:
        return (999, 0)

    pos = (contact.position or "").lower()
    dept = (contact.department or "").lower()
    full = f"{pos} {dept}"

    # Explicit exclusions
    for kw in _EXCLUDE_KEYWORDS:
        if kw in full:
            return (999, 0)

    # Tier 1: marketing / growth / revenue
    for kw in _TIER_1_KEYWORDS:
        if kw in full:
            return (1, contact.confidence)

    # Tier 2: CEO / founder
    for kw in _TIER_2_KEYWORDS:
        if kw in full:
            return (2, contact.confidence)

    # Everything else is excluded (COO, COO-adjacent, unclear titles)
    return (999, 0)


def _extract_domain(url: str) -> str:
    """Bare domain without scheme or www."""
    from urllib.parse import urlparse
    if "://" not in url:
        url = "https://" + url
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def pick_best_contact(contacts: list[HunterContact]) -> Optional[HunterContact]:
    """
    Pick the highest-priority contact from a Hunter result.

    Priority:
        1. Marketing / Growth / Revenue titles (CMO, VP Marketing, Head of Growth, etc.)
        2. CEO / Founder / President
        3. Skip everything else (CFO, CTO, COO, support, etc.)
    """
    scored = []
    for c in contacts:
        tier, conf = _score_contact(c)
        if tier < 999:
            scored.append((tier, conf, c))

    if not scored:
        return None

    # Sort by tier ascending, then confidence descending
    scored.sort(key=lambda t: (t[0], -t[1]))
    return scored[0][2]


def enrich_prospect(
    prospect: Prospect,
    client: Optional[HunterClient] = None,
) -> bool:
    """
    Enrich a single Prospect with Hunter.io contacts.

    Mutates prospect.emails, prospect.linkedin, and prospect._raw_analysis.
    Returns True if a suitable contact was found, False otherwise.
    """
    domain = _extract_domain(prospect.url)
    if not domain:
        return False

    own_client = client is None
    if own_client:
        client = HunterClient()

    try:
        result = client.domain_search(domain, limit=10)
    except Exception as e:
        print(f"    [enrich] Hunter error for {domain}: {e}")
        if own_client:
            client.close()
        return False
    finally:
        if own_client:
            client.close()

    best = pick_best_contact(result.contacts)
    if not best:
        print(f"    [enrich] No suitable marketing/growth contact for {domain}")
        return False

    # Mutate the prospect
    prospect.emails = [best.email]
    if best.linkedin:
        prospect.linkedin = best.linkedin

    # Store full Hunter payload for debugging / template personalisation
    prospect._raw_analysis["hunter"] = {
        "domain": result.domain,
        "pattern": result.pattern,
        "contacts_found": len(result.contacts),
        "selected": {
            "email": best.email,
            "name": best.full_name,
            "position": best.position,
            "confidence": best.confidence,
            "linkedin": best.linkedin,
        },
        "all_contacts": [
            {
                "email": c.email,
                "name": c.full_name,
                "position": c.position,
                "confidence": c.confidence,
                "type": c.email_type,
                "status": c.verification_status,
            }
            for c in result.contacts
        ],
        "credits_used": result.credits_used,
    }

    print(
        f"    [enrich] ✓ {best.full_name} ({best.position}) @ {domain} "
        f"[{best.confidence}% confidence, tier {_score_contact(best)[0]}]"
    )
    return True


def enrich_prospects(prospects: list[Prospect]) -> list[Prospect]:
    """Bulk enrich a list of prospects.  Returns the enriched list."""
    with HunterClient() as client:
        for p in prospects:
            enrich_prospect(p, client=client)
    return prospects
