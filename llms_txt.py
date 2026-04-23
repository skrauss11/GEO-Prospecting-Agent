#!/usr/bin/env python3
"""
llms.txt Analyzer — Checks for llms.txt file and validates its format.
Ported from geo-seo-claude (zubair-trabzada) for use in geo_scanner.py.

llms.txt is an emerging standard (Jeremy Howard, Sep 2024) that helps AI systems
understand website structure — analogous to robots.txt but for AI crawlers.
"""

import re
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None


def analyze_llms_txt(base: str) -> dict:
    """
    Fetch and analyze the llms.txt file at a domain root.
    Returns a full analysis dict.
    """
    llms_url = f"{base.rstrip('/')}/llms.txt"

    try:
        resp = httpx.get(llms_url, headers=_headers(), timeout=15, follow_redirects=True)
        status = resp.status_code
    except Exception:
        status = 0

    result = {
        "url": llms_url,
        "http_status": status,
        "exists": status == 200,
        "format_valid": False,
        "has_title": False,
        "has_description": False,
        "has_sections": False,
        "has_links": False,
        "section_count": 0,
        "link_count": 0,
        "content": "",
        "issues": [],
        "suggestions": [],
        "full_version_exists": False,
        "score": 0,
        "score_label": "",
    }

    if status == 0:
        result["issues"].append("Network error fetching llms.txt")
        result["suggestions"].append("Ensure the domain is accessible")
    elif status == 404:
        result["issues"].append("llms.txt does not exist (404)")
        result["suggestions"].append(
            "Generate llms.txt — a concise guide to your most important pages "
            "(helps AI understand your site structure)"
        )
    elif status == 403:
        result["issues"].append("llms.txt exists but access is blocked (403)")
        result["suggestions"].append("Check if robots.txt or server config blocks AI crawlers")
    elif status == 200:
        result["content"] = resp.text[:5000]
        _validate_format(result)

        # Check for full version
        full_url = f"{base.rstrip('/')}/llms-full.txt"
        try:
            full_resp = httpx.get(full_url, headers=_headers(), timeout=10)
            result["full_version_exists"] = full_resp.status_code == 200
        except Exception:
            pass

    # Calculate score
    result["score"] = _calculate_score(result)
    result["score_label"] = _score_label(result["score"])

    return result


def _headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }


def _validate_format(result: dict) -> None:
    """Validate llms.txt format and populate validation fields."""
    content = result["content"]
    lines = content.split("\n")

    # Check title (# Site Name)
    if lines and lines[0].startswith("# "):
        result["has_title"] = True

    # Check description (> brief description)
    for line in lines[:5]:
        if line.startswith("> "):
            result["has_description"] = True
            if len(line) > 200:
                result["issues"].append("Description too long (should be under 200 chars)")
            break

    # Check sections (## Section Name)
    section_lines = [l for l in lines if re.match(r"^##\s+\S", l)]
    result["section_count"] = len(section_lines)
    result["has_sections"] = len(section_lines) > 0

    # Check links (- [Page Title](url))
    link_pattern = re.compile(r"-\s+\[.+?\]\(.+?\)")
    links = link_pattern.findall(content)
    result["link_count"] = len(links)
    result["has_links"] = len(links) >= 5

    # Build issues and suggestions
    if not result["has_title"]:
        result["issues"].append("Missing title (should start with '# Site Name')")

    if not result["has_description"]:
        result["issues"].append("Missing description (use '> Brief description' after title)")

    if not result["has_sections"]:
        result["issues"].append("No sections found (use '## Section Name' to organize pages)")
        result["suggestions"].append("Add sections like ## Docs, ## About, ## Contact")
    else:
        if result["section_count"] < 2:
            result["suggestions"].append("Consider adding more sections (aim for 3-6)")

    if not result["has_links"]:
        result["issues"].append("No page links found (use '- [Page Title](url)')")
    else:
        if result["link_count"] < 5:
            result["suggestions"].append("Add more key pages (aim for 10-20 entries)")
        if result["link_count"] > 0:
            # Check for absolute URLs
            broken_urls = []
            for line in content.split("\n"):
                match = re.search(r"\((https?://[^\)]+)\)", line)
                if match:
                    url = match.group(1)
                    if not url.startswith("http"):
                        broken_urls.append(url)
            if broken_urls:
                result["issues"].append(f"Some URLs may not be absolute: {broken_urls[:3]}")

    if not result["has_description"]:
        result["suggestions"].append(
            "Add a blockquote description after the title: '> One-sentence site description'"
        )

    # Check for key sections
    content_lower = content.lower()
    if "contact" not in content_lower and "## contact" not in content_lower:
        result["suggestions"].append("Consider adding a ## Contact section with email/location")
    if "key facts" not in content_lower and "## key facts" not in content_lower:
        result["suggestions"].append("Consider adding a ## Key Facts section with company info")


def _calculate_score(result: dict) -> float:
    """
    Calculate llms.txt readiness score (0-10).
    Based on: existence, format validity, link/section count.
    """
    if not result["exists"]:
        if result.get("http_status") == 403:
            return 2.0
        return 1.0

    score = 5.0  # Base: file exists

    if result["has_title"]:
        score += 1.0
    if result["has_description"]:
        score += 1.0
    if result["has_sections"]:
        score += 1.5
    if result["has_links"]:
        link_bonus = min(result["link_count"] * 0.1, 1.5)
        score += link_bonus

    # Full version bonus
    if result.get("full_version_exists"):
        score += 0.5

    return round(min(score, 10.0), 1)


def _score_label(score: float) -> str:
    if score >= 9:
        return "Excellent"
    elif score >= 7:
        return "Good"
    elif score >= 5:
        return "Fair"
    elif score >= 3:
        return "Poor"
    else:
        return "Missing/Critical"


def llms_result_to_dimension(result: dict) -> dict:
    """
    Convert llms.txt analysis result into a geo_scanner dimension format (score 0-10).
    """
    score = result.get("score", 0)
    issues = result.get("issues", [])
    suggestions = result.get("suggestions", [])

    detail_parts = [
        f"{result.get('link_count', 0)} links",
        f"{result.get('section_count', 0)} sections",
    ]
    if result.get("full_version_exists"):
        detail_parts.append("llms-full.txt present")

    detail = ", ".join(detail_parts)
    if issues:
        detail += f" | Issues: {'; '.join(issues[:2])}"

    return {"score": score, "detail": detail}


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python llms_txt.py <base_url>")
        sys.exit(1)

    base = sys.argv[1]
    result = analyze_llms_txt(base)
    print(json.dumps(result, indent=2, default=str))
