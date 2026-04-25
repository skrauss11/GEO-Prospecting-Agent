#!/usr/bin/env python3
"""
geo_competitor_intel.py — Autonomous competitor discovery + comparative GEO scan.

Given a target URL, this script:
  1. Uses an LLM + web_search to identify 3 likely competitors
  2. Runs full GEO scans on the target + competitors via geo_scanner
  3. Builds a comparison via geo_competitor_scanner.build_comparison
  4. Writes a markdown report to proposals/ and a JSON to data/

This turns each prospect into a sales-ready comparative asset without manual
competitor lookup.

Usage:
    python3 geo_competitor_intel.py https://target.com
    python3 geo_competitor_intel.py https://target.com --vertical ps
    python3 geo_competitor_intel.py https://target.com --top 3 --post-discord
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))

from shared.config import DEFAULT_MODEL, DISCORD_WEBHOOK_URL, call_with_retry, get_openai_client
from geo_scanner import scan_site_sync
from geo_competitor_scanner import build_comparison, save_comparison_json, extract_domain
from tools import web_search


VERTICAL_HINTS = {
    "ps": "professional services firm (law, accounting, consulting, wealth management)",
    "dtc": "DTC / eCommerce consumer brand",
    "default": "company in the same industry and target market",
}


def discover_competitors(target_url: str, vertical: str = "default",
                         top: int = 3) -> list[str]:
    """Use the LLM to identify N competitor URLs for the target."""
    target_domain = extract_domain(target_url)
    hint = VERTICAL_HINTS.get(vertical, VERTICAL_HINTS["default"])

    print(f"[intel] Discovering {top} competitors for {target_domain}...", flush=True)

    # Pre-feed the model with raw search results so it picks real URLs
    search_results = web_search(f"{target_domain} competitors alternatives")

    prompt = f"""\
You are identifying direct competitors for the target company below.

Target URL: {target_url}
Target type: {hint}

Recent web search results for "{target_domain} competitors":
{search_results[:3000]}

Return JSON only — exactly {top} competitor URLs. Pick real, currently-operating
competitors that serve the same buyers. Do NOT include the target itself, and
do NOT include directories, listicles, news outlets, or marketplaces.

