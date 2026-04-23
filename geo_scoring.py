"""
Pure GEO (LLM-readiness) scoring logic.

No network I/O lives here — callers fetch HTML, robots.txt, and sitemap.xml
however they like (sync or async) and pass the raw text in. That keeps this
module trivially testable and usable from both the sync tools.analyze_site_geo
entry point and the async geo_scanner.analyze_one batch path.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

AI_BOT_NAMES = [
    "gptbot", "chatgpt-user", "google-extended", "ccbot",
    "anthropic-ai", "claudebot", "bytespider", "perplexitybot",
]
CRITICAL_AI_BOTS = {"gptbot", "claudebot", "perplexitybot"}

FAQ_KEYWORDS = ["faq", "frequently asked", "questions", "q&a", "ask us"]
FAQ_LINK_RE = re.compile(r"(?i)faq|frequently asked|questions")
FAQ_SCHEMA_TYPES = {"FAQPage", "HowTo", "QAPage"}

NOISE_TAGS = ["script", "style", "nav", "header", "footer", "aside"]

OG_META_RE = re.compile(r"^og:")
TWITTER_META_RE = re.compile(r"^twitter:")

DIMENSION_WEIGHTS = {
    "structured_data": 3.0,
    "ai_crawl_access": 2.5,
    "sitemap_quality": 1.5,
    "content_depth": 2.0,
    "faq_content": 2.0,
    "heading_structure": 1.5,
    "semantic_html": 1.0,
    "social_meta": 1.0,
}


@dataclass
class PageSignals:
    word_count: int = 0
    json_ld_count: int = 0
    json_ld_types: list = field(default_factory=list)
    microdata_count: int = 0
    og_count: int = 0
    twitter_count: int = 0
    h1_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    heading_total: int = 0
    list_count: int = 0
    table_count: int = 0
    article_count: int = 0
    faq_keywords: int = 0
    faq_links: int = 0
    faq_schema_count: int = 0


def extract_page_signals(html: str) -> tuple[PageSignals, BeautifulSoup]:
    """Parse HTML once and compute every page-level signal used for scoring.

    Returns both the signal bundle and the cleaned soup (noise tags already
    decomposed) so callers can reuse it for anything else they need.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Collect JSON-LD BEFORE decomposing <script> — otherwise we'd lose it.
    json_ld_tags = soup.find_all("script", type="application/ld+json")
    json_ld_count = len(json_ld_tags)
    json_ld_types: list[str] = []
    for tag in json_ld_tags:
        try:
            data = json.loads(tag.string)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            t = data.get("@type", "")
            if isinstance(t, list):
                json_ld_types.extend(t)
            else:
                json_ld_types.append(t)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    t = item.get("@type", "")
                    if isinstance(t, list):
                        json_ld_types.extend(t)
                    else:
                        json_ld_types.append(t)

    for tag in soup(NOISE_TAGS):
        tag.decompose()
    clean_text = soup.get_text(separator=" ", strip=True)
    text_lower = clean_text.lower()

    signals = PageSignals(
        word_count=len(clean_text.split()),
        json_ld_count=json_ld_count,
        json_ld_types=json_ld_types,
        microdata_count=len(soup.find_all(attrs={"itemtype": True})),
        og_count=len(soup.find_all("meta", attrs={"property": OG_META_RE})),
        twitter_count=len(soup.find_all("meta", attrs={"name": TWITTER_META_RE})),
        h1_count=len(soup.find_all("h1")),
        h2_count=len(soup.find_all("h2")),
        h3_count=len(soup.find_all("h3")),
        heading_total=sum(len(soup.find_all(f"h{i}")) for i in range(1, 7)),
        list_count=len(soup.find_all(["ul", "ol"])),
        table_count=len(soup.find_all("table")),
        article_count=len(soup.find_all("article")),
        faq_keywords=sum(1 for kw in FAQ_KEYWORDS if kw in text_lower),
        faq_links=len(soup.find_all("a", string=FAQ_LINK_RE)),
        faq_schema_count=sum(1 for t in json_ld_types if t in FAQ_SCHEMA_TYPES),
    )
    return signals, soup


def parse_robots_for_ai_bots(robots_text: str) -> list[str]:
    """Return AI bot names that are *mentioned* in robots.txt (case-insensitive).

    Note: this matches on name appearance, not on a proper Disallow parse —
    kept for behavioral parity with the prior inline code.
    """
    lower = robots_text.lower()
    return [b for b in AI_BOT_NAMES if b in lower]


