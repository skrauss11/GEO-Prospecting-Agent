#!/usr/bin/env python3
"""
dtc_discovery.py — DTC / eCommerce GEO Prospect Discovery
Finds, analyzes, and ranks 5 DTC consumer brands ($100M+ revenue) as GEO prospects.
Output is Discord-formatted markdown printed to stdout for cron delivery.

Usage:
    python3 dtc_discovery.py           # live run
    python3 dtc_discovery.py --test    # print to stdout only
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

VERTICALS = [
    "DTC Apparel & Fashion",
    "DTC Beauty & Cosmetics",
    "DTC Health & Wellness",
    "DTC Food & Beverage",
    "DTC Home & Lifestyle",
]

SYSTEM_PROMPT = """\
You are a GEO (Generative Engine Optimization) prospecting agent for MadTech Growth,
a B2B agency that helps consumer brands become visible to AI search engines
(ChatGPT, Perplexity, Google AI Overviews, etc.).

## YOUR TASK
Find, analyze, and rank **5 DTC/eCommerce consumer brands** as GEO prospects.
For each brand:
1. Search for it (web_search) — confirm it's a real DTC brand
2. Analyze its AI visibility (analyze_site_geo)
3. Extract contact info (extract_contacts)
4. Score it 1-5 on GEO opportunity

## TARGET CRITERIA
- **Verticals**: DTC apparel/fashion, beauty/cosmetics, health/wellness, food/beverage, home goods
- **Revenue**: $100M+ estimated — look for: appearing in "Top DTC Brands" lists,
  Shark Tank deals, major press/coverage, visible investor backing, large social followings
- **Geography**: US-focused brands (national reach, not local)
- **Variety**: Cover at least 3 different DTC categories across your 5 picks

## GEO SCORING (1-5)
1 — Low: Already has strong AI visibility (rich structured data, product schema, FAQ)
2 — Some: Partial structured data (maybe product schema) but incomplete overall
3 — Moderate: Notable gaps, basic meta tags but no JSON-LD product schema, no FAQ,
  no AI-optimized content
4 — Strong: Large DTC brand with almost no structured data beyond basic meta,
  no FAQ section, thin product descriptions, blocks AI bots
5 — Top Prospect: Major DTC brand ($100M+) with ZERO product schema,
  no FAQ content, thin AI-visible copy, and/or AI bots blocked in robots.txt.
  These brands are losing traffic to AI-powered shopping recommendations.

## PREVIOUSLY REPORTED (dedup — do not repeat these exact URLs)
{history}

## OUTPUT FORMAT
After analyzing all 5 brands, output a Discord-formatted report using markdown.

Format:
```
**🛍️ DTC/eCommerce GEO Prospects — {date}**

Found 5 prospects across {{X}} verticals.

---

### ⬤ [Brand Name](URL) — Category | est. $XXXM revenue
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
    return history.get_urls_for_vertical("dtc")


def save_history(urls: list[str]) -> None:
    history = UnifiedHistory(HISTORY_FILE)
    history.add_urls("dtc", urls)


def extract_urls(text: str) -> list[str]:
    import re
    from urllib.parse import urlparse
    pattern = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+')
    skip = {"duckduckgo.com", "google.com", "linkedin.com", "facebook.com",
            "twitter.com", "instagram.com", "youtube.com", "yelp.com", "bing.com",
            "amazon.com", "shopify.com"}
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
            tool_results = []
            for block in response.choices[0].message.tool_calls:
                handler = TOOL_DISPATCH.get(block.function.name)
                result = handler(json.loads(block.function.arguments)) if handler else f"Unknown tool: {block.function.name}"
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": block.id,
                    "content": json.dumps(result) if isinstance(result, dict) else str(result),
                })
            messages.append(response.choices[0].message)
            messages.append({"role": "user", "content": json.dumps(tool_results)})
        else:
            final = response.choices[0].message.content or ""
            return final

    return "Agent reached maximum turns."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    today = date.today().strftime("%B %d, %Y")
    history = load_history()

    print(f"[dtc_discovery] DTC/eCommerce GEO — {today}", flush=True)
    print(f"  Mode: {'TEST' if args.test else 'LIVE → Discord'}", flush=True)

    prompt = (
        f"Today is {today}. "
        f"{'TEST RUN — print the report to stdout.' if args.test else 'Output the full report as Discord markdown printed to stdout — it will be delivered to #geo-prospects automatically.'}\n\n"
        "Find, analyze, and rank 5 DTC/eCommerce brands with $100M+ revenue. "
        "Cover at least 3 different DTC categories. "
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
