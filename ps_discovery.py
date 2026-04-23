#!/usr/bin/env python3
"""
ps_discovery.py — Professional Services GEO Prospect Discovery
Finds, analyzes, and ranks 5 professional services firms as GEO prospects.
Output is Discord-formatted markdown printed to stdout for cron delivery.

Usage:
    python3 ps_discovery.py           # live run
    python3 ps_discovery.py --test     # print to stdout only
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))
from tools import TOOL_SCHEMAS, TOOL_DISPATCH
from shared.history import UnifiedHistory

load_dotenv(override=True)

NOUS_API_KEY = os.environ.get("NOUS_API_KEY", "")
NOUS_BASE_URL = os.environ.get("NOUS_BASE_URL", "https://gateway.nous.uno/v1")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "moonshotai/kimi-k2.6")

HISTORY_FILE = Path(__file__).parent / "data" / "discovery_history.json"

# Vertical focus: law firms (the universal gap vertical), accounting, consulting, finance
VERTICALS = [
    "Law Firms (Personal Injury, Corporate, Immigration, Real Estate)",
    "Accounting & CPA Firms",
    "Management Consulting",
    "Financial Advisors & Wealth Management",
]

SYSTEM_PROMPT = """\
You are a GEO (Generative Engine Optimization) prospecting agent for MadTech Growth,
a B2B agency that helps businesses become visible to AI search engines
(ChatGPT, Perplexity, Google AI Overviews, Claude for search, etc.).

## YOUR TASK
Find, analyze, and rank **5 professional services businesses** as GEO prospects.
For each business:
1. Search for it (web_search)
2. Confirm it's a real business with a public website
3. Analyze its AI visibility (analyze_site_geo)
4. Extract contact info (extract_contacts)
5. Score it 1-5 on GEO opportunity

## TARGET CRITERIA
- **Verticals**: Law firms, accounting/CPA firms, management consulting, financial advisors
- **Location**: NYC metro (Manhattan, Brooklyn, Queens, Bronx, Staten Island, Westchester, Long Island, Northern NJ)
- **Size**: $10M+ revenue indicators — multiple attorneys/partners, large team pages,
  presence on industry rankings, enterprise-grade website
- **Variety**: Pick from DIFFERENT verticals (don't put all 5 in the same category)
- **Law firms are PRIORITY** — they have the most consistent GEO gap (zero Schema/JSON-LD)

## GEO SCORING (1-5)
1 — Low: Already strong AI visibility (rich structured data, FAQ, allows AI bots)
2 — Some: Minor gaps, some structured data but incomplete
3 — Moderate: Notable gaps, basic meta tags but no JSON-LD or FAQ content
4 — Strong: Large firm with almost no structured data, no FAQ, blocks AI bots
5 — Top Prospect: Major established firm with ZERO AI visibility optimization.
  No JSON-LD, no FAQ, thin content, and/or blocks AI crawlers.
  **Law firms scoring 4-5 are ideal for MadTech Growth outreach.**

## PREVIOUSLY REPORTED (dedup — do not repeat these exact URLs)
{history}

## OUTPUT FORMAT
After analyzing all 5 businesses, output a Discord-formatted report using markdown.
Print it to stdout — it will be delivered to Discord automatically.

Format:
```
**🔍 Professional Services GEO Prospects — {date}**

Found 5 prospects across {{X}} verticals.

---

### ⬤ [Company Name](URL) — Vertical | NYC Metro
**GEO Score: X/5** [red circle for 4-5, yellow for 3, green for 1-2]
- Key gaps: bullet list of 2-3 specific AI visibility failures
- Contacts: email(s), phone(s), or LinkedIn
- Recommended GEO action: 1-2 sentence strategy

---
[repeat for each prospect]

---
_Scored by MadTech Growth GEO Agent · {date}_
```
"""


def load_history() -> list[str]:
    history = UnifiedHistory(HISTORY_FILE)
    return history.get_urls_for_vertical("ps")


def save_history(urls: list[str]) -> None:
    history = UnifiedHistory(HISTORY_FILE)
    history.add_urls("ps", urls)


def extract_urls(text: str) -> list[str]:
    import re
    from urllib.parse import urlparse
    pattern = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+')
    skip = {"duckduckgo.com", "google.com", "linkedin.com", "facebook.com",
            "twitter.com", "instagram.com", "youtube.com", "yelp.com", "bing.com"}
    found = []
    for u in pattern.findall(text):
        parsed = urlparse(u)
        domain = parsed.netloc.replace("www.", "")
        if domain and domain not in skip:
            base = f"{parsed.scheme}://{parsed.netloc}"
            if base not in found:
                found.append(base)
    return found


def run_agent(user_query: str, history: list[str], max_turns: int = 30) -> str:
    client = OpenAI(base_url=NOUS_BASE_URL, api_key=NOUS_API_KEY)

    history_str = "\n".join(f"- {u}" for u in history[-50:]) if history else "None yet."
    system = SYSTEM_PROMPT.format(
        date=date.today().strftime("%B %d, %Y"),
        history=history_str,
    )

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user_query}]

    for turn in range(max_turns):
        print(f"  [turn {turn + 1}]", flush=True)
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            max_tokens=8096,
            messages=messages,
            tools=TOOL_SCHEMAS,
        )

        if response.choices[0].finish_reason == "tool_calls":
            assistant_message = response.choices[0].message
            messages.append(assistant_message)
            
            for block in assistant_message.tool_calls:
                handler = TOOL_DISPATCH.get(block.function.name)
                if handler:
                    result = handler(json.loads(block.function.arguments))
                    tool_content = json.dumps(result) if isinstance(result, dict) else str(result)
                else:
                    tool_content = f"Unknown tool: {block.function.name}"
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": block.id,
                    "content": tool_content,
                })
        else:
            final = response.choices[0].message.content or ""
            return final

    return "Agent reached maximum turns."


def score_emoji(score: int) -> str:
    if score >= 4:
        return "🔴"
    elif score == 3:
        return "🟡"
    else:
        return "🟢"


def format_discord(report_text: str) -> str:
    """Parse the agent's raw output and reformat as clean Discord markdown."""
    # The agent just prints the Discord-formatted output directly
    return report_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    today = date.today().strftime("%B %d, %Y")
    history = load_history()

    print(f"[ps_discovery] Professional Services GEO — {today}", flush=True)
    print(f"  Mode: {'TEST' if args.test else 'LIVE → Discord'}", flush=True)

    prompt = (
        f"Today is {today}. "
        f"{'TEST RUN — print the report to stdout, do NOT post anywhere.' if args.test else 'Output the full report as Discord markdown printed to stdout — it will be delivered to #geo-prospects automatically.'}\n\n"
        "Find, analyze, and rank 5 Professional Services firms. Prioritize law firms. "
        "Output the Discord-formatted report as described in the system prompt."
    )

    report = run_agent(prompt, history)

    found_urls = extract_urls(report)
    if found_urls:
        save_history(found_urls)
        print(f"\n[saved] {len(found_urls)} URLs to dedup history.", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("REPORT OUTPUT:", flush=True)
    print("=" * 60, flush=True)
    print(report, flush=True)


if __name__ == "__main__":
    main()
