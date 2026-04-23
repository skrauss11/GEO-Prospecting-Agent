"""
Research Summarizer — Uses LLM to turn raw stories into actionable GEO intel.
"""

import json
import os
from datetime import date
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

# Nous API config
NOUS_API_KEY = os.environ.get("NOUS_API_KEY", "")
NOUS_BASE_URL = os.environ.get("NOUS_BASE_URL", "https://gateway.nous.uno/v1")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "moonshotai/kimi-k2.6")


SYSTEM_PROMPT = """\
You are a GEO (Generative Engine Optimization) research analyst for MadTech Growth.

YOUR TASK: Analyze SEO/GEO news stories and produce a daily briefing with actionable outreach angles.

For each story you must produce:
1. HEADLINE — The core news in 10 words or fewer
2. SUMMARY — 2 sentences explaining what changed and why it matters
3. OUTREACH ANGLES — One angle per vertical:
   - Professional Services (law firms, accounting, consulting, finance)
   - DTC/eCommerce ($100M+ brands)
4. EMAIL HOOK — A 1-sentence cold email opener tailored to each vertical

RULES:
- Be specific. No generic advice like "optimize your site."
- Focus on PAIN or FEAR or URGENCY — what does this trend COST the prospect?
- Each email hook should feel like it was written 5 minutes ago, not copied from a template.
- If a story is not relevant to GEO/SEO, skip it.
- Return ONLY valid JSON.

OUTPUT FORMAT:
{
  "briefing": {
    "date": "YYYY-MM-DD",
    "top_stories": [
      {
        "headline": "...",
        "summary": "...",
        "source": "...",
        "url": "...",
        "angles": {
          "professional_services": "...",
          "dtc_ecommerce": "..."
        },
        "hooks": {
          "professional_services": "...",
          "dtc_ecommerce": "..."
        }
      }
    ],
    "theme_of_the_day": "One-line summary of the biggest trend across all stories"
  }
}
"""


def summarize_stories(stories: list[dict[str, Any]], max_stories: int = 5) -> dict[str, Any]:
    """
    Send stories to LLM and get back structured briefing.

    Args:
        stories: Raw stories from fetcher
        max_stories: Cap number of stories sent to LLM (to fit context)

    Returns:
        Parsed JSON briefing dict
    """
    if not stories:
        return {
            "briefing": {
                "date": str(date.today()),
                "top_stories": [],
                "theme_of_the_day": "No fresh stories today.",
            }
        }

    # Build compact input for LLM
    story_texts = []
    for i, s in enumerate(stories[:max_stories], 1):
        snippet = s.get("description", "")[:300]
        story_texts.append(
            f"STORY {i}\n"
            f"Source: {s.get('feed_name', 'Unknown')}\n"
            f"Title: {s.get('title', '')}\n"
            f"URL: {s.get('url', '')}\n"
            f"Snippet: {snippet}\n"
        )

    user_prompt = (
        f"Today is {date.today().strftime('%B %d, %Y')}.\n\n"
        f"Analyze these {len(story_texts)} SEO/GEO stories and produce a daily briefing.\n\n"
        + "\n---\n".join(story_texts)
    )

    client = OpenAI(base_url=NOUS_BASE_URL, api_key=NOUS_API_KEY)

    print("[research] Sending to LLM for summarization...")
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        max_tokens=8192,
        messages=[
            {"role": "user", "content": SYSTEM_PROMPT + "\n\n" + user_prompt},
        ],
    )

    output = response.choices[0].message.content or "{}"

    try:
        data = json.loads(output)
        # Normalize key if LLM wraps differently
        if "briefing" not in data and "top_stories" in data:
            data = {"briefing": data}
        return data
    except json.JSONDecodeError as e:
        print(f"  ⚠️ LLM returned invalid JSON: {e}")
        return {
            "briefing": {
                "date": str(date.today()),
                "top_stories": [],
                "theme_of_the_day": "Error generating briefing.",
                "_raw_output": output[:500],
            }
        }


def format_discord_briefing(briefing: dict[str, Any]) -> str:
    """Format the briefing dict into a Discord message."""
    b = briefing.get("briefing", briefing)
    lines = [
        f"**📰 GEO Daily Briefing — {b.get('date', str(date.today()))}**",
        f"\n_Theme of the day: {b.get('theme_of_the_day', 'N/A')}_\n",
    ]

    for story in b.get("top_stories", [])[:3]:
        lines.append(f"**{story.get('headline', 'Untitled')}**")
        lines.append(f"> {story.get('summary', '')}")
        lines.append(f"> 🔗 {story.get('url', '')}")

        ps_angle = story.get("angles", {}).get("professional_services", "")
        ps_hook = story.get("hooks", {}).get("professional_services", "")
        if ps_angle:
            lines.append(f"> 🏢 **PS angle:** {ps_angle}")
        if ps_hook:
            lines.append(f"> ✉️ *Hook:* {ps_hook}")

        dtc_angle = story.get("angles", {}).get("dtc_ecommerce", "")
        dtc_hook = story.get("hooks", {}).get("dtc_ecommerce", "")
        if dtc_angle:
            lines.append(f"> 🛒 **DTC angle:** {dtc_angle}")
        if dtc_hook:
            lines.append(f"> ✉️ *Hook:* {dtc_hook}")

        lines.append("")  # spacer

    return "\n".join(lines)


def save_briefing_markdown(briefing: dict[str, Any], out_dir: Any) -> str:
    """Save the full briefing as a markdown file."""
    from pathlib import Path
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    b = briefing.get("briefing", briefing)
    date_str = b.get("date", str(date.today()))
    filepath = out_dir / f"{date_str}_briefing.md"

    lines = [
        f"# GEO Daily Briefing — {date_str}",
        "",
        f"**Theme of the day:** {b.get('theme_of_the_day', 'N/A')}",
        "",
        "---",
        "",
    ]

    for i, story in enumerate(b.get("top_stories", []), 1):
        lines.append(f"## {i}. {story.get('headline', 'Untitled')}")
        lines.append("")
        lines.append(f"**Summary:** {story.get('summary', '')}")
        lines.append("")
        lines.append(f"**Source:** [{story.get('source', 'Unknown')}]({story.get('url', '')})")
        lines.append("")

        angles = story.get("angles", {})
        hooks = story.get("hooks", {})

        lines.append("### Outreach Angles")
        lines.append("")
        if angles.get("professional_services"):
            lines.append(f"**Professional Services:** {angles['professional_services']}")
        if hooks.get("professional_services"):
            lines.append(f"*Email hook:* {hooks['professional_services']}")
        lines.append("")
        if angles.get("dtc_ecommerce"):
            lines.append(f"**DTC/eCommerce:** {angles['dtc_ecommerce']}")
        if hooks.get("dtc_ecommerce"):
            lines.append(f"*Email hook:* {hooks['dtc_ecommerce']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    print(f"[research] Saved briefing: {filepath}")
    return str(filepath)
