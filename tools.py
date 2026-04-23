"""
Shared tool definitions and implementations for the research agents.

Each tool has:
  1. A JSON schema (TOOL_SCHEMAS) — tells Claude what the tool does and its parameters
  2. A Python implementation — the actual function that runs when Claude calls the tool
  3. A dispatch entry (TOOL_DISPATCH) — maps tool names to their implementations
"""

import json
import os
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

import geo_scoring

# ---------------------------------------------------------------------------
# Tool schemas (JSON Schema for Claude)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for information. Returns a list of search result "
                "snippets with titles and URLs. Use this to find relevant pages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": (
                "Fetch and extract the main text content from a web page URL. "
                "Use this after web_search to read a specific page in detail."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the page to fetch.",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_site_geo",
            "description": (
                "Analyze a website for GEO (Generative Engine Optimization) readiness. "
                "Returns a structured JSON score from 1-10 with per-dimension breakdowns, "
                "gaps, and actionable recommendations for improving LLM visibility."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The homepage URL of the website to analyze.",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_contacts",
            "description": (
                "Extract contact information from a website. Scans the homepage, "
                "contact page, about page, and team page for email addresses, "
                "phone numbers, and LinkedIn links."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The homepage URL of the website to extract contacts from.",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_discord_report",
            "description": (
                "Send a formatted report to a Discord channel via webhook. "
                "The message should use Discord-compatible markdown formatting. "
                "Requires DISCORD_WEBHOOK_URL environment variable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The report title (used as the header).",
                    },
                    "body": {
                        "type": "string",
                        "description": (
                            "The report body using Discord markdown formatting. "
                            "Use **bold**, *italic*, `code`, bullet points (•), "
                            "and dividers (---). Keep each section under 1900 chars."
                        ),
                    },
                },
                "required": ["title", "body"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (research-agent)"}
_TIMEOUT = 15


def _get(url: str, **kwargs) -> httpx.Response:
    """Convenience wrapper for httpx.get with default headers/timeout."""
    return httpx.get(
        url,
        headers=_HTTP_HEADERS,
        timeout=_TIMEOUT,
        follow_redirects=True,
        **kwargs,
    )


def _normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


# ---------------------------------------------------------------------------
# Tool: web_search
# ---------------------------------------------------------------------------

SEARCH_API = "https://html.duckduckgo.com/html/"


def web_search(query: str) -> str:
    """Search DuckDuckGo and return top results as a formatted string."""
    try:
        resp = _get(SEARCH_API, params={"q": query})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for i, r in enumerate(soup.select(".result"), 1):
            title_el = r.select_one(".result__title")
            snippet_el = r.select_one(".result__snippet")
            link_el = r.select_one(".result__url")
            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            link = link_el.get_text(strip=True) if link_el else ""
            if title:
                results.append(f"{i}. {title}\n   URL: {link}\n   {snippet}")
            if i >= 8:
                break
        return "\n\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search error: {e}"


# ---------------------------------------------------------------------------
# Tool: fetch_page
# ---------------------------------------------------------------------------


def fetch_page(url: str) -> str:
    """Fetch a page and extract its text content."""
    url = _normalize_url(url)
    try:
        resp = _get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if len(text) > 12_000:
            text = text[:12_000] + "\n\n[...truncated]"
        return text
    except Exception as e:
        return f"Fetch error: {e}"


# ---------------------------------------------------------------------------
# Tool: analyze_site_geo
# ---------------------------------------------------------------------------


def analyze_site_geo(url: str) -> str:
    """
    Analyze a website for GEO (Generative Engine Optimization) readiness
    and return a structured 1-10 LLM readiness score.

    Scoring dimensions (weighted):
      structured_data    (weight 3.0)  — JSON-LD / Schema.org markup
      ai_crawl_access    (weight 2.5)  — robots.txt AI bot permissions
      sitemap_quality    (weight 1.5)  — sitemap.xml presence & completeness
      content_depth      (weight 2.0)  — word count as proxy for content richness
      faq_content        (weight 2.0)  — FAQ sections and Q&A structure
      heading_structure  (weight 1.5)  — semantic heading hierarchy
      semantic_html      (weight 1.0)  — lists, tables, article tags
      social_meta        (weight 1.0)  — OpenGraph and Twitter Card tags

    Returns JSON with overall_score, grade, per-dimension scores, strengths,
    gaps, and actionable recommendations.
    """
    url = _normalize_url(url)
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    # 1. Fetch homepage and extract signals
    try:
        resp = _get(url)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return json.dumps({"error": f"Could not fetch {url}: {e}"})

    signals, _soup = geo_scoring.extract_page_signals(html)

    # 2. Fetch robots.txt + sitemap.xml (best-effort)
    blocked_ai_bots: list[str] = []
    try:
        robots_resp = _get(f"{base}/robots.txt")
        if robots_resp.status_code == 200:
            blocked_ai_bots = geo_scoring.parse_robots_for_ai_bots(robots_resp.text)
    except httpx.HTTPError:
        pass

    sitemap_present = False
    sitemap_url_count = 0
    sitemap_type = None
    try:
        sitemap_resp = _get(f"{base}/sitemap.xml")
        if sitemap_resp.status_code == 200:
            sitemap_present, sitemap_type, sitemap_url_count = (
                geo_scoring.parse_sitemap_preview(sitemap_resp.text)
            )
    except httpx.HTTPError:
        pass

    # 3. Score dimensions + weighted overall
    scores = geo_scoring.score_all_dimensions(
        signals, blocked_ai_bots, sitemap_present, sitemap_url_count
    )
    overall_score = geo_scoring.weighted_overall(scores)
    grade, readiness = geo_scoring.score_to_grade(overall_score)

    # 4. Strengths, gaps, and recommendations (presentation layer, caller-specific)
    strengths: list[str] = []
    gaps: list[str] = []
    recommendations: list[str] = []

    if scores["structured_data"] >= 6:
        strengths.append("Rich JSON-LD structured data present")
    elif signals.json_ld_count > 0:
        gaps.append("Only minimal JSON-LD; add comprehensive Schema.org markup")
        recommendations.append("Add Organization, LocalBusiness, or Service schema with full properties")
    else:
        gaps.append("No structured data (JSON-LD/Schema.org) — major blind spot for LLMs")
        recommendations.append("Implement JSON-LD structured data for relevant entity types")

    if scores["ai_crawl_access"] == 10:
        strengths.append("AI bots allowed in robots.txt")
    else:
        gaps.append(f"AI bots may be blocked in robots.txt: {', '.join(blocked_ai_bots) if blocked_ai_bots else 'check manually'}")
        recommendations.append("Audit robots.txt — ensure GPTBot, ClaudeBot, CCBot are not explicitly disallowed")

    if scores["sitemap_quality"] >= 7:
        strengths.append(f" sitemap.xml present ({sitemap_url_count} URLs)")
    else:
        gaps.append("No sitemap.xml or incomplete sitemap")
        recommendations.append("Submit a comprehensive sitemap.xml to Google Search Console and Bing Webmaster Tools")

    if scores["content_depth"] >= 7:
        strengths.append("Substantive homepage content")
    else:
        gaps.append(f"Thin homepage content (~{signals.word_count} words)")
        recommendations.append("Expand homepage copy to 1000+ words with distinct service/problem sections")

    if scores["faq_content"] >= 6:
        strengths.append("FAQ content detected")
    else:
        gaps.append("No FAQ section — LLMs lose Q&A-structured context")
        recommendations.append("Add a dedicated FAQ page with Q&A pairs covering common customer questions")

    if scores["heading_structure"] >= 6:
        strengths.append("Proper heading hierarchy (H1/H2/H3)")
    else:
        gaps.append("Poor or missing heading structure")
        recommendations.append("Use semantic H1 for page title, H2 for section headings, H3 for subsections")

    if scores["social_meta"] >= 5:
        strengths.append("Social meta tags present")
    else:
        gaps.append("Missing or sparse OpenGraph/Twitter Card meta tags")
        recommendations.append("Add OG title, description, image, and URL tags; add Twitter Card meta")

    # 5. Assemble response
    result = {
        "url": url,
        "overall_score": overall_score,
        "grade": grade,
        "llm_readiness": readiness,
        "word_count": signals.word_count,
        "dimensions": {
            "structured_data": {
                "score": scores["structured_data"],
                "max": 10,
                "detail": f"{signals.json_ld_count} JSON-LD blocks, {signals.microdata_count} microdata elements, types: {signals.json_ld_types}",
            },
            "ai_crawl_access": {
                "score": scores["ai_crawl_access"],
                "max": 10,
                "detail": "AI bots blocked" if blocked_ai_bots else "No AI bot blocks detected",
                "blocked_bots": blocked_ai_bots,
            },
            "sitemap_quality": {
                "score": scores["sitemap_quality"],
                "max": 10,
                "detail": f"{sitemap_type or 'absent'} sitemap, ~{sitemap_url_count} URLs indexed",
            },
            "content_depth": {
                "score": scores["content_depth"],
                "max": 10,
                "detail": f"~{signals.word_count:,} words on homepage",
            },
            "faq_content": {
                "score": scores["faq_content"],
                "max": 10,
                "detail": f"{signals.faq_keywords} FAQ keywords, {signals.faq_links} FAQ links, {signals.faq_schema_count} FAQ schema blocks",
            },
            "heading_structure": {
                "score": scores["heading_structure"],
                "max": 10,
                "detail": f"h1:{signals.h1_count}, h2:{signals.h2_count}, h3:{signals.h3_count}, total headings: {signals.heading_total}",
            },
            "semantic_html": {
                "score": scores["semantic_html"],
                "max": 10,
                "detail": f"{signals.list_count} lists, {signals.table_count} tables, {signals.article_count} article tags",
            },
            "social_meta": {
                "score": scores["social_meta"],
                "max": 10,
                "detail": f"{signals.og_count} OG tags, {signals.twitter_count} Twitter Card tags",
            },
        },
        "strengths": strengths if strengths else ["No significant strengths detected"],
        "gaps": gaps if gaps else ["Site appears well-optimized for LLM access"],
        "recommendations": recommendations if recommendations else ["Maintain current optimization level"],
    }

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool: extract_contacts
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)
_PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
)
_LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9\-_%]+"
)

