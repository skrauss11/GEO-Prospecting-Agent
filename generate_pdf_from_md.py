#!/usr/bin/env python3
"""
Generate a branded PDF snapshot from a markdown report.

Usage:
    python3 generate_pdf_from_md.py proposals/geo_snapshot_anchin_2026-04-23.md
    python3 generate_pdf_from_md.py proposals/geo_snapshot_anchin_2026-04-23.md --output ~/Desktop

Output:
    PDF file in the same directory as the markdown (or --output dir)
"""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
from shared.snapshot_pdf import generate_snapshot_pdf


def parse_markdown_snapshot(md_path: Path) -> dict:
    """Parse a markdown snapshot report into the JSON format expected by the PDF generator."""
    text = md_path.read_text()
    lines = text.split("\n")

    result = {
        "url": "",
        "company": "",
        "vertical": "default",
        "notes": "",
        "overall_score": 0.0,
        "grade": "N/A",
        "llm_readiness": "Unknown",
        "word_count": 0,
        "error": None,
        "dimensions": {},
        "gaps": [],
        "recommendations": []
    }

    # Extract company name from first H2
    title_match = re.search(r'##\s+(.+?)(?:\n|$)', text)
    if title_match:
        result["company"] = title_match.group(1).strip()

    # Extract URL
    url_match = re.search(r'\*\*URL:\*\*\s*(https?://[^\s]+)', text)
    if url_match:
        result["url"] = url_match.group(1).strip()

    # Extract date
    date_match = re.search(r'\*\*Date:\*\*\s*(.+?)(?:\n|$)', text)
    if date_match:
        result["notes"] = date_match.group(1).strip()

    # Extract overall score and grade from Executive Summary table
    score_match = re.search(r'\*\*Overall GEO Readiness\*\*\s*\|\s*([0-9.]+)/10\s*\|\s*([A-F])', text)
    if score_match:
        result["overall_score"] = float(score_match.group(1))
        result["grade"] = score_match.group(2)

    readiness_match = re.search(r'\*\*LLM Visibility\*\*\s*\|\s*(.+?)\s*\|', text)
    if readiness_match:
        result["llm_readiness"] = readiness_match.group(1).strip().replace("🟡", "").replace("🟢", "").replace("🔴", "").strip()

    # Extract word count from gaps or content
    wc_match = re.search(r'Only\s+(\d+)\s+words', text) or re.search(r'(\d+)\s+words', text)
    if wc_match:
        result["word_count"] = int(wc_match.group(1))

    # Parse Dimension Breakdown table
    dim_section = re.search(r'## Dimension Breakdown\n\n(.+?)(?=\n##|\Z)', text, re.DOTALL)
    if dim_section:
        dim_text = dim_section.group(1)
        # Find table rows
        dim_map = {
            "AI Crawl Access": "ai_crawl_access",
            "Social Meta": "social_meta",
            "Heading Structure": "heading_structure",
            "Structured Data": "structured_data",
            "Content Depth": "content_depth",
            "Sitemap Quality": "sitemap_quality",
            "Semantic HTML": "semantic_html",
            "FAQ Content": "faq_content",
            "Content Citability": "content_citability",
            "llms.txt Presence": "llms_txt",
        }

        for line in dim_text.split("\n"):
            if line.startswith("|") and "Score" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")]
                parts = [p for p in parts if p]
                if len(parts) >= 4:
                    dim_name = parts[0].replace("**", "").strip()
                    score_str = parts[1].replace("/10", "").strip()
                    detail = parts[3] if len(parts) > 3 else ""

                    key = dim_map.get(dim_name, dim_name.lower().replace(" ", "_"))
                    try:
                        score = float(score_str)
                    except ValueError:
                        score = 0.0

                    result["dimensions"][key] = {
                        "score": score,
                        "detail": detail
                    }

    # Parse gaps
    gap_section = re.search(r'## Critical Gaps.*?\n\n(.+?)(?=\n##|\Z)', text, re.DOTALL)
    if gap_section:
        gap_text = gap_section.group(1)
        # Extract issue lines after - **Issue:**
        issues = re.findall(r'- \*\*Issue:\*\*\s*(.+?)(?=\n|$)', gap_text)
        result["gaps"] = [i.strip() for i in issues if i.strip()]

    # Parse recommendations
    rec_section = re.search(r'## Recommended Action Plan.*?\n\n(.+?)(?=\n##|\Z)', text, re.DOTALL)
    if rec_section:
        rec_text = rec_section.group(1)
        # Extract bullet points
        recs = re.findall(r'- \[(?:x| )\]\s*(.+?)(?=\n|$)', rec_text)
        result["recommendations"] = [r.strip() for r in recs if r.strip()]

    return result


def main():
    parser = argparse.ArgumentParser(description="Generate PDF from markdown GEO snapshot")
    parser.add_argument("markdown_file", help="Path to the markdown snapshot report")
    parser.add_argument("--output", "-o", default=None, help="Output directory (default: same as markdown)")
    args = parser.parse_args()

    md_path = Path(args.markdown_file)
    if not md_path.exists():
        print(f"❌ File not found: {md_path}")
        sys.exit(1)

    output_dir = Path(args.output) if args.output else md_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📄 Parsing {md_path.name}...")
    result = parse_markdown_snapshot(md_path)

    print(f"   Company: {result['company']}")
    print(f"   URL: {result['url']}")
    print(f"   Score: {result['overall_score']}/10 (Grade {result['grade']})")
    print(f"   Dimensions: {len(result['dimensions'])}")
    print(f"   Gaps: {len(result['gaps'])}")

    print(f"\n🎨 Generating branded PDF...")
    pdf_path = generate_snapshot_pdf(result, output_dir=output_dir)

    print(f"\n✅ PDF saved: {pdf_path}")
    print(f"   File size: {pdf_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