def parse_sitemap_preview(sm_text: str) -> tuple[bool, Optional[str], int]:
    """Return (present, type, url_count) from the first ~2KB of a sitemap."""
    preview = sm_text[:2000]
    if "<urlset" in preview or "<sitemapindex" in preview:
        sm_type = "index" if "<sitemapindex" in preview else "standard"
        return True, sm_type, preview.count("<url>")
    return False, None, 0


# --- per-dimension scorers (all 0-10) ---------------------------------------


def score_structured_data(json_ld_count: int, json_ld_types: list, microdata_count: int) -> int:
    if json_ld_count == 0 and microdata_count == 0:
        return 0
    if json_ld_count >= 2 and len(set(json_ld_types)) >= 2:
        return 10
    if json_ld_count >= 1 or microdata_count >= 3:
        return 6
    return 3


def score_ai_crawl(blocked_ai_bots: list[str]) -> int:
    if not blocked_ai_bots:
        return 10
    if any(b in blocked_ai_bots for b in CRITICAL_AI_BOTS):
        return 1
    return 4


def score_sitemap(sitemap_present: bool, sitemap_url_count: int) -> int:
    if not sitemap_present:
        return 2
    if sitemap_url_count < 10:
        return 5
    if sitemap_url_count < 50:
        return 7
    return 10


def score_content_depth(word_count: int) -> int:
    if word_count < 100:
        return 1
    if word_count < 300:
        return 3
    if word_count < 600:
        return 5
    if word_count < 1000:
        return 7
    if word_count < 2000:
        return 8
    return 10


def score_faq(faq_schema_count: int, faq_keywords: int, faq_links: int) -> int:
    if faq_schema_count > 0:
        return 10
    if faq_keywords >= 3 and faq_links >= 1:
        return 7
    if faq_keywords >= 1 or faq_links >= 1:
        return 4
    return 1


def score_headings(heading_total: int, h1_count: int, h2_count: int) -> int:
    if heading_total == 0:
        return 0
    if h1_count >= 1 and h2_count >= 2:
        return 9
    if h1_count >= 1 and h2_count >= 1:
        return 6
    if heading_total >= 3:
        return 4
    return 2


def score_semantic_html(list_count: int, table_count: int, article_count: int) -> int:
    return min(10, (list_count // 2) + (table_count // 2) + (article_count // 2))


def score_social_meta(og_count: int, twitter_count: int) -> int:
    if og_count >= 3 and twitter_count >= 2:
        return 9
    if og_count >= 1 or twitter_count >= 1:
        return 5
    return 2


def score_all_dimensions(
    signals: PageSignals,
    blocked_ai_bots: list[str],
    sitemap_present: bool,
    sitemap_url_count: int,
) -> dict[str, int]:
    """Convenience: run every base-dimension scorer against a signal bundle."""
    return {
        "structured_data": score_structured_data(
            signals.json_ld_count, signals.json_ld_types, signals.microdata_count
        ),
        "ai_crawl_access": score_ai_crawl(blocked_ai_bots),
        "sitemap_quality": score_sitemap(sitemap_present, sitemap_url_count),
        "content_depth": score_content_depth(signals.word_count),
        "faq_content": score_faq(
            signals.faq_schema_count, signals.faq_keywords, signals.faq_links
        ),
        "heading_structure": score_headings(
            signals.heading_total, signals.h1_count, signals.h2_count
        ),
        "semantic_html": score_semantic_html(
            signals.list_count, signals.table_count, signals.article_count
        ),
        "social_meta": score_social_meta(signals.og_count, signals.twitter_count),
    }


def weighted_overall(
    scores: dict[str, float],
    weights: Optional[dict[str, float]] = None,
) -> float:
    """Weighted mean of dimension scores, rounded to 1 decimal.

    Only keys present in both `scores` and `weights` contribute — callers can
    safely pass extended scores (e.g. with content_citability) alongside the
    extended weights dict.
    """
    weights = weights or DIMENSION_WEIGHTS
    total_w = sum(weights[k] for k in scores if k in weights)
    if total_w == 0:
        return 0.0
    raw = sum(scores[k] * weights[k] for k in scores if k in weights)
    return round(raw / total_w, 1)


def score_to_grade(overall: float) -> tuple[str, str]:
    """Map a 0-10 overall score to (letter_grade, readiness_label)."""
    if overall >= 8.5:
        return "A", "High"
    if overall >= 7.0:
        return "B", "Medium-High"
    if overall >= 5.0:
        return "C", "Medium"
    if overall >= 3.0:
        return "D", "Low"
    return "F", "Very Low"
