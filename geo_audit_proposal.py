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

from geo_scanner import scan_site_sync

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_INPUT = Path(__file__).parent / "geoscore_results.json"
OUTPUT_DIR = Path(__file__).parent / "proposals"
OUTPUT_DIR.mkdir(exist_ok=True)

# Brand colors — Design v2 (light editorial)
CREAM = "#FAF7F2"          # warm cream page background
CREAM_SOFT = "#F3EEE4"     # section surfaces
CARD = "#FFFDF8"           # cards
LINE = "#E6DFD0"           # subtle divider
LINE_2 = "#D9D0BC"         # stronger divider
INK = "#1A1D1E"            # primary text
INK_SOFT = "#3B3F42"       # body copy
MUTED = "#7A7568"          # captions, meta
SAGE = "#7A9B76"           # primary accent (~oklch)
SAGE_DEEP = "#4A6B46"      # emphasis, links
CLAY = "#C45D3E"           # secondary accent (terracotta)
CLAY_DEEP = "#9C4527"
NAVY_LIGHT = "#F3EEE4"     # score hero / CTA bg (reused cream-soft)

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


def _domain_key(url: str) -> str:
    """Domain key for lookups (matches geo_competitor_scanner.extract_domain)."""
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "")

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

def build_html(result: dict, comparison_data: Optional[dict] = None) -> str:
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
        impact_color = "#22c55e" if impact == "High" else "#eab308" if impact == "Medium" else MUTED
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
    if comparison_data:
        target_info = comparison_data["target"]
        comps = comparison_data["competitors"]
        rank = comparison_data.get("target_rank")
        total = 1 + len(comps)
        dims = comparison_data.get("dimension_comparison", {})

        # Build comparison table rows
        dim_rows = ""
        for dim_key, label in DIMENSION_LABELS.items():
            if dim_key not in dims:
                continue
            scores_map = dims[dim_key]["scores"]
            target_score = scores_map.get(_domain_key(target_info["url"]), "—")
            comp_cells = ""
            for c in comps:
                c_score = scores_map.get(_domain_key(c["url"]), "—")
                comp_cells += f'<td class="td-score">{c_score}</td>'
            dim_rows += f"""
            <tr>
                <td class="td-dim">{label}</td>
                <td class="td-score" style="font-weight:600;color:{score_color(target_score) if isinstance(target_score, (int, float)) else MUTED};">{target_score}</td>
                {comp_cells}
            </tr>
            """

        # Overall row
        overall_cells = ""
        for c in comps:
            c_score = c.get("overall_score", "—")
            c_color = score_color(c_score) if isinstance(c_score, (int, float)) else MUTED
            overall_cells += f'<td class="td-score" style="font-weight:600;color:{c_color};">{c_score}</td>'

        rank_text = f"Your site ranks <strong>#{rank} of {total}</strong> in overall GEO readiness." if rank else ""
        trailing = comparison_data.get("trailing_gaps", [])
        trailing_html = ""
        if trailing:
            trailing_html = '<div style="margin-top:16px;"><p style="font-size:0.85rem;color:var(--clay);font-weight:600;margin-bottom:8px;">Dimensions where you trail competitors:</p><ul style="font-size:0.85rem;color:var(--ink-soft);margin:0;padding-left:18px;">'
            for gap in trailing:
                trailing_html += f"<li>{gap}</li>"
            trailing_html += "</ul></div>"

        comp_header_cols = "".join(f'<th class="th-comp">{extract_domain(c["url"]).replace("_", ".")[:20]}</th>' for c in comps)

        comp_section = f"""
        <div class="section">
            <h2 class="section-title">Competitor Benchmark</h2>
            <p class="section-sub">{rank_text} Side-by-side comparison across {len(DIMENSION_LABELS)} GEO dimensions:</p>
            <table class="gap-table" style="margin-bottom:16px;">
                <thead>
                    <tr>
                        <th class="th-dim">Dimension</th>
                        <th class="th-comp">You</th>
                        {comp_header_cols}
                    </tr>
                </thead>
                <tbody>
                    {dim_rows}
                    <tr style="border-top:2px solid rgba(0,0,0,0.1);">
                        <td class="td-dim" style="font-weight:600;">Overall</td>
                        <td class="td-score" style="font-weight:700;color:{score_color(overall) if overall else MUTED};">{overall if overall else "—"}</td>
                        {overall_cells}
                    </tr>
                </tbody>
            </table>
            {trailing_html}
        </div>
        """

    grade_c = score_color(overall) if overall else MUTED

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
  --cream: {CREAM};
  --cream-soft: {CREAM_SOFT};
  --card: {CARD};
  --line: {LINE};
  --line-2: {LINE_2};
  --ink: {INK};
  --ink-soft: {INK_SOFT};
  --muted: {MUTED};
  --sage: {SAGE};
  --sage-deep: {SAGE_DEEP};
  --clay: {CLAY};
  --clay-deep: {CLAY_DEEP};
  --navy-light: {NAVY_LIGHT};
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Outfit', sans-serif;
  background: var(--cream);
  color: var(--ink);
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
  border-bottom: 1px solid rgba(0,0,0,0.06);
  margin-bottom: 48px;
}}
.eyebrow {{
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--sage-deep);
  margin-bottom: 12px;
}}
.header h1 {{
  font-family: 'DM Serif Display', serif;
  font-size: 2.5rem;
  font-weight: 400;
  color: var(--ink);
  margin-bottom: 8px;
}}
.header-meta {{
  font-size: 0.9rem;
  color: var(--muted);
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
  color: var(--muted);
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
  color: var(--muted);
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
  color: var(--ink);
}}
.section-sub {{
  font-size: 0.9rem;
  color: var(--muted);
  margin-bottom: 24px;
}}

