"""
LLM-as-judge: validate that a discovered Prospect actually fits the ICP.

The discovery agent self-reports a raw_score, but it can hallucinate or
include off-target firms. This module runs a second, cheap LLM pass that
scores ICP fit on a 0.0-1.0 scale with a one-line rationale.

Usage:
    from shared.judge import judge_prospects
    judged = judge_prospects(prospects, vertical_key="ps")
    # Each prospect gets `judge_score` and `judge_rationale` attached to
    # _raw_analysis. Filter by score before passing downstream.
"""

import json
from typing import Optional

from shared.base import Prospect
from shared.config import DEFAULT_MODEL, call_with_retry, get_openai_client

ICP_DEFINITIONS = {
    "ps": (
        "NYC-metro professional services firm (law, accounting, consulting, "
        "wealth management). Target size: 10-200 employees. Reputation-sensitive. "
        "NOT: solo practitioners, national chains, government, non-profits."
    ),
    "dtc": (
        "Direct-to-consumer / eCommerce brand with $100M+ annual revenue. "
        "Often Shopify or custom stack. Consumer-facing, brand-driven. "
        "NOT: B2B SaaS, marketplaces, sub-$10M brands, dropshippers."
    ),
}


def _judge_prompt(prospect: Prospect, icp: str) -> str:
    return f"""\
You are validating an inbound prospect for an ICP fit check.

ICP: {icp}

Candidate:
- Name: {prospect.name}
- URL: {prospect.url}
- Category: {prospect.category or "(unknown)"}
- Location: {prospect.location or "(unknown)"}
- Revenue indicator: {prospect.revenue_indicator or "(unknown)"}

Return a JSON object only:
{{"score": 0.0-1.0, "rationale": "one short sentence"}}

Scoring guide:
- 1.0: clearly in ICP, high-confidence match
- 0.7-0.9: likely fit, minor uncertainty
- 0.4-0.6: ambiguous; could go either way
- 0.0-0.3: clear miss (wrong vertical, wrong size, wrong geo)
"""


def judge_prospect(prospect: Prospect, vertical_key: str,
                   model: str = DEFAULT_MODEL) -> tuple[float, str]:
    """Score a single prospect 0.0-1.0 for ICP fit. Returns (score, rationale)."""
    icp = ICP_DEFINITIONS.get(vertical_key, "")
    if not icp:
        return 0.5, f"no ICP definition for vertical={vertical_key}"

    client = get_openai_client()

    try:
        response = call_with_retry(
            lambda: client.chat.completions.create(
                model=model,
                max_tokens=200,
                messages=[
                    {"role": "system", "content": "You are a precise ICP-fit judge. Return only JSON."},
                    {"role": "user", "content": _judge_prompt(prospect, icp)},
                ],
            ),
            label=f"judge {prospect.name[:30]}",
        )
        raw = (response.choices[0].message.content or "").strip()

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        data = json.loads(raw)
        score = float(data.get("score", 0.5))
        rationale = str(data.get("rationale", ""))[:200]
        return max(0.0, min(1.0, score)), rationale
    except Exception as e:
        print(f"    [judge] failed for {prospect.name}: {e}", flush=True)
        return 0.5, f"judge_error: {type(e).__name__}"


def judge_prospects(prospects: list[Prospect], vertical_key: str,
                    min_score: float = 0.0) -> list[Prospect]:
    """
    Score all prospects, attach judge_score + judge_rationale to _raw_analysis,
    and filter out anything below `min_score`. Default min_score=0.0 keeps all
    prospects but tags them — caller decides the cutoff.
    """
    if not prospects:
        return []

    print(f"\n[judge] Scoring {len(prospects)} prospect(s) for ICP fit (vertical={vertical_key})...", flush=True)
    kept: list[Prospect] = []
    for p in prospects:
        score, rationale = judge_prospect(p, vertical_key)
        p._raw_analysis["judge_score"] = score
        p._raw_analysis["judge_rationale"] = rationale
        marker = "✓" if score >= 0.7 else ("~" if score >= 0.4 else "✗")
        print(f"  {marker} {p.name}: {score:.2f} — {rationale}", flush=True)
        if score >= min_score:
            kept.append(p)

    dropped = len(prospects) - len(kept)
    if dropped:
        print(f"[judge] Dropped {dropped} prospect(s) below min_score={min_score}", flush=True)
    return kept