Format:
{{"competitors": [
  {{"url": "https://...", "name": "...", "why": "one short sentence"}}
]}}
"""

    client = get_openai_client()
    response = call_with_retry(
        lambda: client.chat.completions.create(
            model=DEFAULT_MODEL,
            max_tokens=600,
            messages=[
                {"role": "system", "content": "You return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
        ),
        label="competitor_discovery",
    )
    raw = (response.choices[0].message.content or "").strip()

    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise RuntimeError(f"Could not parse competitor JSON: {raw[:200]}")
        data = json.loads(match.group(0))

    competitors = data.get("competitors", [])[:top]
    target_dom = extract_domain(target_url)
    urls: list[str] = []
    for c in competitors:
        url = c.get("url", "").strip()
        if not url or extract_domain(url) == target_dom:
            continue
        why = c.get("why", "")
        print(f"  • {c.get('name', url)} — {url}", flush=True)
        if why:
            print(f"    {why}", flush=True)
        urls.append(url)

    return urls


def build_markdown_report(target_url: str, comparison: dict) -> str:
    """Render a markdown comparison report suitable for a proposal."""
    target_dom = extract_domain(target_url)
    today = date.today().isoformat()
    target = comparison.get("target", {})
    competitors = comparison.get("competitors", [])
    rankings = comparison.get("rankings", {})

    lines = [
        f"# Competitive GEO Intelligence — {target_dom}",
        f"_Generated {today} by MadTech Growth_",
        "",
        "## Overall GEO Score",
        "",
        f"- **{target.get('domain', target_dom)}**: {target.get('overall_score', 'N/A')}/10 (Grade {target.get('grade', 'N/A')})",
    ]
    for c in competitors:
        lines.append(
            f"- {c.get('domain')}: {c.get('overall_score', 'N/A')}/10 (Grade {c.get('grade', 'N/A')})"
        )

    lines += ["", "## Where Target Wins", ""]
    wins = rankings.get("target_wins", [])
    if wins:
        for dim in wins:
            lines.append(f"- {dim}")
    else:
        lines.append("_No dimensions where target leads all competitors._")

    lines += ["", "## Where Target Loses", ""]
    losses = rankings.get("target_losses", [])
    if losses:
        for dim in losses:
            lines.append(f"- {dim}")
    else:
        lines.append("_No dimensions where target trails all competitors._")

    lines += [
        "",
        "## Recommended Action",
        "",
        "Address the deficits above first — these are the dimensions where "
        "competitors are already getting cited by AI engines and the target is not.",
        "",
        "---",
        f"_Full JSON data: data/competitor_intel_{target_dom}_{today}.json_",
    ]
    return "\n".join(lines)


def post_to_discord(report: str) -> bool:
    if not DISCORD_WEBHOOK_URL:
        print("[intel] DISCORD_WEBHOOK_URL not set — skipping post.", flush=True)
        return False
    import httpx
    try:
        # Discord caps at 2000 chars
        chunk = report[:1900] + ("\n…(truncated)" if len(report) > 1900 else "")
        resp = httpx.post(
            DISCORD_WEBHOOK_URL,
            json={"content": chunk, "username": "GEO Competitor Intel"},
            timeout=30,
        )
        resp.raise_for_status()
        print(f"[intel] Posted to Discord (status {resp.status_code})", flush=True)
        return True
    except Exception as e:
        print(f"[intel] Discord post failed: {e}", flush=True)
        return False


def main():
    parser = argparse.ArgumentParser(description="Autonomous competitor GEO intel")
    parser.add_argument("target", help="Target URL to analyze")
    parser.add_argument("--vertical", default="default", choices=["ps", "dtc", "default"],
                        help="Vertical hint to improve competitor selection")
    parser.add_argument("--top", type=int, default=3, help="Number of competitors (default 3)")
    parser.add_argument("--post-discord", action="store_true", help="Post summary to Discord")
    parser.add_argument("--competitors", nargs="+", default=None,
                        help="Skip discovery; use these URLs as competitors")
    args = parser.parse_args()

    target = args.target.strip()
    target_dom = extract_domain(target)

    # Discover competitors (or use provided)
    if args.competitors:
        competitor_urls = args.competitors
    else:
        competitor_urls = discover_competitors(target, vertical=args.vertical, top=args.top)

    if not competitor_urls:
        print("[intel] No competitors found. Exiting.", flush=True)
        sys.exit(1)

    # Scan target
    print(f"\n[intel] Scanning target {target}...", flush=True)
    target_scan = scan_site_sync(target)
    if target_scan.get("error"):
        print(f"[intel] Target scan failed: {target_scan['error']}", flush=True)
        sys.exit(1)

    # Scan competitors
    competitor_scans: list[dict] = []
    for url in competitor_urls:
        print(f"[intel] Scanning competitor {url}...", flush=True)
        s = scan_site_sync(url)
        if s.get("error"):
            print(f"  ⚠️ Skipped {url}: {s['error']}", flush=True)
            continue
        competitor_scans.append(s)

    if not competitor_scans:
        print("[intel] No competitor scans succeeded. Exiting.", flush=True)
        sys.exit(1)

    # Build comparison
    comparison = build_comparison(target_scan, competitor_scans)

    # Save outputs
    today = date.today().isoformat()
    proposals_dir = Path(__file__).parent / "proposals"
    proposals_dir.mkdir(exist_ok=True)
    md_path = proposals_dir / f"competitor_intel_{target_dom}_{today}.md"
    md_path.write_text(build_markdown_report(target, comparison), encoding="utf-8")
    print(f"\n[intel] Markdown report: {md_path}", flush=True)

    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    json_path = data_dir / f"competitor_intel_{target_dom}_{today}.json"
    save_comparison_json(comparison, json_path)
    print(f"[intel] JSON data: {json_path}", flush=True)

    if args.post_discord:
        post_to_discord(md_path.read_text())


if __name__ == "__main__":
    main()
