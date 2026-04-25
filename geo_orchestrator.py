#!/usr/bin/env python3
"""
geo_orchestrator.py — Multi-Vertical GEO Discovery Orchestrator

Unified entry point for all vertical discovery pipelines.
Routes to vertical-specific modules, handles cross-vertical dedup,
normalized scoring, and unified output (Discord + CRM-ready JSON).

Usage:
    python3 geo_orchestrator.py --vertical ps              # Professional Services only
    python3 geo_orchestrator.py --vertical dtc             # DTC/eCommerce only
    python3 geo_orchestrator.py --vertical all             # All verticals (default)
    python3 geo_orchestrator.py --vertical ps --test       # Test mode (stdout only)
    python3 geo_orchestrator.py --vertical ps --crm        # Output CRM JSON file
    python3 geo_orchestrator.py --list                     # Show available verticals

Environment:
    NOUS_API_KEY — Nous gateway API key
    NOUS_BASE_URL — Nous gateway base URL (default: https://gateway.nous.uno/v1)
    DISCORD_WEBHOOK_URL — Discord webhook for live delivery
"""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from shared.config import DISCORD_WEBHOOK_URL
from shared.base import BaseVertical, Prospect
from verticals.professional_services import ProfessionalServicesVertical
from verticals.dtc_ecommerce import DTCEcommerceVertical
from shared.history import UnifiedHistory
from shared.scoring import ScoringNormalizer
from shared.output import DiscordFormatter, CRMFormatter
from shared.airtable import export_prospects_to_airtable
from shared.snapshot_pdf import generate_snapshot_pdf
from shared.daily_report import write_daily_report
from geo_scanner import scan_site_sync
from shared.benchmarks import update_distribution
from generate_geo_report import build_markdown, extract_domain

# Configuration
HISTORY_FILE = Path(__file__).parent / "data" / "discovery_history.json"

# Hot-lead snapshot output directory
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"

# Available verticals registry
VERTICALS: dict[str, type[BaseVertical]] = {
    "ps": ProfessionalServicesVertical,
    "dtc": DTCEcommerceVertical,
    "professional_services": ProfessionalServicesVertical,
    "professional-services": ProfessionalServicesVertical,
}


def get_vertical_instance(vertical_key: str) -> BaseVertical:
    """Factory function to get a vertical instance by key."""
    vertical_key = vertical_key.lower().replace("_", "-")
    if vertical_key not in VERTICALS:
        raise ValueError(f"Unknown vertical: {vertical_key}. Available: {list(VERTICALS.keys())}")
    return VERTICALS[vertical_key]()


def run_discovery(
    vertical: BaseVertical,
    history: UnifiedHistory,
    test_mode: bool = False,
    count: int = 3,
) -> tuple[str, list[Prospect]]:
    """
    Run discovery for a single vertical.
    
    Returns:
        Tuple of (discord_formatted_report, structured_prospects)
    """
    print(f"\n[orchestrator] Running discovery for: {vertical.name}", flush=True)
    print(f"  Target: {count} prospects", flush=True)
    print(f"  Mode: {'TEST' if test_mode else 'LIVE'}", flush=True)
    
    # Get previously discovered URLs for this vertical
    exclude_urls = history.get_urls_for_vertical(vertical.key)
    print(f"  Excluding {len(exclude_urls)} previously discovered URLs", flush=True)
    
    # Run the vertical's discovery
    prospects = vertical.discover(
        count=count,
        exclude_urls=exclude_urls,
        test_mode=test_mode,
    )
    
    if not prospects:
        print(f"  ⚠️ No prospects discovered", flush=True)
        return f"_No prospects discovered for {vertical.name}_", []
    
    print(f"  ✓ Discovered {len(prospects)} prospects", flush=True)
    
    # Normalize scores across verticals
    normalizer = ScoringNormalizer()
    for prospect in prospects:
        prospect.normalized_score = normalizer.normalize(
            score=prospect.raw_score,
            vertical=vertical.key,
            max_score=vertical.max_score,
        )
    
    # Format for Discord
    discord_report = DiscordFormatter.format_vertical_report(vertical, prospects)
    
    # Save to history
    history.add_prospects(vertical.key, prospects)
    print(f"  ✓ Saved {len(prospects)} to unified history", flush=True)
    
    return discord_report, prospects


