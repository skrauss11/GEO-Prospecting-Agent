"""
GEO Visibility Snapshot — Premium PDF generator (Design v2)

Renders a beautiful, editorial-quality PDF using Playwright + Chromium.
Template uses the full MadTech Growth design system:
  • Cream backgrounds, ink text
  • DM Serif Display + Outfit + JetBrains Mono
  • Sage primary accent, clay secondary
  • Inline SVG charts (donut score, horizontal bars, radar, competitor bars)

Requires: playwright (pip install playwright && playwright install chromium)
"""

from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, List
import math

# ── Try Playwright first, fall back to basic FPDF if unavailable ─────────────
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# ── Benchmarks ───────────────────────────────────────────────────────────────
try:
    from shared.benchmarks import get_percentile, get_vertical_label
except ImportError:
    def get_percentile(score: float, vertical: str = "default") -> int:
        return 50

    def get_vertical_label(vertical: str) -> str:
        return vertical.replace("_", " ").title()


# ── Brand palette ────────────────────────────────────────────────────────────
COLORS = {
    "cream": "#FAF7F2",
    "cream_soft": "#F3EEE4",
    "card": "#FFFDF8",
    "line": "#D9D0BC",
    "line_2": "#CFC5B0",
    "ink": "#1A1D1E",
    "ink_soft": "#3B3F42",
    "muted": "#6B6658",
    "sage": "#7A9B76",
    "sage_deep": "#4A6B46",
    "sage_soft": "#D4E5D2",
    "clay": "#C45D3E",
    "clay_deep": "#9C4527",
    "clay_soft": "#F5E0D8",
    "green": "#166534",
    "green_soft": "#dcfce7",
    "amber": "#92400e",
    "amber_soft": "#fef9c3",
    "red": "#991b1b",
    "red_soft": "#fee2e2",
}

# ── Score color helper ───────────────────────────────────────────────────────
def score_color(score: float) -> str:
    if score >= 7:
        return COLORS["green"]
    elif score >= 5:
        return COLORS["amber"]
    return COLORS["red"]


def score_bg(score: float) -> str:
    if score >= 7:
        return COLORS["green_soft"]
    elif score >= 5:
        return COLORS["amber_soft"]
    return COLORS["red_soft"]


# ── Dimension display names (short for radar labels) ─────────────────────────
DIM_LABELS = {
    "structured_data": "Structured Data / Schema",
    "ai_crawl_access": "AI Bot Accessibility",
    "sitemap_quality": "Sitemap & Indexing",
    "content_depth": "Content Depth",
    "faq_content": "FAQ & Q&A Content",
    "heading_structure": "Heading Hierarchy",
    "semantic_html": "Semantic HTML",
    "social_meta": "Social / OpenGraph Meta",
    "content_citability": "Content Citability",
    "llms_txt": "llms.txt File",
}

DIM_SHORT = {
    "structured_data": "Schema",
    "ai_crawl_access": "Bot Access",
    "sitemap_quality": "Sitemap",
    "content_depth": "Content",
    "faq_content": "FAQ",
    "heading_structure": "Headings",
    "semantic_html": "Semantic",
    "social_meta": "Social",
    "content_citability": "Citable",
    "llms_txt": "llms.txt",
}

DIM_ORDER = [
    "structured_data",
    "ai_crawl_access",
    "sitemap_quality",
    "content_depth",
    "faq_content",
    "heading_structure",
    "semantic_html",
    "social_meta",
    "content_citability",
    "llms_txt",
]


# ═══════════════════════════════════════════════════════════════════════════════
# SVG Chart generators
# ═══════════════════════════════════════════════════════════════════════════════

def svg_donut(score: float, size: int = 200, stroke: int = 18) -> str:
    """Generate an SVG donut chart for the overall score."""
    pct = min(score / 10, 1.0)
    radius = (size - stroke) / 2
    circumference = 2 * 3.14159265 * radius
    dash = circumference * pct
    gap = circumference - dash
    color = score_color(score)
    bg = COLORS["line"]
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none"
    stroke="{bg}" stroke-width="{stroke}" />
  <circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none"
    stroke="{color}" stroke-width="{stroke}"
    stroke-dasharray="{dash:.2f} {gap:.2f}"
    stroke-linecap="round"
    transform="rotate(-90 {size/2} {size/2})" />
  <text x="{size/2}" y="{size/2 + 2}" text-anchor="middle"
    font-family="'Outfit', sans-serif" font-size="42" font-weight="700"
    fill="{COLORS['ink']}">{score:.1f}</text>
  <text x="{size/2}" y="{size/2 + 26}" text-anchor="middle"
    font-family="'JetBrains Mono', monospace" font-size="11" font-weight="500"
    fill="{COLORS['muted']}" letter-spacing="0.08em">OUT OF 10</text>
</svg>"""


def svg_bar(score: float, width: int = 280, height: int = 10) -> str:
    """Generate an SVG horizontal bar for a dimension score."""
    pct = min(score / 10 * 100, 100)
    color = score_color(score)
    return f"""<svg width="{width}" height="{height + 2}" style="display:block;">
  <rect x="0" y="1" width="{width}" height="{height}" rx="{height/2}"
    fill="{COLORS['line']}" opacity="0.6"/>
  <rect x="0" y="1" width="{width * pct / 100:.1f}" height="{height}" rx="{height/2}"
    fill="{color}"/>
