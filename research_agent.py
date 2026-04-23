#!/usr/bin/env python3
"""
Research Agent — Daily GEO/SEO intel pipeline.

Fetches fresh content from RSS + Reddit, summarizes with LLM,
generates outreach angles + email hooks, saves locally, posts to Discord.

Usage:
    python3 research_agent.py              # Full run
    python3 research_agent.py --test       # Test mode (mock data)
    python3 research_agent.py --query "law firms"  # On-demand angle lookup
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, str(Path(__file__).parent))

from shared.research_fetcher import fetch_all_sources
from shared.research_summarizer import summarize_stories, format_discord_briefing, save_briefing_markdown
from shared.output import DiscordFormatter

# Config
RESEARCH_DIR = Path(__file__).parent / "research"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")


def run_daily_research(test_mode: bool = False) -> dict[str, Any]:
    """Run the full research pipeline."""
    print("\n" + "=" * 60)
    print("📰 GEO Research Agent — Daily Briefing")
    print("=" * 60 + "\n")

    if test_mode:
        stories = [
            {
                "title": "Google Expands AI Overviews to 100+ Countries",
                "url": "https://searchengineland.com/google-ai-overviews-expansion-123456",
                "description": "Google announced that AI Overviews will now appear in search results across more than 100 countries...",
                "published": "2026-04-23",
                "source": "rss",
                "feed_name": "Search Engine Land",
            },
            {
                "title": "Local SEO Ranking Factors Report 2026 Released",
                "url": "https://www.searchenginejournal.com/local-seo-ranking-factors-2026/",
                "description": "The annual survey reveals that proximity and reviews continue to dominate local pack rankings...",
                "published": "2026-04-23",
                "source": "rss",
                "feed_name": "Search Engine Journal",
            },
        ]
    else:
        stories = fetch_all_sources()

    if not stories:
        print("⚠️ No stories fetched. Skipping briefing.")
        return {}

    # Summarize with LLM
    briefing = summarize_stories(stories)

    # Save markdown locally
    filepath = save_briefing_markdown(briefing, RESEARCH_DIR)

    # Post to Discord
    if DISCORD_WEBHOOK_URL and not test_mode:
        discord_msg = format_discord_briefing(briefing)
        DiscordFormatter.send_raw(discord_msg, DISCORD_WEBHOOK_URL)
        print("[research] Posted to Discord.")
    elif test_mode:
        print("\n--- DISCORD PREVIEW ---\n")
        print(format_discord_briefing(briefing))
        print("\n--- END PREVIEW ---\n")

    print(f"[research] Done. Briefing saved to: {filepath}")
    return briefing


def on_demand_query(query: str) -> str:
    """Generate an outreach angle for a specific topic or vertical."""
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(override=True)

    NOUS_API_KEY = os.environ.get("NOUS_API_KEY", "")
    NOUS_BASE_URL = os.environ.get("NOUS_BASE_URL", "https://gateway.nous.uno/v1")
    DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "moonshotai/kimi-k2.6")

    client = OpenAI(base_url=NOUS_BASE_URL, api_key=NOUS_API_KEY)

    prompt = f"""\
Generate a cold email hook for a GEO (Generative Engine Optimization) agency reaching out to {query}.

Requirements:
- Reference a CURRENT or RECENT SEO/GEO trend (AI Overviews, zero-click search, SGE, etc.)
- Make it specific to {query}
- Lead with PAIN or FEAR, not a pitch
- Keep it to 1-2 sentences
- Sound like a consultant who just noticed something, not a salesperson

Return ONLY the hook text.
"""

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    hook = response.choices[0].message.content or ""
    return hook.strip()


def main():
    parser = argparse.ArgumentParser(description="GEO Research Agent")
    parser.add_argument("--test", action="store_true", help="Test mode with mock data")
    parser.add_argument("--query", type=str, help="On-demand outreach hook for a topic/vertical")
    args = parser.parse_args()

    if args.query:
        hook = on_demand_query(args.query)
        print(f"\n💡 Hook for '{args.query}':\n")
        print(hook)
        print()
        return

    run_daily_research(test_mode=args.test)


if __name__ == "__main__":
    main()