def run_all_verticals(
    history: UnifiedHistory,
    test_mode: bool = False,
    crm_mode: bool = False,
    count: int = 3,
) -> dict[str, Any]:
    """Run discovery for all enabled verticals and combine results."""
    all_prospects: list[Prospect] = []
    reports: dict[str, str] = {}
    
    # Run each vertical
    for vertical_key in ["ps", "dtc"]:
        vertical = get_vertical_instance(vertical_key)
        report, prospects = run_discovery(
            vertical=vertical,
            history=history,
            test_mode=test_mode,
            count=count,
        )
        reports[vertical.key] = report
        all_prospects.extend(prospects)
    
    # Generate combined Discord report
    combined_report = DiscordFormatter.format_combined_report(reports, all_prospects)
    
    result = {
        "discord_report": combined_report,
        "vertical_reports": reports,
        "prospects": all_prospects,
        "prospect_count": len(all_prospects),
        "timestamp": datetime.now().isoformat(),
    }
    
    # Generate CRM output if requested
    if crm_mode:
        crm_data = CRMFormatter.format_prospects(all_prospects)
        result["crm_data"] = crm_data
        
        # Save to file
        crm_file = Path(__file__).parent / "data" / f"prospects_{date.today().isoformat()}.json"
        crm_file.parent.mkdir(exist_ok=True)
        crm_file.write_text(json.dumps(crm_data, indent=2))
        print(f"\n[orchestrator] CRM data saved to: {crm_file}", flush=True)
    
    return result


def send_to_discord(report: str, test_mode: bool = False) -> bool:
    """Send report to Discord webhook."""
    if test_mode:
        print("\n[TEST MODE] Would send to Discord:", flush=True)
        print("=" * 60, flush=True)
        return True
    
    if not DISCORD_WEBHOOK_URL:
        print("\n⚠️ DISCORD_WEBHOOK_URL not set — printing to stdout only", flush=True)
        return False
    
    try:
        import httpx
        
        payload = {
            "content": report,
            "username": "GEO Discovery Bot",
        }
        
        resp = httpx.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        print(f"\n✓ Posted to Discord (status {resp.status_code})", flush=True)
        return True
        
    except Exception as e:
        print(f"\n✗ Failed to post to Discord: {e}", flush=True)
        return False


def process_top_leads(prospects: list[Prospect], top_n: int = 2,
                      competitor_urls: Optional[list[str]] = None,
                      generate_pdfs: bool = False) -> tuple[list[Path], list[Path], str]:
    """
    Sort prospects by normalized score (descending), take top N,
    scan each with geo_scanner, write individual markdown snapshot files
    to proposals/, and optionally generate PDF snapshots.

    Returns:
        (md_paths, pdf_paths, markdown_summary) for Discord/reporting
    """
    if not prospects:
        return [], [], ""

    # Sort by normalized score descending, break ties by raw score
    ranked = sorted(prospects, key=lambda p: (p.normalized_score, p.raw_score), reverse=True)
    top = ranked[:top_n]

    print(f"\n📊 Ranked {len(prospects)} prospects — scanning top {len(top)} for snapshot reports...", flush=True)

    md_paths: list[Path] = []
    pdf_paths: list[Path] = []
    summary_lines: list[str] = [
        "",
        f"📎 **Top {len(top)} Lead Snapshots (Ranked by GEO Score):**",
    ]

    proposals_dir = Path(__file__).parent / "proposals"
    proposals_dir.mkdir(exist_ok=True)

    # Scan competitors if provided
    competitor_results: list[dict] = []
    if competitor_urls:
        print(f"\n  🔍 Scanning {len(competitor_urls)} competitor(s)...", flush=True)
        for cu in competitor_urls[:3]:
            try:
                c_res = scan_site_sync(cu)
                if not c_res.get("error"):
                    competitor_results.append(c_res)
                    print(f"    ✓ Competitor scan: {cu} — {c_res.get('overall_score', 0):.1f}/10", flush=True)
            except Exception as e:
                print(f"    ✗ Competitor scan failed for {cu}: {e}", flush=True)

    for i, prospect in enumerate(top, 1):
        try:
            print(f"  [{i}/{len(top)}] Scanning {prospect.url} (score: {prospect.normalized_score:.2f})...", flush=True)
            scan_result = scan_site_sync(prospect.url)
            if scan_result.get("error"):
                print(f"    ⚠️ Scan error: {scan_result['error']}", flush=True)
                summary_lines.append(f"• **{prospect.name}** — scan failed ({scan_result['error']})")
                continue

            # Inject company name + vertical from prospect into scan result
            scan_result["company"] = prospect.name or scan_result.get("company", "")
            scan_result["vertical"] = prospect.vertical or "default"

            # Update benchmark distribution
            try:
                update_distribution(scan_result.get("vertical", "default"),
                                   scan_result.get("overall_score", 0))
            except Exception:
                pass

            # Generate markdown snapshot
            md = build_markdown(scan_result)
            domain = extract_domain(prospect.url)
            today_iso = date.today().isoformat()
            md_filename = f"geo_snapshot_{domain}_{today_iso}.md"
            md_path = proposals_dir / md_filename
            md_path.write_text(md, encoding="utf-8")
            md_paths.append(md_path)

            score_str = scan_result.get("overall_score", "N/A")
            grade_str = scan_result.get("grade", "N/A")
            print(f"    ✓ Markdown saved: {md_path} (GEO: {score_str}/10, Grade {grade_str})", flush=True)

            # Optionally generate PDF
            if generate_pdfs:
                try:
                    pdf_path = generate_snapshot_pdf(scan_result, SNAPSHOTS_DIR,
                                                     competitors=competitor_results or None)
                    pdf_paths.append(pdf_path)
                    print(f"    ✓ PDF saved: {pdf_path}", flush=True)
                except Exception as e:
                    print(f"    ⚠️ PDF generation failed: {e}", flush=True)

            comp_note = ""
            if competitor_results:
                comp_note = f" (vs {len(competitor_results)} competitor(s))"
            pdf_note = f" | PDF: `{pdf_paths[-1].name}`" if pdf_paths else ""
            summary_lines.append(
                f"• **#{i} {prospect.name}** — GEO {score_str}/10 (Grade {grade_str}){comp_note}\n"
                f"  └─ MD: `{md_path.name}`{pdf_note}"
            )
        except Exception as e:
            print(f"    ✗ Failed to generate snapshot for {prospect.url}: {e}", flush=True)
            summary_lines.append(f"• **{prospect.name}** — snapshot generation failed ({e})")

    print(f"\n✓ Generated {len(md_paths)} markdown snapshot(s) in {proposals_dir}/", flush=True)
    if generate_pdfs:
        print(f"✓ Generated {len(pdf_paths)} PDF snapshot(s) in {SNAPSHOTS_DIR}/", flush=True)
    return md_paths, pdf_paths, "\n".join(summary_lines)