</svg>"""


def svg_grade_badge(grade: str) -> str:
    """SVG grade badge with background."""
    color_map = {
        "A": ("#166534", "#dcfce7"),
        "B": ("#166534", "#dcfce7"),
        "C": ("#92400e", "#fef9c3"),
        "D": ("#991b1b", "#fee2e2"),
        "F": ("#991b1b", "#fee2e2"),
    }
    text, bg = color_map.get(grade, ("#3B3F42", "#F3EEE4"))
    return f"""<svg width="72" height="36">
  <rect x="0" y="0" width="72" height="36" rx="18" fill="{bg}" stroke="{text}" stroke-width="1.5"/>
  <text x="36" y="24" text-anchor="middle" font-family="'Outfit', sans-serif"
    font-size="18" font-weight="700" fill="{text}">{grade}</text>
</svg>"""


def svg_readiness_indicator(readiness: str) -> str:
    """Small dot + text readiness indicator."""
    color_map = {
        "Very High": "#166534",
        "High": "#166534",
        "Medium": "#92400e",
        "Low": "#991b1b",
        "Very Low": "#991b1b",
    }
    color = color_map.get(readiness, COLORS["muted"])
    return f"""<svg width="150" height="20" style="display:inline-block;vertical-align:middle;">
  <circle cx="8" cy="10" r="5" fill="{color}"/>
  <text x="20" y="14" font-family="'JetBrains Mono', monospace" font-size="10"
    font-weight="500" fill="{COLORS['ink_soft']}" letter-spacing="0.04em">{readiness.upper()}</text>
</svg>"""


def svg_radar(dimensions: dict, competitor_dims: Optional[List[dict]] = None,
              size: int = 260) -> str:
    """
    Generate an SVG radar/spider chart for dimension scores.
    Optionally overlays competitor average as a lighter polygon.
    """
    cx, cy = size / 2, size / 2
    max_r = size / 2 - 36  # padding for labels
    n = len(DIM_ORDER)
    angle_step = 2 * math.pi / n
    start_angle = -math.pi / 2  # top

    # Grid levels (2, 4, 6, 8, 10)
    grid_levels = [2, 4, 6, 8, 10]
    grid_paths = []
    for level in grid_levels:
        pts = []
        for i in range(n):
            a = start_angle + i * angle_step
            r = max_r * (level / 10)
            x = cx + r * math.cos(a)
            y = cy + r * math.sin(a)
            pts.append(f"{x:.1f},{y:.1f}")
        grid_paths.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="{COLORS["line"]}" stroke-width="0.8" opacity="0.5"/>')

    # Axis lines + labels
    axis_lines = []
    labels = []
    for i, key in enumerate(DIM_ORDER):
        a = start_angle + i * angle_step
        x2 = cx + max_r * math.cos(a)
        y2 = cy + max_r * math.sin(a)
        axis_lines.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{COLORS["line"]}" stroke-width="0.6" opacity="0.4"/>')

        # Label position (slightly beyond radius)
        lx = cx + (max_r + 18) * math.cos(a)
        ly = cy + (max_r + 18) * math.sin(a)
        label = DIM_SHORT.get(key, key)
        anchor = "middle"
        if abs(math.cos(a)) > 0.7:
            anchor = "start" if math.cos(a) > 0 else "end"
        ly_text = ly + 3
        labels.append(
            f'<text x="{lx:.1f}" y="{ly_text:.1f}" text-anchor="{anchor}" '
            f'font-family="\'JetBrains Mono\', monospace" font-size="8" '
            f'fill="{COLORS["muted"]}" font-weight="500">{label}</text>'
        )

    # Target polygon
    target_pts = []
    for i, key in enumerate(DIM_ORDER):
        a = start_angle + i * angle_step
        score = dimensions.get(key, {}).get("score", 0)
        r = max_r * (score / 10)
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        target_pts.append(f"{x:.1f},{y:.1f}")

    target_poly = (
        f'<polygon points="{" ".join(target_pts)}" '
        f'fill="{COLORS["sage"]}" fill-opacity="0.18" '
        f'stroke="{COLORS["sage_deep"]}" stroke-width="2" stroke-linejoin="round"/>'
    )

    # Target dots
    target_dots = []
    for i, key in enumerate(DIM_ORDER):
        a = start_angle + i * angle_step
        score = dimensions.get(key, {}).get("score", 0)
        r = max_r * (score / 10)
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        target_dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{COLORS["sage_deep"]}"/>')

    # Competitor average polygon (optional)
    comp_poly = ""
    comp_dots = ""
    if competitor_dims:
        comp_pts = []
        for i, key in enumerate(DIM_ORDER):
            a = start_angle + i * angle_step
            vals = [d.get(key, {}).get("score", 0) for d in competitor_dims if key in d]
            avg = sum(vals) / len(vals) if vals else 0
            r = max_r * (avg / 10)
            x = cx + r * math.cos(a)
            y = cy + r * math.sin(a)
            comp_pts.append(f"{x:.1f},{y:.1f}")
        comp_poly = (
            f'<polygon points="{" ".join(comp_pts)}" '
            f'fill="{COLORS["clay"]}" fill-opacity="0.10" '
            f'stroke="{COLORS["clay"]}" stroke-width="1.5" stroke-dasharray="4,3" stroke-linejoin="round"/>'
        )
        for i, key in enumerate(DIM_ORDER):
            a = start_angle + i * angle_step
            vals = [d.get(key, {}).get("score", 0) for d in competitor_dims if key in d]
            avg = sum(vals) / len(vals) if vals else 0
            r = max_r * (avg / 10)
            x = cx + r * math.cos(a)
            y = cy + r * math.sin(a)
            comp_dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{COLORS["clay"]}"/>'

    legend = ""
    if competitor_dims:
        legend = f"""<g transform="translate({size - 110}, {size - 28})">
  <rect x="0" y="0" width="10" height="10" rx="2" fill="{COLORS["sage_deep"]}" opacity="0.7"/>
  <text x="16" y="9" font-family="'JetBrains Mono', monospace" font-size="8" fill="{COLORS['muted']}">Target</text>
  <rect x="60" y="0" width="10" height="10" rx="2" fill="{COLORS['clay']}" opacity="0.7"/>
  <text x="76" y="9" font-family="'JetBrains Mono', monospace" font-size="8" fill="{COLORS['muted']}">Competitors</text>
