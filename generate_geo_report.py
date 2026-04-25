#!/usr/bin/env python3
"""
generate_geo_report.py — Single-URL GEO Snapshot Report Generator

Takes any website URL, runs the full GEO scan, and outputs a branded
markdown report (.md) to the proposals/ directory.

Optionally auto-generates the PDF too.

Usage:
    python3 generate_geo_report.py https://example.com
    python3 generate_geo_report.py https://example.com --pdf
    python3 generate_geo_report.py https://example.com --output ~/Desktop

Output:
    proposals/geo_snapshot_<domain>_<date>.md
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from geo_scanner import scan_site_sync


# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
PROPOSALS_DIR = SCRIPT_DIR / "proposals"
PROPOSALS_DIR.mkdir(exist_ok=True)


# ── Dimension label mapping ──────────────────────────────────────────────────
DIMENSION_LABELS = {
    "structured_data": "Structured Data",
    "ai_crawl_access": "AI Crawl Access",
    "sitemap_quality": "Sitemap Quality",
    "content_depth": "Content Depth",
    "faq_content": "FAQ Content",
    "heading_structure": "Heading Structure",
    "semantic_html": "Semantic HTML",
    "social_meta": "Social Meta",
    "content_citability": "Content Citability",
    "llms_txt": "llms.txt",
}

DIMENSION_ORDER = [
    "ai_crawl_access",
    "social_meta",
    "heading_structure",
    "structured_data",
    "content_depth",
    "sitemap_quality",
    "semantic_html",
    "faq_content",
    "content_citability",
    "llms_txt",
]


def score_emoji(score: float) -> str:
    if score >= 7:
        return "✅"
    elif score >= 4:
        return "⚠️"
    else:
        return "🔴"


def readiness_emoji(readiness: str) -> str:
    lower = (readiness or "").lower()
    if "high" in lower:
        return "🟢"
    elif "medium" in lower:
        return "🟡"
    elif "low" in lower:
        return "🔴"
    return "⚪"


def extract_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "").replace(".", "_")
    return domain


def company_from_url(url: str) -> str:
    """Best-effort company name from URL domain."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    parts = domain.split(".")
    # e.g. "anchin.com" -> "Anchin"
    name = parts[0].replace("-", " ").replace("_", " ").title()
    # Basic heuristic: split camelCase-ish joins (e.g. "madtechgrowth" -> "Madtechgrowth" still, but
    # common patterns like "law", "group", "llp" can be spaced)
    # Keep it simple — user can override with --company
    return name


