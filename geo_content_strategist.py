#!/usr/bin/env python3
"""
GEO Content Strategist — Daily GEO article → blog post ideation pipeline.

1. Fetches fresh GEO/SEO articles via web search
2. Reads MadTech Growth frameworks from Obsidian vault
3. Cross-references articles against frameworks using LLM
4. Proposes 1-2 blog post ideas with titles, angles, pillar mappings, and citations
5. Saves brief to ~/Desktop/ScottOS/Cron Outputs/ and posts to Discord

Usage:
    python3 geo_content_strategist.py              # Full run
    python3 geo_content_strategist.py --test       # Test mode (mock data)
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

sys.path.insert(0, str(Path(__file__).parent))
from shared.output import DiscordFormatter

# ─── Config ───────────────────────────────────────────────────────────────────

OBSIDIAN_VAULT = Path.home() / "Desktop" / "ScottOS"
FRAMEWORKS_DIR = OBSIDIAN_VAULT / "GEO Frameworks"
OUTPUT_DIR = OBSIDIAN_VAULT / "Cron Outputs"
CONTENT_DIR = OBSIDIAN_VAULT / "Claude Content"

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
NOUS_API_KEY = os.environ.get("NOUS_API_KEY", "")
NOUS_BASE_URL = os.environ.get("NOUS_BASE_URL", "https://gateway.nous.uno/v1")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "moonshotai/kimi-k2.6")

SEARCH_QUERIES = [
    "Generative Engine Optimization GEO 2026",
    "GEO SEO AI search optimization trends",
    "Answer Engine Optimization AEO 2026",
    "ChatGPT Perplexity brand citations search visibility",
    "AI search optimization enterprise brands",
    "agentic commerce protocol MCP ACP UCP 2026",
]


def web_search(query: str, limit: int = 5) -> list[dict]:
    """Fetch web search results via Hermes tool wrapper."""
    try:
        from hermes_tools import web_search as ws
        result = ws(query, limit=limit)
        return result.get("data", {}).get("web", [])
    except Exception as e:
        print(f"  ⚠️ web_search failed for '{query}': {e}")
        return []


def fetch_geo_articles(max_per_query: int = 3) -> list[dict[str, Any]]:
    """Fetch fresh GEO articles from web search (Hermes env) or RSS fallback (local dev)."""
    print("\n" + "=" * 60)
    print("📰 Fetching fresh GEO articles...")
    print("=" * 60 + "\n")

    articles = []
    seen_urls = set()

    # Try Hermes web_search first (available in cron environment)
    hermes_available = True
    try:
        import hermes_tools
    except ImportError:
        hermes_available = False
        print("  ℹ️ hermes_tools not available locally; falling back to RSS/Reddit fetch\n")

    if hermes_available:
        for query in SEARCH_QUERIES:
            results = web_search(query, limit=max_per_query + 2)
            for r in results:
                url = r.get("url", "")
                if not url or url in seen_urls:
                    continue
                skip = ["youtube.com", "podcasts.apple", "audible.com", "schema.org",
                        "llms.txt", "google.com/search", "reddit.com", "twitter.com", "x.com"]
                if any(s in url for s in skip):
                    continue
                seen_urls.add(url)
                articles.append({
                    "title": r.get("title", "Unknown"),
                    "url": url,
                    "source": r.get("source", "Web"),
                    "description": r.get("description", "")[:400],
                })
            print(f"  ✓ '{query[:40]}...' → {len(results)} results")
    else:
        # Local fallback: use RSS feeds
        try:
            from shared.research_fetcher import fetch_all_sources
            stories = fetch_all_sources()
            for s in stories:
                url = s.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                articles.append({
                    "title": s.get("title", "Unknown"),
                    "url": url,
                    "source": s.get("feed_name", s.get("source", "RSS")),
                    "description": s.get("description", "")[:400],
                })
        except Exception as e:
            print(f"  ⚠️ RSS fallback also failed: {e}")

    print(f"\n[content] Total unique articles fetched: {len(articles)}\n")
    return articles


def load_frameworks() -> str:
    """Read all GEO framework files from Obsidian vault."""
    print("📚 Loading GEO frameworks from Obsidian vault...")
    framework_texts = []

    if not FRAMEWORKS_DIR.exists():
        print(f"  ⚠️ Frameworks dir not found: {FRAMEWORKS_DIR}")
        return ""

    for md_file in sorted(FRAMEWORKS_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        # Truncate very long files to stay within context limits
        lines = content.splitlines()
        if len(lines) > 200:
            content = "\n".join(lines[:200]) + "\n...[truncated for brevity]..."
        framework_texts.append(f"--- FILE: {md_file.name} ---\n{content}\n")

    combined = "\n".join(framework_texts)
    print(f"  ✓ Loaded {len(framework_texts)} framework files ({len(combined)} chars)\n")
    return combined


def generate_content_brief(articles: list[dict], frameworks: str) -> dict[str, Any]:
    """Use LLM to cross-reference articles with frameworks and propose blog posts."""
    if not articles:
        return {
            "brief": {
                "date": str(date.today()),
                "articles_scanned": 0,
                "proposed_posts": [],
                "note": "No fresh articles found today.",
            }
        }

    # Build compact article input
    article_texts = []
    for i, a in enumerate(articles[:8], 1):  # cap at 8 to manage context
        article_texts.append(
            f"ARTICLE {i}\n"
            f"Title: {a['title']}\n"
            f"Source: {a['source']}\n"
            f"URL: {a['url']}\n"
            f"Description: {a['description']}\n"
        )

    system_prompt = """\
