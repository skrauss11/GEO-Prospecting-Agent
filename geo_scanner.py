#!/usr/bin/env python3
from __future__ import annotations
"""
GEO Scanner — batch LLM readiness scorer for prospect lists.

Accepts site input via:
  • CSV file path        — python geo_scanner.py prospects.csv
  • Google Sheets URL    — python geo_scanner.py "https://docs.google.com/..."
  • Direct URLs          — python geo_scanner.py https://site1.com https://site2.com

Outputs:
  • Ranked JSON  (geoscore_results.json)
  • Ranked CSV   (geoscore_results.csv)
  • Console summary (color-coded table)

Usage:
    python geo_scanner.py <input> [input2 ...]
    python geo_scanner.py --json          # JSON output only
    python geo_scanner.py --csv            # CSV output only
    python geo_scanner.py --quiet         # suppress console output
    python geo_scanner.py --min-score 5   # only include scores >= N
"""

import argparse
import asyncio
import csv
import io
import json
import sys
import re
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import httpx

import citability
import geo_scoring
import llms_txt

from discover import discover as run_discover
from tools import TOOL_DISPATCH


def _normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _get(url: str, timeout: float = 15) -> httpx.Response:
    return httpx.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (geo-scanner)"},
        timeout=timeout,
        follow_redirects=True,
    )


# -----------------------------------------------------------------------------
# Input loaders
# -----------------------------------------------------------------------------