</g>"""

    return f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  {"".join(grid_paths)}
  {"".join(axis_lines)}
  {comp_poly}
  {target_poly}
  {comp_dots}
  {"".join(target_dots)}
  {"".join(labels)}
  {legend}
</svg>"""


def svg_competitor_bars(dimensions: dict, competitors: List[dict],
                        width: int = 640, bar_h: int = 10, gap: int = 28) -> str:
    """
    Side-by-side horizontal bars for target + competitors per dimension.
    Returns HTML (not SVG) since it needs text labels beside bars.
    """
    rows = []
    bar_w = 110
    for key in DIM_ORDER:
        label = DIM_SHORT.get(key, key)
        t_score = dimensions.get(key, {}).get("score", 0)
        t_pct = min(t_score / 10 * 100, 100)
        t_color = score_color(t_score)

        comp_bars = []
        for c in competitors[:3]:
            c_name = c.get("company") or urlparse(c["url"]).netloc.replace("www.", "")[:12]
            c_score = c.get("dimensions", {}).get(key, {}).get("score", 0)
            c_pct = min(c_score / 10 * 100, 100)
            c_color = score_color(c_score)
            comp_bars.append(f"""
            <div class="comp-bar-group">
              <div class="comp-bar-name">{c_name}</div>
              <div class="comp-bar-track">
                <div class="comp-bar-fill" style="width:{c_pct:.1f}%;background:{c_color};"></div>
              </div>
              <div class="comp-bar-score">{c_score:.1f}</div>
            </div>
            """)

        rows.append(f"""
        <div class="comp-row">
          <div class="comp-dim-label">{label}</div>
          <div class="comp-target">
            <div class="comp-bar-track target">
              <div class="comp-bar-fill" style="width:{t_pct:.1f}%;background:{t_color};"></div>
            </div>
            <div class="comp-bar-score target">{t_score:.1f}</div>
          </div>
          <div class="comp-rivals">
            {"".join(comp_bars)}
          </div>
        </div>
        """)

    return f"""<div class="comp-chart">
      {"".join(rows)}
    </div>"""