You are the Chief Content Strategist for MadTech Growth, a GEO (Generative Engine Optimization) advisory firm.

YOUR TASK:
1. Analyze the fresh GEO/SEO articles provided below.
2. Cross-reference each article against the MadTech Growth GEO frameworks.
3. Select the 1-2 MOST relevant articles for content creation — ones that either:
   - Validate or extend a MadTech framework pillar
   - Surface a new trend that maps to client pain points
   - Provide hard data/stats that can anchor a thought-leadership piece
   - Reveal a gap or misconception that MadTech's methodology addresses

4. For each selected article, propose ONE blog post with:
   - title: A sharp, executive-framed headline (max 12 words)
   - hook: The core tension or insight in 1-2 sentences
   - framework_pillar: Which of the 8 GEO Pillars this maps to (or "Agentic Commerce" / "Cross-Pillar")
   - angle: The specific MadTech lens — how we reframe the story (not just summarizing the news)
   - key_sources: List of sources to cite (include the article URL + any frameworks referenced)
   - target_audience: "Professional Services" or "DTC/eCommerce" or "Both"
   - why_timely: Why publish this NOW — what makes it urgent/relevant
   - suggested_cta: What the post should drive readers to do (audit, newsletter, consultation)

RULES:
- Do NOT propose generic "what is GEO" posts. Assume the audience is sophisticated.
- Lead with narrative control, reputation risk, or revenue impact — not tactics.
- Each proposal must explicitly tie back to at least one framework concept.
- If no article is strong enough, say so and explain why.
- Return ONLY valid JSON.

OUTPUT FORMAT:
{
  "brief": {
    "date": "YYYY-MM-DD",
    "articles_scanned": N,
    "proposed_posts": [
      {
        "title": "...",
        "hook": "...",
        "framework_pillar": "...",
        "angle": "...",
        "key_sources": ["..."],
        "target_audience": "...",
        "why_timely": "...",
        "suggested_cta": "...",
        "source_article": {"title": "...", "url": "..."}
      }
    ],
    "rejected_articles": [
      {"title": "...", "reason": "Too tactical / already covered / off-brand / etc."}
    ],
    "content_calendar_note": "One-line strategic takeaway for the week"
  }
}
"""

    user_prompt = (
        f"Today is {date.today().strftime('%B %d, %Y')}.\n\n"
        f"--- MADTECH GROWTH GEO FRAMEWORKS ---\n{frameworks}\n\n"
        f"--- FRESH ARTICLES ---\n"
        + "\n---\n".join(article_texts)
    )

    client = OpenAI(base_url=NOUS_BASE_URL, api_key=NOUS_API_KEY)

    print("[content] Sending to LLM for cross-reference analysis...")
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        max_tokens=8192,
        messages=[
            {"role": "user", "content": system_prompt + "\n\n" + user_prompt},
        ],
    )

    output = response.choices[0].message.content or "{}"

    try:
        data = json.loads(output)
        if "brief" not in data and "proposed_posts" in data:
            data = {"brief": data}
        return data
    except json.JSONDecodeError as e:
        print(f"  ⚠️ LLM returned invalid JSON: {e}")
        return {
            "brief": {
                "date": str(date.today()),
                "articles_scanned": len(articles),
                "proposed_posts": [],
                "note": "Error generating brief.",
                "_raw_output": output[:800],
            }
        }


def save_brief_markdown(brief: dict[str, Any]) -> str:
    """Save the content brief as a markdown file in Obsidian vault."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    b = brief.get("brief", brief)
    date_str = b.get("date", str(date.today()))
    filepath = OUTPUT_DIR / f"geo_content_brief_{date_str}.md"

    lines = [
        f"---",
        f"type: brief",
        f"topic: GEO Content Strategy",
        f"updated: {date_str}",
        f"---",
        f"",
        f"# GEO Content Brief — {date_str}",
        f"",
        f"**Articles scanned:** {b.get('articles_scanned', 'N/A')}",
        f"",
        f"**Content calendar note:** {b.get('content_calendar_note', 'N/A')}",
        f"",
        f"---",
        f"",
    ]

    posts = b.get("proposed_posts", [])
    if not posts:
        lines.append("_No blog post proposals today._")
        lines.append("")
        if b.get("note"):
            lines.append(f"**Note:** {b['note']}")
    else:
        for i, post in enumerate(posts, 1):
            lines.append(f"## Proposal {i}: {post.get('title', 'Untitled')}")
            lines.append("")
            lines.append(f"**Hook:** {post.get('hook', '')}")
            lines.append("")
            lines.append(f"**Framework pillar:** `{post.get('framework_pillar', 'N/A')}`")
            lines.append("")
            lines.append(f"**Angle:** {post.get('angle', '')}")
            lines.append("")
            lines.append(f"**Target audience:** {post.get('target_audience', '')}")
            lines.append("")
            lines.append(f"**Why timely:** {post.get('why_timely', '')}")
            lines.append("")
            lines.append(f"**Suggested CTA:** {post.get('suggested_cta', '')}")
            lines.append("")

            sources = post.get("key_sources", [])
            if sources:
                lines.append("**Key sources:**")
                for src in sources:
                    lines.append(f"- {src}")
                lines.append("")

            src_article = post.get("source_article", {})
            if src_article:
                lines.append(f"**Source article:** [{src_article.get('title', 'Link')}]({src_article.get('url', '')})")
                lines.append("")

            lines.append("---")
            lines.append("")

    rejected = b.get("rejected_articles", [])
    if rejected:
        lines.append("## Rejected Articles")
        lines.append("")
        for r in rejected:
            lines.append(f"- **{r.get('title', 'Unknown')}** — {r.get('reason', '')}")
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    print(f"[content] Saved brief: {filepath}")

    # Also copy to Claude Content for easy editing
    content_filepath = CONTENT_DIR / f"Content Brief {date_str}.md"
    content_filepath.write_text("\n".join(lines), encoding="utf-8")
    print(f"[content] Copied to: {content_filepath}")

    return str(filepath)