def build_markdown(result: dict) -> str:
    """Format a geo_scanner result dict into the branded snapshot markdown."""
    url = result["url"]
    company = result.get("company") or company_from_url(url)
    overall = result.get("overall_score", 0)
    grade = result.get("grade", "?")
    readiness = result.get("llm_readiness", "Unknown")
    word_count = result.get("word_count", 0)
    dims = result.get("dimensions", {})
    gaps = result.get("gaps", [])
    recs = result.get("recommendations", [])
    today = date.today().strftime("%B %d, %Y")

    # ── Dimension rows ──
    dim_rows = []
    for key in DIMENSION_ORDER:
        if key not in dims:
            continue
        d = dims[key]
        score = d.get("score", 0)
        detail = d.get("detail", "").replace("|", "\|")
        emoji = score_emoji(score)
        label = DIMENSION_LABELS.get(key, key.replace("_", " ").title())
        dim_rows.append(
            f"| **{label}** | {score}/10 | {emoji} | {detail} |"
        )

    # ── Gaps / Recommendations ──
    gap_sections = []
    for i, (gap, rec) in enumerate(zip(gaps, recs), 1):
        gap_sections.append(
            f"### {i}. **{gap}**\n"
            f"- **Fix:** {rec}\n"
        )

    gaps_md = "\n".join(gap_sections) if gap_sections else "_No critical gaps detected._\n"

    # ── Action plan (derived from gaps) ──
    action_items = []
    for i, rec in enumerate(recs[:6], 1):
        action_items.append(f"- [ ] {rec}")
    actions_md = "\n".join(action_items) if action_items else "_No specific actions recommended._\n"

    # ── Summary paragraph ──
    if overall >= 7:
        summary = (
            f"{company} demonstrates **strong AI visibility**. "
            f"Their site is well-structured for LLM crawlers with solid schema markup, "
            f"content depth, and technical accessibility. Minor optimizations can push them into the top tier."
        )
    elif overall >= 5:
        summary = (
            f"{company} has **moderate AI visibility**. "
            f"They've implemented some foundational GEO elements but have clear gaps in "
            f"{' and '.join(gaps[:2]).lower() if len(gaps) >= 2 else (gaps[0].lower() if gaps else 'technical infrastructure')}. "
            f"Targeted improvements can significantly improve LLM citation rates."
        )
    else:
        summary = (
            f"{company} has **limited AI visibility**. "
            f"Their site lacks critical infrastructure that LLMs rely on for understanding and recommending businesses. "
            f"A structured GEO audit and implementation roadmap is strongly recommended."
        )

    md = f"""# GEO Visibility Snapshot
## {company}
**URL:** {url}  
**Date:** {today}  
**Prepared by:** MadTech Growth

---

## Executive Summary

| Metric | Score | Grade |
|--------|-------|-------|
| **Overall GEO Readiness** | {overall}/10 | {grade} |
| **LLM Visibility** | {readiness} | {readiness_emoji(readiness)} |

{summary}

---

## Dimension Breakdown

| Dimension | Score | Status | Detail |
|-----------|-------|--------|--------|
{chr(10).join(dim_rows)}

---

## Critical Gaps (Revenue Impact)

{gaps_md}

---

## Recommended Action Plan

{actions_md}

---

*This snapshot was generated by the MadTech Growth GEO Analysis Engine. For a complete audit and implementation roadmap, contact: scott@madtechgrowth.com*
"""
    return md


def main():
    parser = argparse.ArgumentParser(
        description="Generate a GEO snapshot markdown report from a URL",
    )
    parser.add_argument("url", help="Website URL to analyze (e.g. https://example.com)")
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=str(PROPOSALS_DIR),
        help=f"Output directory for the .md file (default: {PROPOSALS_DIR})",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Also generate a PDF from the markdown report",
    )
    parser.add_argument(
        "--company",
        type=str,
        default="",
        help="Override company name (auto-detected from URL if omitted)",
    )
    args = parser.parse_args()

    # Normalize URL
    url = args.url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    domain = extract_domain(url)
    today_iso = date.today().isoformat()
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    md_filename = f"geo_snapshot_{domain}_{today_iso}.md"
    md_path = out_dir / md_filename

    print(f"🔍 Scanning {url}...")
    result = scan_site_sync(url)

    if result.get("error"):
        print(f"✗ Scan failed: {result['error']}", file=sys.stderr)
        sys.exit(1)

    # Override company name if provided
    if args.company:
        result["company"] = args.company

    print(f"✓ Score: {result.get('overall_score', 0)}/10 (Grade {result.get('grade', '?')})")
    print(f"✓ Gaps found: {len(result.get('gaps', []))}")

    md = build_markdown(result)
    md_path.write_text(md, encoding="utf-8")
    print(f"✓ Markdown saved: {md_path}")

    # Optional PDF generation
    if args.pdf:
        try:
            from generate_pdf_from_md import main as pdf_main
            import sys as _sys

            # Temporarily swap sys.argv so the PDF generator gets the right args
            old_argv = _sys.argv
            _sys.argv = ["generate_pdf_from_md.py", str(md_path), "--output", str(out_dir)]
            pdf_main()
            _sys.argv = old_argv

            pdf_name = md_filename.replace(".md", ".pdf")
            print(f"✓ PDF saved: {out_dir / pdf_name}")
        except Exception as e:
            print(f"⚠️ PDF generation failed: {e}", file=sys.stderr)

    print(f"\nDone. Report: {md_path}")


if __name__ == "__main__":
    main()