# ═══════════════════════════════════════════════════════════════════════════════
# HTML Template builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_html(result: dict, competitors: Optional[List[dict]] = None) -> str:
    """Build the full HTML document for the snapshot PDF."""
    company = result.get("company") or urlparse(result["url"]).netloc.replace("www.", "")
    url = result["url"]
    score = result.get("overall_score", 0)
    grade = result.get("grade", "N/A")
    readiness = result.get("llm_readiness", "Unknown")
    word_count = result.get("word_count", 0)
    dimensions = result.get("dimensions", {})
    gaps = result.get("gaps", [])
    recommendations = result.get("recommendations", [])
    vertical = result.get("vertical", "default")
    today = date.today().strftime("%B %d, %Y")

    # Benchmark
    percentile = get_percentile(score, vertical)
    vertical_label = get_vertical_label(vertical)

    # Build dimension rows
    dim_rows = []
    for key in DIM_ORDER:
        if key not in dimensions:
            continue
        d = dimensions[key]
        s = d.get("score", 0)
        detail = d.get("detail", "")
        color = score_color(s)
        dim_rows.append(f"""
        <tr class="dim-row">
          <td class="dim-name">{DIM_LABELS.get(key, key)}</td>
          <td class="dim-bar-cell">{svg_bar(s)}</td>
          <td class="dim-score" style="color:{color}">{s:.1f}</td>
          <td class="dim-detail">{detail}</td>
        </tr>
        """)

    # Gap/rec pairs
    gap_cards = []
    for i, (gap, rec) in enumerate(zip(gaps, recommendations), 1):
        gap_cards.append(f"""
        <div class="gap-card">
          <div class="gap-num">{i:02d}</div>
          <div class="gap-content">
            <p class="gap-title">{gap}</p>
            <p class="gap-rec">→ {rec}</p>
          </div>
        </div>
        """)

    # Technical checks
    sd = dimensions.get("structured_data", {})
    ai = dimensions.get("ai_crawl_access", {})
    sm = dimensions.get("sitemap_quality", {})
    og = dimensions.get("social_meta", {})
    llms = dimensions.get("llms_txt", {})

    def check_icon(score_val):
        if isinstance(score_val, dict):
            score_val = score_val.get("score", 0)
        if score_val >= 7:
            return '<span class="check pass">✓</span>'
        elif score_val >= 4:
            return '<span class="check warn">~</span>'
        return '<span class="check fail">✕</span>'

    checks_html = f"""
    <div class="check-grid">
      <div class="check-item">{check_icon(sd)} <span>JSON-LD Schema</span></div>
      <div class="check-item">{check_icon(ai)} <span>AI Bot Access</span></div>
      <div class="check-item">{check_icon(sm)} <span>XML Sitemap</span></div>
      <div class="check-item">{check_icon(og)} <span>OpenGraph Tags</span></div>
      <div class="check-item">{check_icon(llms)} <span>llms.txt</span></div>
      <div class="check-item"><span class="check neutral">{word_count}</span> <span>Homepage Words</span></div>
    </div>
    """

    schema_score = dimensions.get("structured_data", {}).get("score", 0)

    # Competitor data prep
    comp_dims = [c.get("dimensions", {}) for c in (competitors or [])]
    has_competitors = bool(competitors)

    # Radar chart (with competitor overlay if available)
    radar_html = svg_radar(dimensions, comp_dims if has_competitors else None, size=260)

    # Competitor comparison chart
    comp_chart_html = ""
    if has_competitors:
        comp_chart_html = svg_competitor_bars(dimensions, competitors)

    # Competitor names for header
    comp_names = ""
    if has_competitors:
        names = [c.get("company") or urlparse(c["url"]).netloc.replace("www.", "") for c in competitors[:3]]
        comp_names = f" vs {', '.join(names)}"

    total_pages = 5 if has_competitors else 4

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>GEO Snapshot — {company}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>
  :root {{
    --cream: {COLORS["cream"]};
    --cream-soft: {COLORS["cream_soft"]};
    --card: {COLORS["card"]};
    --line: {COLORS["line"]};
    --line-2: {COLORS["line_2"]};
    --ink: {COLORS["ink"]};
    --ink-soft: {COLORS["ink_soft"]};
    --muted: {COLORS["muted"]};
    --sage: {COLORS["sage"]};
    --sage-deep: {COLORS["sage_deep"]};
    --sage-soft: {COLORS["sage_soft"]};
    --clay: {COLORS["clay"]};
    --clay-deep: {COLORS["clay_deep"]};
    --clay-soft: {COLORS["clay_soft"]};
  }}

  @page {{ size: letter; margin: 0; }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Outfit', sans-serif;
    color: var(--ink);
    background: var(--cream);
    line-height: 1.5;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  .page {{
    width: 8.5in;
    min-height: 11in;
    padding: 48px 56px;
    position: relative;
    page-break-after: always;
    background: var(--cream);
  }}
  .page:last-child {{ page-break-after: auto; }}

  .header-strip {{
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 6px;
    background: var(--sage);
  }}

  .top-nav {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 36px;
  }}
  .brand {{
    font-family: 'DM Serif Display', serif;
    font-size: 20px;
    color: var(--ink);
  }}
  .brand span {{ color: var(--sage-deep); }}
  .doc-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
  }}

  /* ── Hero ─────────────────────────────────────────────── */
  .hero {{
    display: flex;
    gap: 40px;
    align-items: center;
    margin-bottom: 28px;
  }}
  .hero-score {{ flex-shrink: 0; }}
  .hero-info {{ flex: 1; }}
  .hero-eyebrow {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--sage-deep);
    margin-bottom: 10px;
  }}
  .hero-eyebrow::before {{
    content: "";
    display: inline-block;
    width: 22px;
    height: 2px;
    background: var(--sage);
    vertical-align: middle;
    margin-right: 10px;
  }}
  .hero-title {{
    font-family: 'DM Serif Display', serif;
    font-size: 34px;
    line-height: 1.1;
    color: var(--ink);
    margin-bottom: 6px;
  }}
  .hero-url {{
    font-size: 13px;
    color: var(--muted);
    margin-bottom: 18px;
  }}
  .hero-meta {{
    display: flex;
    gap: 18px;
    align-items: center;
  }}

  /* ── Benchmark pill ───────────────────────────────────── */
  .benchmark-bar {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 24px;
  }}
  .benchmark-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
  }}
  .benchmark-track {{
    flex: 1;
    height: 8px;
    background: var(--line);
    border-radius: 4px;
    position: relative;
    max-width: 280px;
  }}
  .benchmark-fill {{
    position: absolute;
    left: 0; top: 0; bottom: 0;
    background: var(--sage);
    border-radius: 4px;
  }}
  .benchmark-marker {{
    position: absolute;
    top: -3px;
    width: 14px;
    height: 14px;
    background: var(--clay);
    border: 2px solid var(--card);
    border-radius: 50%;
    transform: translateX(-50%);
    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
  }}
  .benchmark-text {{
    font-size: 12px;
    font-weight: 600;
    color: var(--ink-soft);
  }}
  .benchmark-text strong {{
    color: var(--clay-deep);
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
  }}

  /* ── Score summary ────────────────────────────────────── */
  .score-summary {{
    display: flex;
    gap: 16px;
    margin-bottom: 24px;
    flex-wrap: wrap;
  }}
  .score-pill {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
  }}
  .score-pill-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
  }}
  .score-pill-value {{
    font-size: 15px;
    font-weight: 700;
    color: var(--ink);
  }}

  /* ── Radar + info split ───────────────────────────────── */
  .cover-split {{
    display: flex;
    gap: 32px;
    align-items: flex-start;
    margin-bottom: 24px;
  }}
  .cover-radar {{ flex-shrink: 0; }}
  .cover-info {{ flex: 1; }}

  /* ── Info card ────────────────────────────────────────── */
  .info-card {{
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 22px 26px;
  }}
  .info-card h3 {{
    font-family: 'DM Serif Display', serif;
    font-size: 16px;
    margin-bottom: 10px;
  }}
  .info-card p {{
    font-size: 12px;
    color: var(--ink-soft);
    line-height: 1.7;
  }}

  /* ── Section header ───────────────────────────────────── */
  .section-header {{
    margin-bottom: 24px;
  }}
  .section-eyebrow {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--sage-deep);
    margin-bottom: 8px;
  }}
  .section-eyebrow::before {{
    content: "";
    display: inline-block;
    width: 22px;
    height: 2px;
    background: var(--sage);
    vertical-align: middle;
    margin-right: 10px;
  }}
  .section-title {{
    font-family: 'DM Serif Display', serif;
    font-size: 24px;
    line-height: 1.15;
    color: var(--ink);
  }}

  /* ── Dimension table ──────────────────────────────────── */
  .dim-table {{
    width: 100%;
    border-collapse: collapse;
  }}
  .dim-row {{
    border-bottom: 1px solid rgba(0,0,0,0.04);
  }}
  .dim-row td {{
    padding: 13px 8px;
    vertical-align: middle;
  }}
  .dim-name {{
    font-size: 13px;
    font-weight: 500;
    color: var(--ink);
    width: 220px;
    padding-left: 4px !important;
  }}
  .dim-bar-cell {{
    width: 280px;
  }}
  .dim-score {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px;
    font-weight: 700;
    width: 48px;
    text-align: center;
  }}
  .dim-detail {{
    font-size: 11px;
    color: var(--muted);
    width: 150px;
  }}

  /* ── Check grid ───────────────────────────────────────── */
  .check-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-top: 8px;
  }}
  .check-item {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    color: var(--ink-soft);
  }}
  .check {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    font-size: 13px;
    font-weight: 700;
    flex-shrink: 0;
  }}
  .check.pass {{ background: var(--sage-soft); color: var(--sage-deep); }}
  .check.warn {{ background: var(--amber-soft); color: var(--amber); }}
  .check.fail {{ background: var(--red-soft); color: var(--red); }}
  .check.neutral {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    background: var(--cream-soft);
    color: var(--muted);
    border-radius: 6px;
    width: auto;
    padding: 2px 8px;
  }}

  /* ── Gap cards ────────────────────────────────────────── */
  .gap-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 8px;
  }}
  .gap-card {{
    display: flex;
    gap: 16px;
    padding: 16px 18px;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    border-left: 3px solid var(--clay);
  }}
  .gap-num {{
    font-family: 'DM Serif Display', serif;
    font-size: 26px;
    color: var(--line-2);
    line-height: 1;
    flex-shrink: 0;
    min-width: 30px;
  }}
  .gap-content {{ flex: 1; }}
  .gap-title {{
    font-size: 13px;
    font-weight: 600;
    color: var(--ink);
    margin-bottom: 5px;
    line-height: 1.4;
  }}
  .gap-rec {{
    font-size: 12px;
    color: var(--sage-deep);
    line-height: 1.5;
  }}

  /* ── Competitor chart ─────────────────────────────────── */
  .comp-chart {{
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .comp-row {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 10px;
  }}
  .comp-dim-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--muted);
    width: 80px;
    flex-shrink: 0;
  }}
  .comp-target {{
    display: flex;
    align-items: center;
    gap: 8px;
    width: 170px;
    flex-shrink: 0;
  }}
  .comp-rivals {{
    display: flex;
    gap: 14px;
    flex: 1;
  }}
  .comp-bar-group {{
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
  }}
  .comp-bar-name {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 8px;
    color: var(--muted);
    width: 50px;
    text-align: right;
    flex-shrink: 0;
  }}
  .comp-bar-track {{
    flex: 1;
    height: 8px;
    background: var(--line);
    border-radius: 4px;
    overflow: hidden;
    max-width: 90px;
  }}
  .comp-bar-track.target {{ max-width: 110px; }}
  .comp-bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
  }}
  .comp-bar-score {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 600;
    color: var(--muted);
    width: 26px;
    text-align: right;
    flex-shrink: 0;
  }}
  .comp-bar-score.target {{
    color: var(--ink);
    font-size: 11px;
  }}
  .comp-legend {{
    display: flex;
    gap: 20px;
    margin-bottom: 16px;
    padding: 0 4px;
  }}
  .comp-legend-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 500;
    color: var(--ink-soft);
  }}
  .comp-legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 3px;
  }}

  /* ── CTA box ──────────────────────────────────────────── */
  .cta-box {{
    background: linear-gradient(135deg, var(--cream-soft) 0%, var(--sage-soft) 100%);
    border-radius: 20px;
    padding: 32px 36px;
    text-align: center;
    margin-top: 28px;
  }}
  .cta-box h2 {{
    font-family: 'DM Serif Display', serif;
    font-size: 22px;
    margin-bottom: 10px;
  }}
  .cta-box p {{
    font-size: 13px;
    color: var(--ink-soft);
    max-width: 420px;
    margin: 0 auto 18px;
    line-height: 1.6;
  }}
  .cta-contact {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 0.04em;
  }}

  /* ── Footer ───────────────────────────────────────────── */
  .page-footer {{
    position: absolute;
    bottom: 32px;
    left: 56px;
    right: 56px;
    display: flex;
    justify-content: space-between;
    font-family: 'JetBrains Mono', monospace;
    font-size: 8px;
    color: var(--muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border-top: 1px solid var(--line);
    padding-top: 12px;
  }}

  /* ── Ambient blobs ────────────────────────────────────── */
  .blob {{
    position: absolute;
    border-radius: 50%;
    filter: blur(80px);
    opacity: 0.35;
    pointer-events: none;
  }}
  .blob-sage {{
    width: 300px; height: 300px;
    background: var(--sage);
    top: -80px; right: -60px;
  }}
  .blob-clay {{
    width: 220px; height: 220px;
    background: var(--clay);
    bottom: 80px; left: -60px;
    opacity: 0.12;
  }}

  @media print {{
    .page {{ page-break-after: always; }}
    .page:last-child {{ page-break-after: auto; }}
  }}
</style>
</head>
<body>

<!-- ════════════════════════════════════════════════════════════
     PAGE 1 — COVER / HERO + RADAR
     ════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="header-strip"></div>
  <div class="blob blob-sage"></div>

  <div class="top-nav">
    <div class="brand">MadTech<span>Growth</span></div>
    <div class="doc-label">GEO Visibility Snapshot · {today}</div>
  </div>

  <div class="hero">
    <div class="hero-score">
      {svg_donut(score)}
    </div>
    <div class="hero-info">
      <div class="hero-eyebrow">AI Visibility Analysis</div>
      <h1 class="hero-title">{company}</h1>
      <p class="hero-url">{url}</p>
      <div class="hero-meta">
        {svg_grade_badge(grade)}
        {svg_readiness_indicator(readiness)}
      </div>
    </div>
  </div>

  <!-- Benchmark percentile bar -->
  <div class="benchmark-bar">
    <span class="benchmark-label">Benchmark</span>
    <div class="benchmark-track">
      <div class="benchmark-fill" style="width:{percentile}%;"></div>
      <div class="benchmark-marker" style="left:{percentile}%;"></div>
    </div>
    <span class="benchmark-text">You score higher than <strong>{percentile}%</strong> of {vertical_label} sites</span>
  </div>

  <div class="score-summary">
    <div class="score-pill">
      <span class="score-pill-label">Overall Score</span>
      <span class="score-pill-value" style="color:{score_color(score)}">{score:.1f}/10</span>
    </div>
    <div class="score-pill">
      <span class="score-pill-label">Grade</span>
      <span class="score-pill-value">{grade}</span>
    </div>
    <div class="score-pill">
      <span class="score-pill-label">Readiness</span>
      <span class="score-pill-value" style="color:{score_color(score)}">{readiness}</span>
    </div>
    <div class="score-pill">
      <span class="score-pill-label">Schema Score</span>
      <span class="score-pill-value" style="color:{score_color(schema_score)}">{schema_score:.1f}/10</span>
    </div>
  </div>

  <div class="cover-split">
    <div class="cover-radar">
      {radar_html}
    </div>
    <div class="cover-info">
      <div class="info-card">
        <h3>What is GEO?</h3>
        <p>Generative Engine Optimization ensures your brand is accurately represented in AI-generated answers. This snapshot measures how visible and accessible your site is to LLM crawlers and AI search engines — across structured data, bot accessibility, content depth, and semantic markup.</p>
      </div>
    </div>
  </div>

  <div class="page-footer">
    <span>MadTech Growth · GEO Advisory</span>
    <span>Page 1 of {total_pages}</span>
  </div>
</div>

<!-- ════════════════════════════════════════════════════════════
     PAGE 2 — DIMENSION BREAKDOWN
     ════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="header-strip"></div>

  <div class="top-nav">
    <div class="brand">MadTech<span>Growth</span></div>
    <div class="doc-label">Dimension Breakdown</div>
  </div>

  <div class="section-header">
    <div class="section-eyebrow">8-Pillar Assessment</div>
    <h2 class="section-title">How AI sees your site</h2>
  </div>

  <table class="dim-table">
    <tbody>
      {''.join(dim_rows)}
    </tbody>
  </table>

  <div class="page-footer">
    <span>MadTech Growth · GEO Advisory</span>
    <span>Page 2 of {total_pages}</span>
  </div>
</div>

<!-- ════════════════════════════════════════════════════════════
     PAGE 3 — TECHNICAL CHECKS + GAPS
     ════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="header-strip"></div>

  <div class="top-nav">
    <div class="brand">MadTech<span>Growth</span></div>
    <div class="doc-label">Technical Analysis</div>
  </div>

  <div class="section-header">
    <div class="section-eyebrow">Quick Checks</div>
    <h2 class="section-title">Technical snapshot</h2>
  </div>

  {checks_html}

  <div class="section-header" style="margin-top:36px;">
    <div class="section-eyebrow">Priority Issues</div>
    <h2 class="section-title">Gaps to fix</h2>
  </div>

  <div class="gap-list">
    {''.join(gap_cards) if gap_cards else '<p style="color:var(--muted);font-size:13px;">No critical gaps detected — excellent GEO health.</p>'}
  </div>

  <div class="page-footer">
    <span>MadTech Growth · GEO Advisory</span>
    <span>Page 3 of {total_pages}</span>
  </div>
</div>

{f'''
<!-- ════════════════════════════════════════════════════════════
     PAGE 4 — COMPETITOR COMPARISON
     ════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="header-strip"></div>

  <div class="top-nav">
    <div class="brand">MadTech<span>Growth</span></div>
    <div class="doc-label">Competitor Benchmark</div>
  </div>

  <div class="section-header">
    <div class="section-eyebrow">Side-by-Side</div>
    <h2 class="section-title">How you compare</h2>
  </div>

  <div class="comp-legend">
    <div class="comp-legend-item">
      <div class="comp-legend-dot" style="background:{COLORS['green']};"></div>
      <span>Strong (7–10)</span>
    </div>
    <div class="comp-legend-item">
      <div class="comp-legend-dot" style="background:{COLORS['amber']};"></div>
      <span>Moderate (5–6.9)</span>
    </div>
    <div class="comp-legend-item">
      <div class="comp-legend-dot" style="background:{COLORS['red']};"></div>
      <span>Weak (0–4.9)</span>
    </div>
  </div>

  {comp_chart_html}

  <div class="page-footer">
    <span>MadTech Growth · GEO Advisory</span>
    <span>Page 4 of {total_pages}</span>
  </div>
</div>
''' if has_competitors else ''}

<!-- ════════════════════════════════════════════════════════════
     FINAL PAGE — CTA / ABOUT
     ════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="header-strip"></div>
  <div class="blob blob-clay"></div>

  <div class="top-nav">
    <div class="brand">MadTech<span>Growth</span></div>
    <div class="doc-label">Next Steps</div>
  </div>

  <div class="section-header">
    <div class="section-eyebrow">Recommendation</div>
    <h2 class="section-title">Turn this snapshot into a roadmap</h2>
  </div>

  <div class="info-card" style="margin-bottom:22px;">
    <h3>What you get in a full GEO Audit</h3>
    <p style="margin-top:8px;">
      A comprehensive audit covers all 8 GEO dimensions, competitor benchmarking against 3 rival sites,
      a prioritized implementation roadmap with effort estimates, and a 90-day GEO sprint plan.
      You'll know exactly what to fix, in what order, and what impact to expect.
    </p>
  </div>

  <div class="check-grid" style="grid-template-columns: 1fr 1fr; margin-bottom:28px;">
    <div class="check-item"><span class="check pass">✓</span> <span>10-dimension deep scan</span></div>
    <div class="check-item"><span class="check pass">✓</span> <span>Competitor benchmarking</span></div>
    <div class="check-item"><span class="check pass">✓</span> <span>Prioritized fix list with effort</span></div>
    <div class="check-item"><span class="check pass">✓</span> <span>90-day implementation roadmap</span></div>
    <div class="check-item"><span class="check pass">✓</span> <span>Schema markup prescriptions</span></div>
    <div class="check-item"><span class="check pass">✓</span> <span>Monthly progress tracking</span></div>
  </div>

  <div class="cta-box">
    <h2>Ready to own your AI narrative?</h2>
    <p>Schedule a 20-minute discovery call. We'll review these findings, benchmark your competitors, and build a prioritized GEO roadmap.</p>
    <div class="cta-contact">scott@madtechgrowth.com · madtechgrowth.com</div>
  </div>

  <div class="page-footer">
    <span>MadTech Growth · GEO Advisory</span>
    <span>Page {total_pages} of {total_pages}</span>
  </div>
</div>

</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# HTML → PDF via Playwright
# ═══════════════════════════════════════════════════════════════════════════════

def html_to_pdf(html: str, output_path: Path) -> Path:
    """Render HTML to PDF using Playwright's headless Chromium."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.wait_for_timeout(1800)
        page.pdf(
            path=str(output_path),
            format="Letter",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()
    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback: basic FPDF
# ═══════════════════════════════════════════════════════════════════════════════

def generate_snapshot_pdf_fallback(result: dict, output_dir: Path) -> Path:
    """Minimal fallback using FPDF if Playwright is not installed."""
    from fpdf import FPDF

    company = result.get("company") or urlparse(result["url"]).netloc.replace("www.", "")
    safe_name = "".join(c if c.isalnum() else "_" for c in company).lower()[:40]
    today = date.today().isoformat()
    output_dir = output_dir / today
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"geo_snapshot_{safe_name}_{today}.pdf"

    class _PDF(FPDF):
        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(122, 117, 104)
            self.cell(0, 10, f"MadTech Growth · {date.today().strftime('%B %d, %Y')} · Page {self.page_no()}", align="C")

    pdf = _PDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "GEO Visibility Snapshot", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, company, ln=True)
    pdf.cell(0, 8, result["url"], ln=True)
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Score: {result.get('overall_score', 0)}/10   Grade: {result.get('grade', 'N/A')}", ln=True)
    pdf.output(str(pdf_path))
    return pdf_path


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def generate_snapshot_pdf(result: dict, output_dir: Path,
                          competitors: Optional[List[dict]] = None) -> Path:
    """
    Generate a branded PDF snapshot from a geo_scanner result dict.
    Optionally accepts a list of competitor result dicts for comparison.
    Uses Playwright + Chromium for high-quality rendering if available,
    otherwise falls back to basic FPDF.
    """
    company = result.get("company") or urlparse(result["url"]).netloc.replace("www.", "")
    safe_name = "".join(c if c.isalnum() else "_" for c in company).lower()[:40]
    today = date.today().isoformat()
    output_dir = output_dir / today
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"geo_snapshot_{safe_name}_{today}.pdf"

    if not HAS_PLAYWRIGHT:
        print("[snapshot_pdf] Playwright not available — using fallback FPDF renderer")
        return generate_snapshot_pdf_fallback(result, output_dir)

    html = build_html(result, competitors=competitors)
    return html_to_pdf(html, pdf_path)


# ═══════════════════════════════════════════════════════════════════════════════
# Quick test
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    test_result = {
        "url": "https://example-lawfirm.com",
        "company": "Example Law Firm",
        "vertical": "professional_services",
        "overall_score": 4.2,
        "grade": "D",
        "llm_readiness": "Low",
        "word_count": 340,
        "dimensions": {
            "structured_data": {"score": 2.0, "detail": "0 JSON-LD, 0 microdata"},
            "ai_crawl_access": {"score": 10.0, "detail": "allowed"},
            "sitemap_quality": {"score": 3.0, "detail": "absent: ~0 URLs"},
            "content_depth": {"score": 4.2, "detail": "~340 words"},
            "faq_content": {"score": 0.0, "detail": "0 kw, 0 links, 0 schema"},
            "heading_structure": {"score": 4.0, "detail": "h1:1 h2:2 h3:0"},
            "semantic_html": {"score": 3.0, "detail": "1 lists, 0 tables"},
            "social_meta": {"score": 5.0, "detail": "2 OG, 0 Twitter"},
            "content_citability": {"score": 3.5, "detail": "Low citation signals"},
            "llms_txt": {"score": 0.0, "detail": "No llms.txt found"},
        },
        "gaps": [
            "No structured data (JSON-LD/Schema.org)",
            "Missing or incomplete sitemap.xml",
            "Thin homepage content (~340 words)",
            "No FAQ section — LLMs lose Q&A-structured context",
        ],
        "recommendations": [
            "Implement JSON-LD structured data for relevant entity types",
            "Submit a comprehensive sitemap.xml to Google Search Console",
            "Expand homepage to 1000+ words with distinct service/problem sections",
            "Add a dedicated FAQ page with Q&A pairs covering common customer questions",
        ],
    }

    test_competitors = [
        {
            "url": "https://rival1.com",
            "company": "Rival One",
            "dimensions": {
                "structured_data": {"score": 7.5},
                "ai_crawl_access": {"score": 10.0},
                "sitemap_quality": {"score": 8.0},
                "content_depth": {"score": 6.5},
                "faq_content": {"score": 5.0},
                "heading_structure": {"score": 7.0},
                "semantic_html": {"score": 6.5},
                "social_meta": {"score": 8.0},
                "content_citability": {"score": 6.0},
                "llms_txt": {"score": 4.0},
            },
        },
        {
            "url": "https://rival2.com",
            "company": "Rival Two",
            "dimensions": {
                "structured_data": {"score": 5.0},
                "ai_crawl_access": {"score": 10.0},
                "sitemap_quality": {"score": 6.0},
                "content_depth": {"score": 5.5},
                "faq_content": {"score": 3.0},
                "heading_structure": {"score": 6.0},
                "semantic_html": {"score": 5.0},
                "social_meta": {"score": 7.0},
                "content_citability": {"score": 5.5},
                "llms_txt": {"score": 2.0},
            },
        },
    ]

    import tempfile
    out = Path(tempfile.gettempdir())
    path = generate_snapshot_pdf(test_result, out, competitors=test_competitors)
    print(f"PDF generated: {path}")