/* Dimension cards */
.dim-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 0;
  border-bottom: 1px solid rgba(0,0,0,0.04);
}}
.dim-info {{ flex: 1; min-width: 200px; }}
.dim-name {{ font-size: 0.95rem; font-weight: 500; color: var(--ink); }}
.dim-detail {{ font-size: 0.8rem; color: var(--muted); margin-top: 2px; }}
.dim-score-area {{
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 180px;
}}
.dim-bar-wrap {{
  flex: 1;
  height: 8px;
  background: rgba(0,0,0,0.06);
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
  color: var(--muted);
  border-bottom: 1px solid rgba(0,0,0,0.08);
}}
.gap-table td {{
  padding: 14px 16px;
  border-bottom: 1px solid rgba(0,0,0,0.04);
  vertical-align: top;
}}
.td-priority {{
  font-weight: 700;
  color: var(--clay);
  width: 60px;
}}
.td-gap {{ color: var(--ink); max-width: 220px; }}
.td-rec {{ color: var(--ink-soft); max-width: 280px; }}
.td-effort, .td-impact {{ width: 90px; }}
.badge {{
  display: inline-block;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  white-space: nowrap;
}}

/* Competitor comparison table */
.th-dim {{ width: 180px; }}
.th-comp {{ width: 100px; text-align: center; }}
.td-dim {{ font-size: 0.85rem; color: var(--ink); }}
.td-score {{ font-size: 0.85rem; text-align: center; width: 100px; }}

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
  color: var(--ink);
}}
.cta-box p {{
  font-size: 0.95rem;
  color: var(--muted);
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
  background: var(--card);
  border: 1px solid var(--line);
  min-width: 160px;
}}
.price-card .price {{
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--clay);
}}
.price-card .label {{
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: 4px;
}}
.cta-btn {{
  display: inline-block;
  background: var(--clay);
  color: #FFF;
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
  border-top: 1px solid rgba(0,0,0,0.06);
  margin-top: 48px;
}}
.footer p {{
  font-size: 0.8rem;
  color: var(--muted);
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
  color: var(--ink-soft);
  font-size: 0.9rem;
  border-bottom: 1px solid rgba(0,0,0,0.04);
}}
.comp-list li::before {{
  content: "→";
  color: var(--sage-deep);
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
        {gap_rows if gap_rows else '<tr><td colspan="5" style="text-align:center;color:' + MUTED + ';">No gaps detected — excellent GEO health.</td></tr>'}
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
    parser.add_argument("--competitors", nargs="+", help="Competitor URLs to scan and benchmark")
    parser.add_argument("--output", type=str, help="Custom output path (optional)")
    args = parser.parse_args()

    results = load_results(Path(args.input))
    result = find_result(results, args.url, args.index)

    # Build competitor comparison if URLs provided
    comparison_data = None
    if args.competitors:
        print(f"\n🔍 Scanning {len(args.competitors)} competitor(s)...")
        from geo_competitor_scanner import run_scan, build_comparison
        target_scan = result  # Use existing scanner result for target
        # Ensure target has full dimension data; if not, rescan
        if not target_scan.get("dimensions"):
            target_scan = run_scan(result["url"])
        comp_scans = [run_scan(url) for url in args.competitors]
        comparison_data = build_comparison(target_scan, comp_scans)
        print(f"   Target rank: #{comparison_data['target_rank']} of {1 + len(args.competitors)}")

    domain = extract_domain(result["url"])
    html = build_html(result, comparison_data=comparison_data)

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
    if comparison_data:
        print(f"   Competitors: {len(args.competitors)} (rank #{comparison_data['target_rank']})")
    elif args.competitors:
        print(f"   Competitors: {len(args.competitors)} (placeholder — run with scanner data for live comparison)")


if __name__ == "__main__":
    main()