def load_csv(path: str) -> list[dict]:
    """Read a CSV and return rows with at least a 'url' column."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("url") or row.get("URL") or row.get("link") or row.get("website")
            if url and url.strip():
                entry = {"url": url.strip(), "_raw": row}
                # Carry through optional columns
                for col in ("company", "company_name", "name", "vertical", "category", "notes"):
                    if col in row and row[col].strip():
                        entry[col] = row[col].strip()
                rows.append(entry)
    return rows


def load_google_sheets(url: str) -> list[dict]:
    """
    Accept a Google Sheets URL (published to CSV or standard edit URL).
    Extracts the first sheet as CSV.
    """
    # Normalize: /edit#gid=0 → /export?format=csv&gid=0
    # or already a /export URL
    if "/export?" not in url:
        parsed = urlparse(url)
        # Handle /d/spreadsheetId//edit?gid=0&...
        match = re.match(r"/d/([a-zA-Z0-9-_]+)", parsed.path)
        if match:
            sheet_id = match.group(1)
            # Try to extract gid
            gid_match = re.search(r"gid=(\d+)", parsed.query)
            gid = gid_match.group(1) if gid_match else "0"
            url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        else:
            raise ValueError(f"Could not parse Google Sheets URL: {url}")

    resp = _get(url)
    resp.raise_for_status()
    rows = []
    reader = csv.DictReader(io.StringIO(resp.text))
    for row in reader:
        url = row.get("url") or row.get("URL") or row.get("link") or row.get("website")
        if url and url.strip():
            entry = {"url": url.strip(), "_raw": row}
            for col in ("company", "company_name", "name", "vertical", "category", "notes"):
                if col in row and row[col].strip():
                    entry[col] = row[col].strip()
            rows.append(entry)
    return rows


def load_direct_urls(args: list[str]) -> list[dict]:
    """Treat positional arguments as raw URLs or URL-containing strings."""
    rows = []
    for arg in args:
        # Skip flags
        if arg.startswith("--"):
            continue
        # If it looks like a URL, use it directly
        if re.match(r"https?://", arg) or re.match(r"[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", arg):
            rows.append({"url": _normalize_url(arg)})
        else:
            # Try to extract URLs from the string (handles commas, newlines)
            found = re.findall(r"https?://[a-zA-Z0-9.-._~:/?#\[\]@!$&'()*+,;=%]+", arg)
            for u in found:
                rows.append({"url": u})
    return rows


# -----------------------------------------------------------------------------
# GEO analyzer (async)
# -----------------------------------------------------------------------------


async def analyze_one(client: httpx.AsyncClient, entry: dict) -> dict:
    """Run the full GEO analysis for a single URL."""
    url = _normalize_url(entry["url"])
    result = {
        "url": url,
        "company": entry.get("company") or entry.get("company_name") or entry.get("name") or "",
        "vertical": entry.get("vertical") or entry.get("category") or "",
        "notes": entry.get("notes") or "",
        "overall_score": None,
        "grade": None,
        "llm_readiness": None,
        "word_count": None,
        "error": None,
        "dimensions": {},
        "gaps": [],
        "recommendations": [],
    }

    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    try:
        # --- Fetch homepage ---
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

        signals, _soup = geo_scoring.extract_page_signals(html)

        # --- robots.txt ---
        blocked_ai_bots: list[str] = []
        try:
            robots_resp = await client.get(f"{base}/robots.txt")
            if robots_resp.status_code == 200:
                blocked_ai_bots = geo_scoring.parse_robots_for_ai_bots(robots_resp.text)
        except httpx.HTTPError:
            pass

        # --- sitemap ---
        sitemap_present = False
        sitemap_url_count = 0
        sitemap_type = None
        try:
            sitemap_resp = await client.get(f"{base}/sitemap.xml")
            if sitemap_resp.status_code == 200:
                sitemap_present, sitemap_type, sitemap_url_count = (
                    geo_scoring.parse_sitemap_preview(sitemap_resp.text)
                )
        except httpx.HTTPError:
            pass

        # --- Base dimensions ---
        scores = geo_scoring.score_all_dimensions(
            signals, blocked_ai_bots, sitemap_present, sitemap_url_count
        )

        # --- Extended dimensions: citability + llms.txt ---
        cit_result = citability.score_html_citability(html)
        cit_dim = citability.citability_score_to_dimension(cit_result)
        scores["content_citability"] = cit_dim["score"]

        llms_result = llms_txt.analyze_llms_txt(base)
        llms_dim = llms_txt.llms_result_to_dimension(llms_result)
        scores["llms_txt"] = llms_dim["score"]

        # --- Weighted overall (base weights + scanner-specific extras) ---
        weights = {
            **geo_scoring.DIMENSION_WEIGHTS,
            "content_citability": 2.0,
            "llms_txt": 1.0,
        }
        overall_score = geo_scoring.weighted_overall(scores, weights)
        grade, readiness = geo_scoring.score_to_grade(overall_score)

        # --- Build gaps and recommendations ---
        gaps: list[str] = []
        recommendations: list[str] = []

        if scores["structured_data"] < 6:
            if signals.json_ld_count > 0:
                gaps.append("Minimal JSON-LD markup")
                recommendations.append("Add comprehensive Schema.org markup (Organization, Service, LocalBusiness)")
            else:
                gaps.append("No structured data (JSON-LD/Schema.org)")
                recommendations.append("Implement JSON-LD structured data for relevant entity types")

        if scores["ai_crawl_access"] != 10:
            gaps.append(f"AI bots may be blocked: {', '.join(blocked_ai_bots) if blocked_ai_bots else 'check robots.txt'}")
            recommendations.append("Audit robots.txt — ensure GPTBot, ClaudeBot, CCBot are allowed")

        if scores["sitemap_quality"] < 7:
            gaps.append("Missing or incomplete sitemap.xml")
            recommendations.append("Submit a comprehensive sitemap.xml to Google Search Console")

        if scores["content_depth"] < 7:
            gaps.append(f"Thin homepage content (~{signals.word_count} words)")
            recommendations.append("Expand homepage to 1000+ words with distinct service/problem sections")

        if scores["faq_content"] < 6:
            gaps.append("No FAQ section — LLMs lose Q&A-structured context")
            recommendations.append("Add a dedicated FAQ page with Q&A pairs covering common customer questions")

        if scores["heading_structure"] < 6:
            gaps.append("Poor or missing semantic heading structure")
            recommendations.append("Use H1 for page title, H2 for sections, H3 for subsections")

        if scores["social_meta"] < 5:
            gaps.append("Missing OpenGraph/Twitter Card meta tags")
            recommendations.append("Add OG title, description, image tags and Twitter Card meta")

        if scores["llms_txt"] < 7:
            if scores["llms_txt"] >= 3:
                gaps.append("llms.txt exists but incomplete")
                recommendations.append("Improve llms.txt: add title, description, 10+ page links across 3+ sections")
            else:
                gaps.append("No llms.txt file — AI crawlers lack a site guide")
                recommendations.append(
                    "Create llms.txt at domain root: a markdown file with your key pages and descriptions "
                    "(helps AI models understand your site structure in one pass)"
                )

        result.update({
            "overall_score": overall_score,
            "grade": grade,
            "llm_readiness": readiness,
            "word_count": signals.word_count,
            "error": None,
            "dimensions": {
                "structured_data": {"score": scores["structured_data"], "detail": f"{signals.json_ld_count} JSON-LD, {signals.microdata_count} microdata"},
                "ai_crawl_access": {"score": scores["ai_crawl_access"], "detail": "blocked" if blocked_ai_bots else "allowed"},
                "sitemap_quality": {"score": scores["sitemap_quality"], "detail": f"{sitemap_type or 'absent'}: ~{sitemap_url_count} URLs"},
                "content_depth": {"score": scores["content_depth"], "detail": f"~{signals.word_count} words"},
                "faq_content": {"score": scores["faq_content"], "detail": f"{signals.faq_keywords} kw, {signals.faq_links} links, {signals.faq_schema_count} schema"},
                "heading_structure": {"score": scores["heading_structure"], "detail": f"h1:{signals.h1_count} h2:{signals.h2_count} h3:{signals.h3_count}"},
                "semantic_html": {"score": scores["semantic_html"], "detail": f"{signals.list_count} lists, {signals.table_count} tables"},
                "social_meta": {"score": scores["social_meta"], "detail": f"{signals.og_count} OG, {signals.twitter_count} Twitter"},
                "content_citability": {"score": scores["content_citability"], "detail": cit_dim["detail"]},
                "llms_txt": {"score": scores["llms_txt"], "detail": llms_dim["detail"]},
            },
            "gaps": gaps,
            "recommendations": recommendations,
        })

    except httpx.TimeoutException:
        result["error"] = "Timeout fetching page"
    except httpx.HTTPStatusError as e:
        result["error"] = f"HTTP {e.response.status_code}"
    except Exception as e:
        result["error"] = str(e)

    return result


async def run_analysis(entries: list[dict], max_concurrency: int = 5) -> list[dict]:
    """Analyze all URLs concurrently with a semaphore cap."""
    semaphore = asyncio.Semaphore(max_concurrency)

    async def limited_analyze(client, entry):
        async with semaphore:
            return await analyze_one(client, entry)

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        tasks = [limited_analyze(client, e) for e in entries]
        results = await asyncio.gather(*tasks)

    # Sort by score ascending (low score = better prospect)
    scored = [r for r in results if r["overall_score"] is not None]
    errors = [r for r in results if r["overall_score"] is None]
    scored.sort(key=lambda r: r["overall_score"])
    return scored + errors


# -----------------------------------------------------------------------------
# Output formatters
# -----------------------------------------------------------------------------


def color_score(score: float | None) -> str:
    if score is None:
        return "\033[90m—\033[0m"
    if score >= 7:
        return f"\033[92m{score}\033[0m"       # green
    elif score >= 5:
        return f"\033[93m{score}\033[0m"       # yellow
    elif score >= 3:
        return f"\033[33m{score}\033[0m"       # orange
    else:
        return f"\033[91m{score}\033[0m"       # red


def print_summary(results: list[dict]) -> None:
    today = date.today().strftime("%B %d, %Y")
    scored = [r for r in results if r["overall_score"] is not None]
    print(f"\n\033[1mGEO Scanner Report — {today}\033[0m")
    print(f"{len(scored)} sites scored, {len(results) - len(scored)} errors\n")

    header = (f"{'#':<3} {'Company':<30} {'URL':<35} {'Score':>6} {'Grade':>5}  "
              f"{'Readiness':<12}  Top Gaps")
    print(header)
    print("-" * 110)

    for i, r in enumerate(scored, 1):
        company = (r.get("company") or "").strip()[:29]
        url_short = r["url"].replace("https://", "").replace("http://", "")[:35]
        score_str = color_score(r["overall_score"])
        grade = r.get("grade", "")
        readiness = r.get("llm_readiness", "")
        top_gaps = r.get("gaps", [])
        gap_str = " | ".join(top_gaps[:2])[:40]

        print(
            f"{i:<3} {company:<30} {url_short:<35} {score_str:>6} {grade:>5}  "
            f"{readiness:<12}  {gap_str}"
        )

    if scored:
        print()
        avg = sum(r["overall_score"] for r in scored) / len(scored)
        print(f"  Average score: {avg:.1f}/10  |  "
              f"Lowest: {scored[0]['overall_score']} ({scored[0].get('company', scored[0]['url'])})  |  "
              f"Highest: {scored[-1]['overall_score']} ({scored[-1].get('company', scored[-1]['url'])})")

    errors = [r for r in results if r["error"]]
    if errors:
        print(f"\n\033[91m{len(errors)} site(s) had errors:\033[0m")
        for r in errors:
            print(f"  • {r['url']} — {r['error']}")


def save_json(results: list[dict], path: str) -> None:
    output = {
        "generated": date.today().isoformat(),
        "total": len(results),
        "scored": len([r for r in results if r["overall_score"] is not None]),
        "results": results,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"  JSON → {path}")


def save_csv(results: list[dict], path: str) -> None:
    scored = [r for r in results if r["overall_score"] is not None]
    fieldnames = ["rank", "url", "company", "vertical", "overall_score", "grade",
                  "llm_readiness", "word_count", "error",
                  "structured_data_score", "ai_crawl_score", "sitemap_score",
                  "content_depth_score", "faq_score", "heading_score",
                  "semantic_html_score", "social_meta_score",
                  "gaps", "recommendations"]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, r in enumerate(scored, 1):
            dims = r.get("dimensions", {})
            writer.writerow({
                "rank": i,
                "url": r["url"],
                "company": r.get("company", ""),
                "vertical": r.get("vertical", ""),
                "overall_score": r["overall_score"],
                "grade": r["grade"],
                "llm_readiness": r["llm_readiness"],
                "word_count": r.get("word_count", ""),
                "error": r.get("error", ""),
                "structured_data_score": dims.get("structured_data", {}).get("score", ""),
                "ai_crawl_score": dims.get("ai_crawl_access", {}).get("score", ""),
                "sitemap_score": dims.get("sitemap_quality", {}).get("score", ""),
                "content_depth_score": dims.get("content_depth", {}).get("score", ""),
                "faq_score": dims.get("faq_content", {}).get("score", ""),
                "heading_score": dims.get("heading_structure", {}).get("score", ""),
                "semantic_html_score": dims.get("semantic_html", {}).get("score", ""),
                "social_meta_score": dims.get("social_meta", {}).get("score", ""),
                "gaps": " | ".join(r.get("gaps", [])),
                "recommendations": " | ".join(r.get("recommendations", [])),
            })
    print(f"  CSV  → {path}")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def detect_input(args: list[str]) -> tuple[str, list[dict]]:
    """
    Auto-detect input type and load sites.
    Returns (input_type, list of {url, ...}).
    """
    if not args:
        raise ValueError("No input provided. See --help for usage.")

    first = args[0].strip()

    # Google Sheets
    if "docs.google.com" in first:
        return ("google_sheets", load_google_sheets(first))

    # Local CSV
    if first.endswith(".csv") and Path(first).exists():
        return ("csv", load_csv(first))

    # Direct URLs
    return ("urls", load_direct_urls(args))


def main():
    parser = argparse.ArgumentParser(description="GEO Scanner — batch LLM readiness scorer")
    parser.add_argument("input", nargs="+", help="CSV path, Sheets URL, or list of URLs")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    parser.add_argument("--csv", action="store_true", help="CSV output only")
    parser.add_argument("--quiet", action="store_true", help="Suppress console output")
    parser.add_argument("--min-score", type=float, default=0,
                        help="Only include sites scoring at least this value (1-10)")
    parser.add_argument("--max-concurrency", type=int, default=5,
                        help="Max concurrent site scans (default: 5)")
    parser.add_argument("--discover", action="store_true",
                        help="Discover sites via web search, then analyze them. "
                             "Pass search params as positional args, e.g. "
                             "--discover 'NYC Law Firms' --limit 8")
    parser.add_argument("--limit", type=int, default=8,
                        help="Max sites to discover (default: 8)")
    parser.add_argument("--sheets", action="store_true",
                        help="Append results to the Google Sheets tracker")
    parser.add_argument("--new-sheet", action="store_true",
                        help="Create a fresh Google Sheets tracker (implies --sheets)")
    parser.add_argument("--title",
                        help="Custom title for the Google Sheet (use with --new-sheet)")
    parser.add_argument("--tracker-id",
                        help="Write results to a specific Google Sheet by ID (bypasses default tracker)")
    args = parser.parse_args()

    # --- Discover mode ---
    if args.discover:
        params = ' '.join(args.input)
        print(f'\n\033[1m🔍 Discover Mode\033[0m — searching for: "{params}"')
        print(f'   Limit: {args.limit} sites\n')

        disc_result = asyncio.run(run_discover(params, limit=args.limit))
        discovered_urls = disc_result['new_sites']

        if not discovered_urls:
            print('No new sites found. Try different search parameters.')
            sys.exit(0)

        entries = [{'url': u} for u in discovered_urls]
        print(f'\nAnalyzing {len(entries)} discovered sites...\n')

        results = asyncio.run(run_analysis(entries, max_concurrency=args.max_concurrency))

        # Add newly discovered URLs to shared history so they won't be re-scored
        from discover import add_to_history
        add_to_history(discovered_urls)
        print(f'Added {len(discovered_urls)} URLs to scoring history.')

    else:
        input_type, entries = detect_input(args.input)
        print(f'Loading from {input_type}... {len(entries)} site(s) found')
        results = asyncio.run(run_analysis(entries, max_concurrency=args.max_concurrency))

    # Filter by min-score
    if args.min_score > 0:
        results = [r for r in results if r["overall_score"] is None or r["overall_score"] >= args.min_score]

    # Output files
    json_path = Path(__file__).parent / "geoscore_results.json"
    csv_path = Path(__file__).parent / "geoscore_results.csv"

    if not args.csv:
        save_json(results, str(json_path))
    if not args.json:
        save_csv(results, str(csv_path))

    if not args.quiet:
        print_summary(results)

    # --- Google Sheets output ---
    if args.sheets or args.new_sheet or args.tracker_id:
        print()
        try:
            import sheets_integration
        except ImportError:
            print("⚠️  Google Sheets integration unavailable (sheets_integration.py not found). Skipping.")
            sheets_integration = None
        if sheets_integration:
            new_tracker = args.new_sheet
            sheet_title = args.title if args.title else None
            tracker_url = sheets_integration.append_to_tracker(
                results, new_sheet=new_tracker, quiet=args.quiet, sheet_title=sheet_title,
                tracker_id=args.tracker_id)
            if not args.quiet:
                print(f"   Results written to: {tracker_url}")


def scan_site_sync(url: str) -> dict:
    """
    Synchronous wrapper to scan a single site.
    Returns the full geo_scanner result dict.
    """
    import asyncio
    entry = {"url": url}
    return asyncio.run(run_analysis([entry], max_concurrency=1))[0]


async def scan_site_async(url: str) -> dict:
    """
    Asynchronous wrapper to scan a single site.
    Use this when already inside an asyncio event loop.
    """
    entry = {"url": url}
    results = await run_analysis([entry], max_concurrency=1)
    return results[0]


if __name__ == "__main__":
    main()
