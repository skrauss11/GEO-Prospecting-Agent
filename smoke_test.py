#!/usr/bin/env python3
"""
smoke_test.py — Warm-up test suite for the GEO discovery stack.

Runs without API keys. Exercises imports, history, scoring, formatting,
and vertical test-mode discovery. Use before live runs to catch breakage.

Usage:
    python3 smoke_test.py
    python3 smoke_test.py --verbose
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Set dummy key so vertical imports don't choke
os.environ.setdefault("NOUS_API_KEY", "sk-dummy")

sys.path.insert(0, str(Path(__file__).parent))

PASS = 0
FAIL = 0

def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        print(f"  ❌ {label}")
        if detail:
            print(f"     → {detail}")


def test_imports() -> None:
    print("\n📦 Module Imports")
    modules = [
        "tools", "geo_scoring", "discover", "geo_scanner",
        "shared.base", "shared.scoring", "shared.output", "shared.history",
        "verticals.professional_services", "verticals.dtc_ecommerce",
        "geo_orchestrator",
    ]
    for mod in modules:
        try:
            __import__(mod)
            check(mod, True)
        except Exception as e:
            check(mod, False, str(e))


def test_unified_history() -> None:
    print("\n🗄️  UnifiedHistory")
    from shared.history import UnifiedHistory
    from shared.base import Prospect

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = Path(f.name)

    try:
        h = UnifiedHistory(tmp)
        check("create fresh", True)
        check("empty urls", len(h.get_all_urls()) == 0)

        # add_urls (standalone-script path)
        h.add_urls("ps", ["https://firma.com", "https://firmb.com"])
        check("add_urls ps", len(h.get_all_urls()) == 2)
        check("get_urls_for_vertical ps", len(h.get_urls_for_vertical("ps")) == 2)

        # add_prospects (orchestrator path)
        p = Prospect(
            name="Test Firm",
            url="https://firmc.com",
            vertical="ps",
            raw_score=5,
            geo_gaps=["No schema"],
        )
        h.add_prospects("ps", [p])
        check("add_prospects", len(h.get_all_urls()) == 3)
        check("recent prospects", len(h.get_recent_prospects()) == 1)

        stats = h.get_stats()
        check("stats total_urls", stats["total_urls"] == 3)
        check("stats by_vertical", stats["by_vertical"].get("ps") == 3)

        # dedup
        h.add_urls("ps", ["https://firma.com"])
        check("dedup same url", len(h.get_all_urls()) == 3)

        # Persistence
        h2 = UnifiedHistory(tmp)
        check("reload persisted", len(h2.get_all_urls()) == 3)

    finally:
        tmp.unlink(missing_ok=True)


def test_prospect() -> None:
    print("\n👤 Prospect Data Model")
    from shared.base import Prospect

    p = Prospect(
        name="Acme Law",
        url="https://acmelaw.com",
        vertical="ps",
        raw_score=5,
        max_score=5,
        normalized_score=1.0,
        geo_gaps=["No JSON-LD"],
        emails=["hello@acmelaw.com"],
        category="Law Firm",
    )
    d = p.to_dict()
    check("to_dict name", d["name"] == "Acme Law")
    check("to_dict score normalized", "normalized_score" in d["scoring"])
    check("domain property", p.domain == "acmelaw.com")
    check("score_emoji hot", p.score_emoji == "🔴")


def test_scoring() -> None:
    print("\n📊 Scoring Normalizer")
    from shared.scoring import ScoringNormalizer

    n = ScoringNormalizer()
    check("ps 5/5 → 1.0", n.normalize(5, "ps") == 1.0)
    check("ps 1/5 → 0.0", n.normalize(1, "ps") == 0.0)
    check("ps 3/5 → 0.5", n.normalize(3, "ps") == 0.5)
    check("priority hot", n.get_priority_tier(0.9) == "hot")
    check("priority warm", n.get_priority_tier(0.6) == "warm")
    check("priority cold", n.get_priority_tier(0.3) == "cold")

    ranked = n.compare_across_verticals([
        ("Firm A", 5, "ps"),
        ("Brand B", 4, "dtc"),
        ("Firm C", 2, "ps"),
    ])
    check("cross-vertical sort", ranked[0][0] == "Firm A")


def test_formatters() -> None:
    print("\n📝 Output Formatters")
    from shared.base import Prospect
    from shared.output import DiscordFormatter, CRMFormatter

    prospects = [
        Prospect(
            name="Test Firm A",
            url="https://firma.com",
            vertical="ps",
            raw_score=5,
            normalized_score=1.0,
            category="Law Firm",
            location="NYC",
            geo_gaps=["No schema", "No FAQ"],
            emails=["a@firma.com"],
            recommended_action="Add schema markup.",
        ),
        Prospect(
            name="Test Brand B",
            url="https://brandb.com",
            vertical="dtc",
            raw_score=4,
            normalized_score=0.75,
            category="DTC Beauty",
            location="National",
            geo_gaps=["Thin content"],
            recommended_action="Expand product pages.",
        ),
    ]

    discord = DiscordFormatter.format_combined_report(
        {"ps": "PS report", "dtc": "DTC report"},
        prospects,
    )
    check("discord combined len", len(discord) > 100)
    check("discord has hot", "🔥 Hot Prospects" in discord)

    crm = CRMFormatter.format_prospects(prospects)
    check("crm total", crm["total_prospects"] == 2)
    check("crm hot count", crm["by_priority"]["hot"] == 1)
    check("crm warm count", crm["by_priority"]["warm"] == 1)


def test_geo_scoring() -> None:
    print("\n🔬 GEO Scoring Engine")
    from geo_scoring import (
        extract_page_signals,
        parse_robots_for_ai_bots,
        parse_sitemap_preview,
        score_all_dimensions,
        weighted_overall,
        score_to_grade,
    )

    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Site</title>
        <meta property="og:title" content="Test">
        <meta name="twitter:card" content="summary">
        <script type="application/ld+json">{"@type":"LocalBusiness","name":"Test"}</script>
    </head>
    <body>
        <h1>Welcome</h1>
        <h2>Services</h2>
        <h2>About</h2>
        <ul><li>Item 1</li><li>Item 2</li></ul>
        <p>This is a paragraph with enough words to pass the minimum threshold.</p>
        <p>More content here to increase the word count for the scoring engine test.</p>
    </body>
    </html>
    """

    signals, soup = extract_page_signals(sample_html)
    check("signals word_count", signals.word_count >= 20)
    check("signals json_ld", signals.json_ld_count == 1)
    check("signals h1", signals.h1_count == 1)
    check("signals h2", signals.h2_count == 2)
    check("signals og", signals.og_count >= 1)

    blocked = parse_robots_for_ai_bots("User-agent: GPTBot\nDisallow: /")
    check("robots blocks gptbot", "gptbot" in blocked)

    present, sm_type, count = parse_sitemap_preview("<urlset><url></url><url></url></urlset>")
    check("sitemap present", present)
    check("sitemap count", count == 2)

    scores = score_all_dimensions(signals, blocked, True, 10)
    check("dimensions complete", len(scores) == 8)
    check("ai_crawl low", scores["ai_crawl_access"] < 5)

    overall = weighted_overall(scores)
    check("overall numeric", isinstance(overall, float))
    grade, readiness = score_to_grade(overall)
    check("grade letter", grade in ("A", "B", "C", "D", "F"))
    check("readiness label", len(readiness) > 0)