# Common junk emails to filter out
_JUNK_EMAILS = {
    "example.com", "domain.com", "email.com", "yoursite.com",
    "sentry.io", "wixpress.com", "w3.org",
}


def _extract_from_soup(soup: BeautifulSoup) -> dict:
    """Extract emails, phones, and LinkedIn URLs from a BeautifulSoup object."""
    text = soup.get_text(separator=" ")
    html_str = str(soup)

    raw_emails = set(_EMAIL_RE.findall(text + " " + html_str))
    emails = {
        e for e in raw_emails
        if not any(junk in e for junk in _JUNK_EMAILS)
        and not e.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js"))
    }
    phones = set(_PHONE_RE.findall(text))
    linkedins = set(_LINKEDIN_RE.findall(html_str))

    return {
        "emails": sorted(emails),
        "phones": sorted(phones),
        "linkedin": sorted(linkedins),
    }


def extract_contacts(url: str) -> str:
    """
    Scan a website's homepage + common contact/about/team pages
    for email addresses, phone numbers, and LinkedIn links.
    """
    url = _normalize_url(url)
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    all_emails = set()
    all_phones = set()
    all_linkedins = set()
    pages_checked = []

    # Pages to check
    paths = [
        "/",
        "/contact",
        "/contact-us",
        "/about",
        "/about-us",
        "/team",
        "/our-team",
        "/people",
        "/leadership",
    ]

    for path in paths:
        page_url = urljoin(base, path)
        try:
            resp = _get(page_url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                found = _extract_from_soup(soup)
                all_emails.update(found["emails"])
                all_phones.update(found["phones"])
                all_linkedins.update(found["linkedin"])
                pages_checked.append(path)
        except Exception:
            continue

    result = [f"Scanned pages: {', '.join(pages_checked)}"]
    if all_emails:
        result.append(f"Emails: {', '.join(sorted(all_emails))}")
    else:
        result.append("Emails: None found")

    if all_phones:
        result.append(f"Phones: {', '.join(sorted(all_phones))}")
    else:
        result.append("Phones: None found")

    if all_linkedins:
        result.append(f"LinkedIn: {', '.join(sorted(all_linkedins))}")
    else:
        result.append("LinkedIn: None found")

    return "\n".join(result)


# ---------------------------------------------------------------------------
# Tool: send_discord_report
# ---------------------------------------------------------------------------


def send_discord_report(title: str, body: str) -> str:
    """Send a formatted report to Discord via webhook."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        return "Error: DISCORD_WEBHOOK_URL environment variable is not set."

    # Discord content limit is 2000 chars; stay well under it
    MAX_LEN = 1900

    # Build chunks
    chunks = []
    current = f"**{title}**\n\n"

    sections = [s.strip() for s in body.split("---") if s.strip()]

    for section in sections:
        candidate = current + section + "\n\n"
        if len(candidate) > MAX_LEN:
            # Flush current chunk
            if current.strip():
                chunks.append(current.strip())
            # Start new chunk with header context
            current = f"**(cont'd)**\n\n{section}\n\n"
        else:
            current = candidate

    if current.strip():
        chunks.append(current.strip())

    # Footer on last chunk
    if chunks:
        chunks[-1] += "\n\n🤖 *MadTech Growth GEO Agent*"

    sent = 0
    errors = []
    for chunk in chunks:
        payload = {
            "content": chunk,
            "username": "GEO Discovery Bot",
        }
        try:
            resp = httpx.post(
                webhook_url,
                json=payload,
                timeout=15,
            )
            if resp.status_code in (200, 204):
                sent += 1
            else:
                errors.append(f"{resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            errors.append(str(e))

    if errors:
        return f"Sent {sent}/{len(chunks)} chunks. Errors: {'; '.join(errors)}"
    return f"Report sent to Discord successfully ({sent} message(s))."


# ---------------------------------------------------------------------------
# Dispatch map
# ---------------------------------------------------------------------------

TOOL_DISPATCH = {
    "web_search": lambda args: web_search(args["query"]),
    "fetch_page": lambda args: fetch_page(args["url"]),
    "analyze_site_geo": lambda args: analyze_site_geo(args["url"]),
    "extract_contacts": lambda args: extract_contacts(args["url"]),
    "send_discord_report": lambda args: send_discord_report(args["title"], args["body"]),
}
