#!/usr/bin/env python3
"""
geo_audit_proposal.py — Branded GEO Audit Proposal Generator

Reads a geo_scanner.py JSON result and outputs a print-ready HTML proposal.
This is your Starter-tier ($3K–$8K) sales document.

Usage:
    python3 geo_audit_proposal.py                          # uses geoscore_results.json, first scored site
    python3 geo_audit_proposal.py --url https://example.com # find by URL
    python3 geo_audit_proposal.py --index 1                # pick by index
    python3 geo_audit_proposal.py --input results.json --url https://example.com
    python3 geo_audit_proposal.py --competitors https://comp1.com https://comp2.com

Output:
    proposals/audit_proposal_<domain>_<date>.html
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_INPUT = Path(__file__).parent / "geoscore_results.json"
OUTPUT_DIR = Path(__file__).parent / "proposals"
OUTPUT_DIR.mkdir(exist_ok=True)

# Brand colors
NAVY = "#0B1120"
TERRACOTTA = "#C45D3E"
CREAM = "#FAF8F5"
GRAY_300 = "#D1CBC3"
GRAY_500 = "#8A8279"
GRAY_700 = "#4A4540"
NAVY_LIGHT = "#1a2540"

# Gap → (effort_hours, impact, priority)
# effort: Small (4-8h), Medium (1-2d), Large (3-5d)
# impact: High / Medium / Low
GAP_EFFORT = {
    "no structured data": ("Medium", "High", "P1"),
    "no json-ld": ("Medium", "High", "P1"),
    "minimal json-ld": ("Small", "High", "P1"),
    "ai bots blocked": ("Small", "High", "P1"),
    "missing sitemap": ("Small", "Medium", "P2"),
    "incomplete sitemap": ("Small", "Medium", "P2"),
    "thin content": ("Large", "High", "P1"),
    "no faq": ("Medium", "High", "P2"),
    "no llms.txt": ("Small", "Medium", "P3"),
    "llms.txt incomplete": ("Small", "Medium", "P3"),
    "poor heading": ("Small", "Medium", "P2"),
    "missing og": ("Small", "Low", "P3"),
    "images missing alt": ("Small", "Low", "P3"),
    "social meta": ("Small", "Low", "P3"),
    "robots.txt": ("Small", "High", "P1"),
}

DIMENSION_LABELS = {
    "structured_data": "Structured Data / Schema",
    "ai_crawl_access": "AI Bot Accessibility",
    "sitemap_quality": "Sitemap Quality",
    "content_depth": "Content Depth",
    "faq_content": "FAQ Content",
    "heading_structure": "Heading Structure",
    "semantic_html": "Semantic HTML",
    "social_meta": "Social Meta Tags",
    "content_citability": "Content Citability",
    "llms_txt": "llms.txt Presence",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "").replace(".", "_")

def score_color(score: float) -> str:
    if score >= 8:
        return "#22c55e"  # green
    elif score >= 6:
        return "#84cc16"  # lime
    elif score >= 4:
        return "#eab308"  # yellow
    elif score >= 2:
        return "#f97316"  # orange
    else:
        return "#ef4444"  # red

def score_bg(score: float) -> str:
    return score_color(score) + "22"

def score_border(score: float) -> str:
    return score_color(score) + "44"

def parse_gap_effort(gap_text: str) -> tuple[str, str, str]:
    """Map a gap description to effort/impact/priority."""
    lower = gap_text.lower()
    for keyword, (effort, impact, priority) in GAP_EFFORT.items():
        if keyword in lower:
            return effort, impact, priority
    # Fallback heuristics
    if "block" in lower or "robots" in lower:
        return "Small", "High", "P1"
    if "schema" in lower or "json-ld" in lower or "structured" in lower:
        return "Medium", "High", "P1"
    if "sitemap" in lower:
        return "Small", "Medium", "P2"
    if "content" in lower and "thin" in lower:
        return "Large", "High", "P1"
    if "faq" in lower:
        return "Medium", "High", "P2"
    if "llms.txt" in lower:
        return "Small", "Medium", "P3"
    if "heading" in lower:
        return "Small", "Medium", "P2"
    if "meta" in lower or "og" in lower or "social" in lower:
        return "Small", "Low", "P3"
    return "Medium", "Medium", "P2"

def grade_readiness_text(grade: str) -> str:
    return {
        "A": "AI agents can easily find and recommend you.",
        "B": "AI agents can find you, but there's room to improve visibility.",
        "C": "AI agents partially understand your site. Gaps are limiting reach.",
        "D": "AI agents struggle to extract value from your content.",
        "F": "Your site is practically invisible to AI search engines.",
    }.get(grade, "Readiness unknown.")

# ---------------------------------------------------------------------------
# HTML Builder
# ---------------------------------------------------------------------------

def build_html(result: dict, competitors: Optional[List[str]] = None) -> str:
    url = result["url"]
    company = result.get("company") or extract_domain(url)
    overall = result["overall_score"]
    grade = result.get("grade", "?")
    readiness = result.get("llm_readiness", "Unknown")
    word_count = result.get("word_count", 0)
    dims = result.get("dimensions", {})
    gaps = result.get("gaps", [])
    recs = result.get("recommendations", [])

    today = date.today().strftime("%B %d, %Y")
    domain = extract_domain(url).replace("_", ".")

    # --- Dimension rows ---
    dim_rows = ""
    for key, label in DIMENSION_LABELS.items():
        if key not in dims:
            continue
        d = dims[key]
        score = d.get("score", 0)
        if isinstance(score, (int, float)):
            pct = min(int((float(score) / 10) * 100), 100)
        else:
            pct = 0
        color = score_color(score)
        detail = d.get("detail", "")
        dim_rows += f"""
        <div class="dim-row">
            <div class="dim-info">
                <div class="dim-name">{label}</div>
                <div class="dim-detail">{detail}</div>
            </div>
            <div class="dim-score-area">
                <div class="dim-bar-wrap">
                    <div class="dim-bar" style="width:{pct}%;background:{color};"></div>
                </div>
                <div class="dim-score-val" style="color:{color};">{score}/10</div>
            </div>
        </div>
        """

    # --- Gap table ---
    gap_rows = ""
    for i, (gap, rec) in enumerate(zip(gaps, recs), 1):
        effort, impact, priority = parse_gap_effort(gap)
        effort_color = "#22c55e" if effort == "Small" else "#eab308" if effort == "Medium" else "#f97316"
        impact_color = "#22c55e" if impact == "High" else "#eab308" if impact == "Medium" else "#8A8279"
        gap_rows += f"""
        <tr>
            <td class="td-priority">{priority}</td>
            <td class="td-gap">{gap}</td>
            <td class="td-rec">{rec}</td>
            <td class="td-effort"><span class="badge" style="background:{effort_color}22;color:{effort_color};border:1px solid {effort_color}44;">{effort}</span></td>
            <td class="td-impact"><span class="badge" style="background:{impact_color}22;color:{impact_color};border:1px solid {impact_color}44;">{impact}</span></td>
        </tr>
        """

    # --- Competitor section ---
    comp_section = ""
    if competitors:
        comp_list = "".join(f"<li>{c}</li>" for c in competitors)
        comp_section = f"""
        <div class="section">
            <h2 class="section-title">Competitor Benchmark</h2>
            <p class="section-sub">We will analyze {len(competitors)} competitor site(s) and provide a side-by-side comparison:</p>
            <ul class="comp-list">{comp_list}</ul>
            <p class="section-sub">Included in your Growth Retainer engagement.</p>
        </div>
        """

    grade_c = score_color(overall) if overall else GRAY_500

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>GEO Audit Proposal — {company}</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
<style>
:root {{
  --navy: {NAVY};
  --terracotta: {TERRACOTTA};
  --cream: {CREAM};
  --gray-300: {GRAY_300};
  --gray-500: {GRAY_500};
  --gray-700: {GRAY_700};
  --navy-light: {NAVY_LIGHT};
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Outfit', sans-serif;
  background: var(--navy);
  color: var(--cream);
  line-height: 1.6;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}}
.container {{
  max-width: 900px;
  margin: 0 auto;
  padding: 60px 40px;
}}

/* Header */
.header {{
  text-align: center;
  padding-bottom: 48px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  margin-bottom: 48px;
}}
.eyebrow {{
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--terracotta);
  margin-bottom: 12px;
}}
.header h1 {{
  font-family: 'DM Serif Display', serif;
  font-size: 2.5rem;
  font-weight: 400;
  color: var(--cream);
  margin-bottom: 8px;
}}
.header-meta {{
  font-size: 0.9rem;
  color: var(--gray-500);
}}

/* Score Hero */
.score-hero {{
  background: var(--navy-light);
  border-radius: 20px;
  padding: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 40px;
  margin-bottom: 48px;
  flex-wrap: wrap;
}}
.score-main {{
  text-align: center;
  flex: 1;
  min-width: 200px;
}}
.score-number {{
  font-size: 5rem;
  font-weight: 700;
  line-height: 1;
}}
.score-label {{
  font-size: 0.85rem;
  color: var(--gray-500);
  margin-top: 4px;
}}
.score-grade {{
  display: inline-block;
  margin-top: 12px;
  padding: 6px 18px;
  border-radius: 100px;
  font-size: 0.8rem;
  font-weight: 600;
}}
.score-readiness {{
  flex: 1;
  min-width: 200px;
}}
.score-readiness h3 {{
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 8px;
}}
.score-readiness p {{
  font-size: 0.9rem;
  color: var(--gray-500);
  line-height: 1.6;
}}

/* Sections */
.section {{
  margin-bottom: 48px;
}}
.section-title {{
  font-family: 'DM Serif Display', serif;
  font-size: 1.5rem;
  font-weight: 400;
  margin-bottom: 8px;
}}
.section-sub {{
  font-size: 0.9rem;
  color: var(--gray-500);
  margin-bottom: 24px;
}}

/* Dimension cards */
.dim-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}}
.dim-info {{ flex: 1; min-width: 200px; }}
.dim-name {{ font-size: 0.95rem; font-weight: 500; }}
.dim-detail {{ font-size: 0.8rem; color: var(--gray-500); margin-top: 2px; }}
.dim-score-area {{
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 180px;
}}
.dim-bar-wrap {{
  flex: 1;
  height: 8px;
  background: rgba(255,255,255,0.06);
  border-radius: 4px;
  overflow: hidden;
  min-width: 100px;
}}
.dim-bar {{
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}}
.dim-score-val {{
  font-size: 0.9rem;
  font-weight: 600;
  width: 48px;
  text-align: right;
}}

/* Gap table */
.gap-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}}
.gap-table th {{
  text-align: left;
  padding: 12px 16px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--gray-500);
  border-bottom: 1px solid rgba(255,255,255,0.08);
}}
.gap-table td {{
  padding: 14px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  vertical-align: top;
}}
.td-priority {{
  font-weight: 700;
  color: var(--terracotta);
  width: 60px;
}}
.td-gap {{ color: var(--cream); max-width: 220px; }}
.td-rec {{ color: var(--gray-300); max-width: 280px; }}
.td-effort, .td-impact {{ width: 90px; }}
.badge {{
  display: inline-block;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  white-space: nowrap;
}}

/* CTA */
.cta-box {{
  background: var(--navy-light);
  border-radius: 20px;
  padding: 48px;
  text-align: center;
  margin-top: 24px;
}}
.cta-box h2 {{
  font-family: 'DM Serif Display', serif;
  font-size: 1.75rem;
  font-weight: 400;
  margin-bottom: 12px;
}}
.cta-box p {{
  font-size: 0.95rem;
  color: var(--gray-500);
  max-width: 500px;
  margin: 0 auto 24px;
  line-height: 1.6;
}}
.cta-pricing {{
  display: flex;
  justify-content: center;
  gap: 32px;
  margin-bottom: 32px;
  flex-wrap: wrap;
}}
.price-card {{
  text-align: center;
  padding: 20px 28px;
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  min-width: 160px;
}}
.price-card .price {{
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--terracotta);
}}
.price-card .label {{
  font-size: 0.75rem;
  color: var(--gray-500);
  margin-top: 4px;
}}
.cta-btn {{
  display: inline-block;
  background: var(--terracotta);
  color: var(--cream);
  text-decoration: none;
  font-size: 1rem;
  font-weight: 600;
  padding: 14px 40px;
  border-radius: 10px;
}}
.cta-btn:hover {{ opacity: 0.9; }}

/* Footer */
.footer {{
  text-align: center;
  padding-top: 48px;
  border-top: 1px solid rgba(255,255,255,0.06);
  margin-top: 48px;
}}
.footer p {{
  font-size: 0.8rem;
  color: var(--gray-700);
  margin-bottom: 4px;
}}

/* Print */
@media print {{
  body {{ background: #fff; color: #111; }}
  .score-hero, .cta-box, .dim-row {{ page-break-inside: avoid; }}
  .cta-btn {{ display: none; }}
}}

.comp-list {{
  list-style: none;
  padding: 0;
  margin: 0 0 16px;
}}
.comp-list li {{
  padding: 8px 0;
  color: var(--gray-300);
  font-size: 0.9rem;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}}
.comp-list li::before {{
  content: "→";
  color: var(--terracotta);
  margin-right: 10px;
}}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <div class="eyebrow">MadTech Growth — GEO Audit Proposal</div>
    <h1>{company}</h1>
    <div class="header-meta">{domain} · {today}</div>
  </div>

  <!-- Score Hero -->
  <div class="score-hero">
    <div class="score-main">
      <div class="score-number" style="color:{grade_c};">{overall if overall else "—"}</div>
      <div class="score-label">out of 10</div>
      <div class="score-grade" style="background:{score_bg(overall) if overall else 'transparent'};color:{grade_c};border:1px solid {score_border(overall) if overall else 'transparent'};">
        Grade: {grade}
      </div>
    </div>
    <div class="score-readiness">
      <h3 style="color:{grade_c};">{readiness} Readiness</h3>
      <p>{grade_readiness_text(grade) if overall else "Site could not be analyzed."}</p>
      <p style="margin-top:8px;font-size:0.8rem;">Homepage word count: {word_count:,} words</p>
    </div>
  </div>

  <!-- Dimensions -->
  <div class="section">
    <h2 class="section-title">8-Dimension Breakdown</h2>
    <p class="section-sub">How AI search engines currently perceive your site</p>
    {dim_rows}
  </div>

  <!-- Gaps -->
  <div class="section">
    <h2 class="section-title">Prioritized Fixes</h2>
    <p class="section-sub">Ranked by impact. Estimated effort = MadTech Growth delivery hours.</p>
    <table class="gap-table">
      <thead>
        <tr>
          <th>Priority</th>
          <th>Gap</th>
          <th>Recommendation</th>
          <th>Effort</th>
          <th>Impact</th>
        </tr>
      </thead>
      <tbody>
        {gap_rows if gap_rows else '<tr><td colspan="5" style="text-align:center;color:' + GRAY_500 + ';">No gaps detected — excellent GEO health.</td></tr>'}
      </tbody>
    </table>
  </div>

  {comp_section}

  <!-- CTA -->
  <div class="section">
    <div class="cta-box">
      <h2>Ready to fix your AI visibility?</h2>
      <p>
        This audit covers the full 8-dimension baseline. The next step is implementation —
        schema markup, content restructuring, FAQ deployment, and llms.txt creation.
      </p>
      <div class="cta-pricing">
        <div class="price-card">
          <div class="price">$3K–$8K</div>
          <div class="label">Starter Audit<br/>+ Implementation Roadmap</div>
        </div>
        <div class="price-card">
          <div class="price">$5K–$15K<span style="font-size:0.9rem;">/mo</span></div>
          <div class="label">Growth Retainer<br/>Ongoing GEO Optimization</div>
        </div>
      </div>
      <a class="cta-btn" href="https://madtechgrowth.com/contact">Book a Discovery Call →</a>
    </div>
  </div>

  <!-- Footer -->
  <div class="footer">
    <p>MadTech Growth · scott@madtechgrowth.com · madtechgrowth.com</p>
    <p>Generated {today} · Confidential — prepared exclusively for {company}</p>
  </div>

</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_results(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    data = json.loads(path.read_text())
    return data.get("results", [])


def find_result(results: list[dict], url: Optional[str], index: Optional[int]) -> dict:
    scored = [r for r in results if r.get("overall_score") is not None]

    if not scored:
        raise ValueError("No scored results found in input file.")

    if url:
        for r in scored:
            if url in r["url"] or r["url"] in url:
                return r
        raise ValueError(f"URL not found in results: {url}")

    if index is not None:
        if index < 0 or index >= len(scored):
            raise ValueError(f"Index {index} out of range (0–{len(scored)-1})")
        return scored[index]

    # Default: best prospect (lowest score = most opportunity)
    scored.sort(key=lambda r: r["overall_score"])
    return scored[0]


def main():
    parser = argparse.ArgumentParser(description="GEO Audit Proposal Generator")
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT),
                        help="Path to geo_scanner JSON output")
    parser.add_argument("--url", type=str, help="Target URL to generate proposal for")
    parser.add_argument("--index", type=int, help="Result index (0-based, scored only)")
    parser.add_argument("--competitors", nargs="+", help="Competitor URLs for benchmark section")
    parser.add_argument("--output", type=str, help="Custom output path (optional)")
    args = parser.parse_args()

    results = load_results(Path(args.input))
    result = find_result(results, args.url, args.index)

    domain = extract_domain(result["url"])
    html = build_html(result, competitors=args.competitors)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = OUTPUT_DIR / f"audit_proposal_{domain}_{date.today().isoformat()}.html"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    print(f"✅ Proposal generated: {out_path}")
    print(f"   Company: {result.get('company') or domain}")
    print(f"   URL: {result['url']}")
    print(f"   Score: {result.get('overall_score', '—')}/10 (Grade {result.get('grade', '?')})")
    print(f"   Gaps: {len(result.get('gaps', []))}")
    if args.competitors:
        print(f"   Competitors: {len(args.competitors)}")


if __name__ == "__main__":
    main()