def process_hot_leads(prospects: list[Prospect]) -> list[Path]:
    """
    Legacy: scan hot prospects (score >= 0.8) with geo_scanner and generate PDF snapshots.
    Returns list of generated PDF paths.
    """
    hot = [p for p in prospects if p.normalized_score >= 0.8]
    if not hot:
        return []
    
    print(f"\n🔥 {len(hot)} hot lead(s) detected — generating PDF snapshots...", flush=True)
    pdf_paths: list[Path] = []
    
    for prospect in hot:
        try:
            print(f"  Scanning {prospect.url}...", flush=True)
            scan_result = scan_site_sync(prospect.url)
            if scan_result.get("error"):
                print(f"    ⚠️ Scan error: {scan_result['error']}", flush=True)
                continue
            pdf_path = generate_snapshot_pdf(scan_result, SNAPSHOTS_DIR)
            pdf_paths.append(pdf_path)
            print(f"    ✓ PDF saved: {pdf_path}", flush=True)
        except Exception as e:
            print(f"    ✗ Failed to generate snapshot for {prospect.url}: {e}", flush=True)
    
    print(f"\n✓ Generated {len(pdf_paths)} PDF snapshot(s) in {SNAPSHOTS_DIR}/", flush=True)
    return pdf_paths


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Vertical GEO Discovery Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --vertical ps                    # Run PS discovery only
  %(prog)s --vertical dtc --test            # Test DTC discovery (stdout only)
  %(prog)s --vertical all --crm             # All verticals + CRM export
  %(prog)s --list                           # Show available verticals
        """,
    )
    
    parser.add_argument(
        "--vertical",
        type=str,
        default="all",
        help="Vertical to run: ps, dtc, all (default: all)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: print to stdout, don't post to Discord",
    )
    parser.add_argument(
        "--crm",
        action="store_true",
        help="Export CRM-ready JSON file",
    )
    parser.add_argument(
        "--airtable",
        action="store_true",
        help="Export prospects to Airtable",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=3,
        help="Number of prospects to find per vertical (default: 3)",
    )
    parser.add_argument(
        "--snapshot-top",
        type=int,
        default=0,
        metavar="N",
        help="After discovery, rank prospects and generate PDF snapshots for the top N (default: 0 = off)",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Shorthand for --snapshot-top 2",
    )
    parser.add_argument(
        "--competitors",
        nargs="+",
        default=None,
        metavar="URL",
        help="1-3 competitor URLs to benchmark against in snapshots (e.g. --competitors https://rival1.com https://rival2.com)",
    )
    parser.add_argument(
        "--auto-pdf",
        action="store_true",
        help="Also auto-generate PDFs for top leads (default: markdown only)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available verticals and exit",
    )
    
    args = parser.parse_args()
    
    # Resolve --snapshot shorthand
    if args.snapshot and args.snapshot_top == 0:
        args.snapshot_top = 2
    
    if args.list:
        print("Available verticals:")
        for key, cls in VERTICALS.items():
            instance = cls()
            print(f"  {key:20} — {instance.name}")
        return
    
    # Initialize shared history
    history = UnifiedHistory(HISTORY_FILE)
    
    # Header
    print("=" * 60, flush=True)
    print("GEO Multi-Vertical Discovery Orchestrator", flush=True)
    print(f"Date: {date.today().strftime('%B %d, %Y')}", flush=True)
    if args.snapshot_top > 0:
        print(f"Mode: Discover → Rank → Snapshot Top {args.snapshot_top}", flush=True)
        if args.competitors:
            print(f"Competitors: {', '.join(args.competitors)}", flush=True)
    print("=" * 60, flush=True)
    
    # Run discovery
    if args.vertical.lower() in ["all", "both"]:
        result = run_all_verticals(
            history=history,
            test_mode=args.test,
            crm_mode=args.crm,
            count=args.count,
        )
        report = result["discord_report"]
    else:
        vertical = get_vertical_instance(args.vertical)
        report, prospects = run_discovery(
            vertical=vertical,
            history=history,
            test_mode=args.test,
            count=args.count,
        )
        
        # Generate CRM if requested
        if args.crm and prospects:
            crm_data = CRMFormatter.format_prospects(prospects)
            crm_file = Path(__file__).parent / "data" / f"prospects_{vertical.key}_{date.today().isoformat()}.json"
            crm_file.parent.mkdir(exist_ok=True)
            crm_file.write_text(json.dumps(crm_data, indent=2))
            print(f"\n[orchestrator] CRM data saved to: {crm_file}", flush=True)
    
    # Output and optionally send to Discord
    print("\n" + "=" * 60, flush=True)
    print("FINAL REPORT:", flush=True)
    print("=" * 60, flush=True)
    print(report, flush=True)
    
    # Determine prospect list for downstream processing
    if args.vertical.lower() in ["all", "both"]:
        all_prospects = result.get("prospects", [])
    else:
        all_prospects = prospects if 'prospects' in locals() else []
    
    # Snapshot mode: rank all prospects, take top N, scan + markdown snapshot
    pdf_paths = []
    if not args.test and args.snapshot_top > 0 and all_prospects:
        md_paths, pdf_paths, snapshot_summary = process_top_leads(
            all_prospects, top_n=args.snapshot_top,
            competitor_urls=args.competitors,
            generate_pdfs=args.auto_pdf,
        )
        if snapshot_summary:
            report += "\n" + snapshot_summary
            report += f"\n_Proposals ready in: `{Path(__file__).parent / 'proposals'}`_"
    
    # Legacy hot-lead processing (only when snapshot mode is OFF)
    elif not args.test and all_prospects:
        pdf_paths = process_hot_leads(all_prospects)
        if pdf_paths:
            snapshot_lines = [
                "",
                "📎 **Hot Lead Snapshots Generated:**",
                *[f"• `{p.name}`" for p in pdf_paths],
                f"_Stored locally in: `{SNAPSHOTS_DIR}`_",
            ]
            report += "\n".join(snapshot_lines)
    
    # Export to Airtable (only when --airtable flag is passed)
    if args.airtable and not args.test and all_prospects:
        crm_data = CRMFormatter.format_prospects(all_prospects)
        export_prospects_to_airtable(crm_data['prospects'])
    
    # Write human-readable daily lead report
    if not args.test and all_prospects:
        try:
            report_path = write_daily_report(all_prospects, md_paths=md_paths or [], pdf_paths=pdf_paths or [])
            print(f"\n📋 Daily lead report saved: {report_path}", flush=True)
            report_path_str = str(report_path)
        except Exception as e:
            print(f"\n⚠️ Failed to write daily lead report: {e}", flush=True)
            report_path_str = ""
    else:
        report_path_str = ""
    
    # Send to Discord (unless test mode)
    if not args.test:
        if report_path_str:
            report += f"\n📋 Full lead report: `{report_path_str}`"
        send_to_discord(report, test_mode=False)
    
    print("\n" + "=" * 60, flush=True)
    print(f"Discovery complete. History: {len(history.get_all_urls())} total URLs", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