def test_discover_filters() -> None:
    print("\n🔍 Discovery Filters")
    from discover import is_business_url, normalize_url, filter_candidates, extract_base_url

    check("valid biz url", is_business_url("https://acmelaw.com"))
    check("skip google", not is_business_url("https://google.com/search"))
    check("skip linkedin", not is_business_url("https://linkedin.com/in/john"))
    check("normalize http", normalize_url("example.com").startswith("https://"))
    check("extract base", extract_base_url("https://sub.example.com/path") == "https://sub.example.com")

    urls = ["https://a.com", "https://b.com", "https://a.com", "https://google.com/search"]
    filtered = filter_candidates(urls)
    check("filter dedup+skip", len(filtered) == 2)


def test_tools_schema() -> None:
    print("\n🛠️  Tool Schemas")
    from tools import TOOL_SCHEMAS, TOOL_DISPATCH

    names = [t["name"] for t in TOOL_SCHEMAS]
    check("web_search schema", "web_search" in names)
    check("analyze_site_geo schema", "analyze_site_geo" in names)
    check("send_discord_report schema", "send_discord_report" in names)
    check("no slack schema", "send_slack_report" not in names)

    check("dispatch web_search", "web_search" in TOOL_DISPATCH)
    check("dispatch discord", "send_discord_report" in TOOL_DISPATCH)


def test_verticals_test_mode() -> None:
    print("\n🏭 Vertical Test Mode")
    from verticals.professional_services import ProfessionalServicesVertical
    from verticals.dtc_ecommerce import DTCEcommerceVertical

    ps = ProfessionalServicesVertical()
    ps_prospects = ps.discover(count=1, test_mode=True)
    check("ps test mode returns", len(ps_prospects) == 1)
    check("ps test name", ps_prospects[0].name != "")
    check("ps test vertical", ps_prospects[0].vertical == "ps")

    dtc = DTCEcommerceVertical()
    dtc_prospects = dtc.discover(count=1, test_mode=True)
    check("dtc test mode returns", len(dtc_prospects) == 1)
    check("dtc test vertical", dtc_prospects[0].vertical == "dtc")


def test_orchestrator_imports() -> None:
    print("\n🎛️  Orchestrator Imports")
    try:
        import geo_orchestrator
        check("geo_orchestrator imports", True)
    except Exception as e:
        check("geo_orchestrator imports", False, str(e))


def main():
    parser = argparse.ArgumentParser(description="GEO Stack Smoke Test")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    print("=" * 50)
    print("🧪 GEO Discovery Stack — Smoke Test")
    print("=" * 50)

    test_imports()
    test_unified_history()
    test_prospect()
    test_scoring()
    test_formatters()
    test_geo_scoring()
    test_discover_filters()
    test_tools_schema()
    test_verticals_test_mode()
    test_orchestrator_imports()

    print("\n" + "=" * 50)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    print("=" * 50)

    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