def format_discord_brief(brief: dict[str, Any]) -> str:
    """Format the content brief for Discord."""
    b = brief.get("brief", brief)
    lines = [
        f"**✍️ GEO Content Brief — {b.get('date', str(date.today()))}**",
        f"\n_{b.get('content_calendar_note', '')}_\n",
    ]

    posts = b.get("proposed_posts", [])
    if not posts:
        lines.append("_No strong blog post angles today._")
    else:
        for i, post in enumerate(posts, 1):
            lines.append(f"**{i}. {post.get('title', 'Untitled')}**")
            lines.append(f"> {post.get('hook', '')}")
            lines.append(f"> 🏛️ **Pillar:** {post.get('framework_pillar', 'N/A')} | **Audience:** {post.get('target_audience', 'N/A')}")
            src = post.get("source_article", {})
            if src:
                lines.append(f"> 🔗 [{src.get('title', 'Source')}]({src.get('url', '')})")
            lines.append("")

    return "\n".join(lines)


def run_content_strategist(test_mode: bool = False) -> dict[str, Any]:
    """Run the full content strategist pipeline."""
    if test_mode:
        articles = [
            {
                "title": "Google Expands AI Overviews to 100+ Countries",
                "url": "https://searchengineland.com/google-ai-overviews-expansion-123456",
                "source": "Search Engine Land",
                "description": "Google announced that AI Overviews will now appear in search results across more than 100 countries, fundamentally changing how brands must think about visibility.",
            },
            {
                "title": "McKinsey: AI Agents Will Mediate $3–5T in Commerce by 2030",
                "url": "https://www.mckinsey.com/agentic-commerce-2030",
                "source": "McKinsey",
                "description": "New McKinsey research projects that autonomous AI agents will handle trillions in commerce transactions within five years, with early-adopter brands capturing disproportionate share.",
            },
        ]
    else:
        articles = fetch_geo_articles()

    frameworks = load_frameworks()
    brief = generate_content_brief(articles, frameworks)
    filepath = save_brief_markdown(brief)

    # Post to Discord
    if DISCORD_WEBHOOK_URL and not test_mode:
        discord_msg = format_discord_brief(brief)
        DiscordFormatter.send_raw(discord_msg, DISCORD_WEBHOOK_URL, username="GEO Content Bot")
        print("[content] Posted to Discord.")
    elif test_mode:
        print("\n--- DISCORD PREVIEW ---\n")
        print(format_discord_brief(brief))
        print("\n--- END PREVIEW ---\n")

    print(f"[content] Done. Brief saved to: {filepath}")
    return brief


def main():
    parser = argparse.ArgumentParser(description="GEO Content Strategist")
    parser.add_argument("--test", action="store_true", help="Test mode with mock data")
    args = parser.parse_args()

    run_content_strategist(test_mode=args.test)


if __name__ == "__main__":
    main()
