#!/usr/bin/env python3
"""
geo_competitor_scanner.py — Competitor GEO Benchmark Engine

Analyzes a target site + N competitor sites side-by-side across all
GEO dimensions. Produces:
  • Console comparison table
  • JSON report with deltas and ranking
  • Data ready for injection into geo_audit_proposal.py

Usage:
    python3 geo_competitor_scanner.py \
        --target https://example.com \
        --competitors https://comp1.com https://comp2.com

    # Save JSON for later use in proposal
    python3 geo_competitor_scanner.py \
        --target https://example.com \
        --competitors https://comp1.com https://comp2.com \
        --json-only
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from geo_scanner import scan_site_sync

# Dimension labels (must match keys produced by geo_scanner)
DIMENSION_LABELS = {
    "structured_data": "Structured Data",
    "ai_crawl_access": "AI Bot Access",
    "sitemap_quality": "Sitemap",
    "content_depth": "Content Depth",
    "faq_content": "FAQ Content",
    "heading_structure": "Headings",
    "semantic_html": "Semantic HTML",
    "social_meta": "Social Meta",
    "content_citability": "Citability",
    "llms_txt": "llms.txt",
}


def extract_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "")


def score_color_ansi(score: Optional[float]) -> str:
    if score is None:
        return "\033[90m—\033[0m"
    if score >= 8:
        return f"\033[92m{score}\033[0m"
    elif score >= 6:
        return f"\033[93m{score}\033[0m"
    elif score >= 4:
        return f"\033[33m{score}\033[0m"
    else:
        return f"\033[91m{score}\033[0m"


def run_scan(url: str) -> dict:
    """Run geo_scanner on a single URL."""
    print(f"  Scanning {url} ...", flush=True)
    result = scan_site_sync(url)
    if result.get("error"):
        print(f"    ⚠️  {result['error']}")
    else:
        print(f"    ✓  Score {result.get('overall_score', '—')}/10  Grade {result.get('grade', '?')}")
    return result


def build_comparison(target: dict, competitors: list[dict]) -> dict:
    """Build structured comparison data."""
    all_sites = [target] + competitors

    # Extract dimension scores for each site
    dim_matrix: dict[str, list[Optional[float]]] = {}
    for dim_key in DIMENSION_LABELS:
        dim_matrix[dim_key] = []
        for site in all_sites:
            dims = site.get("dimensions", {})
            score = dims.get(dim_key, {}).get("score")
            dim_matrix[dim_key].append(score)

    # Overall ranking
    scored_sites = [
        {"url": s["url"], "company": s.get("company") or extract_domain(s["url"]),
         "overall_score": s.get("overall_score"), "grade": s.get("grade")}
        for s in all_sites
        if s.get("overall_score") is not None
    ]
    scored_sites.sort(key=lambda x: x["overall_score"], reverse=True)

    # Find target rank
    target_rank = None
    for i, s in enumerate(scored_sites, 1):
        if s["url"] == target["url"]:
            target_rank = i
            break

    # Per-dimension deltas (target vs best competitor)
    deltas = {}
    for dim_key, scores in dim_matrix.items():
        target_score = scores[0]
        if target_score is None:
            continue
        best_comp = max((s for s in scores[1:] if s is not None), default=None)
        if best_comp is not None:
            deltas[dim_key] = round(target_score - best_comp, 1)

    # Gaps where target trails the field
    trailing_gaps = []
    for dim_key, scores in dim_matrix.items():
        target_score = scores[0]
        if target_score is None:
            continue
        comp_scores = [s for s in scores[1:] if s is not None]
        if comp_scores and target_score < max(comp_scores):
            label = DIMENSION_LABELS.get(dim_key, dim_key)
            trailing_gaps.append(f"{label}: {target_score} vs competitor best {max(comp_scores)}")

    return {
        "generated": date.today().isoformat(),
        "target": {
            "url": target["url"],
            "company": target.get("company") or extract_domain(target["url"]),
            "overall_score": target.get("overall_score"),
            "grade": target.get("grade"),
            "readiness": target.get("llm_readiness"),
            "gaps": target.get("gaps", []),
            "recommendations": target.get("recommendations", []),
        },
        "competitors": [
            {
                "url": c["url"],
                "company": c.get("company") or extract_domain(c["url"]),
                "overall_score": c.get("overall_score"),
                "grade": c.get("grade"),
                "readiness": c.get("llm_readiness"),
            }
            for c in competitors
        ],
        "ranking": scored_sites,
        "target_rank": target_rank,
        "dimension_comparison": {
            dim_key: {
                "label": DIMENSION_LABELS.get(dim_key, dim_key),
                "scores": {
                    extract_domain(all_sites[i]["url"]): score
                    for i, score in enumerate(scores)
                },
            }
            for dim_key, scores in dim_matrix.items()
        },
        "deltas": deltas,
        "trailing_gaps": trailing_gaps,
    }


def print_comparison_table(comparison: dict) -> None:
    """Print a side-by-side console table."""
    target = comparison["target"]
    competitors = comparison["competitors"]
    all_names = [target["company"]] + [c["company"] for c in competitors]

    print("\n" + "=" * 80)
    print(f"  GEO Competitor Benchmark — {target['company']}")
    print("=" * 80)

    # Header
    name_col = 22
    score_col = 10
    header = f"{'Dimension':<{name_col}}"
    for name in all_names:
        header += f"{name[:score_col-1]:>{score_col}}"
    header += f"{'Leader':>{score_col}}"
    print(header)
    print("-" * (name_col + score_col * (len(all_names) + 1)))

    # Rows
    dims = comparison["dimension_comparison"]
    for dim_key in DIMENSION_LABELS:
        if dim_key not in dims:
            continue
        scores_map = dims[dim_key]["scores"]
        row_vals = [scores_map.get(name) for name in all_names]
        valid = [(v, i) for i, v in enumerate(row_vals) if v is not None]
        leader = "—"
        if valid:
            best_val, best_idx = max(valid, key=lambda x: x[0])
            leader = all_names[best_idx]

        row = f"{DIMENSION_LABELS[dim_key]:<{name_col}}"
        for val in row_vals:
            cell = f"{val:.1f}" if val is not None else "—"
            row += f"{cell:>{score_col}}"
        row += f"{leader[:score_col-1]:>{score_col}}"
        print(row)

    # Overall row
    print("-" * (name_col + score_col * (len(all_names) + 1)))
    overall_vals = [target["overall_score"]] + [c["overall_score"] for c in competitors]
    valid = [(v, i) for i, v in enumerate(overall_vals) if v is not None]
    leader = "—"
    if valid:
        best_val, best_idx = max(valid, key=lambda x: x[0])
        leader = all_names[best_idx]

    row = f"{'OVERALL':<{name_col}}"
    for val in overall_vals:
        cell = score_color_ansi(val)
        # Strip ANSI for length calculation, then pad
        plain = cell.replace("\033[92m", "").replace("\033[93m", "").replace("\033[33m", "").replace("\033[91m", "").replace("\033[0m", "")
        pad = score_col - len(plain)
        row += f"{' ' * pad}{cell}"
    row += f"{leader:>{score_col}}"
    print(row)

    print("=" * 80)
    rank = comparison["target_rank"]
    total = len(all_names)
    if rank:
        print(f"  Target rank: {rank} of {total}")
        if rank > 1:
            print(f"  ⚠️  Target trails {rank - 1} competitor(s) in overall GEO readiness")
    print()

    if comparison["trailing_gaps"]:
        print("  Dimensions where target trails competitors:")
        for gap in comparison["trailing_gaps"]:
            print(f"    • {gap}")
        print()


def save_comparison_json(comparison: dict, out_path: Optional[Path] = None) -> Path:
    """Save comparison to JSON. Returns the path."""
    target_domain = extract_domain(comparison["target"]["url"])
    if out_path is None:
        out_path = Path(__file__).parent / "data" / f"competitor_comparison_{target_domain}_{date.today().isoformat()}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="GEO Competitor Benchmark Scanner")
    parser.add_argument("--target", required=True, help="Target site URL")
    parser.add_argument("--competitors", nargs="+", required=True, help="Competitor URLs")
    parser.add_argument("--json-only", action="store_true", help="Suppress console table, save JSON only")
    parser.add_argument("--output", type=str, help="Custom JSON output path")
    args = parser.parse_args()

    print(f"\n🔍 Competitor Benchmark: {args.target}")
    print(f"   vs {len(args.competitors)} competitor(s)\n")

    target = run_scan(args.target)
    if target.get("error") and target.get("overall_score") is None:
        print("✗ Target site could not be analyzed. Exiting.")
        sys.exit(1)

    competitors = []
    for url in args.competitors:
        result = run_scan(url)
        competitors.append(result)

    comparison = build_comparison(target, competitors)

    if not args.json_only:
        print_comparison_table(comparison)

    out_path = save_comparison_json(comparison, Path(args.output) if args.output else None)
    print(f"💾 Comparison saved: {out_path}")


if __name__ == "__main__":
    main()
