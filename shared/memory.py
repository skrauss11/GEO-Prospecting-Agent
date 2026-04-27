"""
Cross-run memory for the discovery agent.

Reads recent prospect history and builds a compact context block summarizing
what the agent has already found — categories saturated, common gaps, top
performers — so each run can build on prior knowledge instead of starting
amnesiac.

Used as an optional system-prompt addendum for `run_discovery_agent`.
"""

from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from shared.history import UnifiedHistory


def _parse_iso(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _recent_prospects(history: UnifiedHistory, vertical_key: str, days: int) -> list[dict]:
    """Return prospect records for `vertical_key` discovered within the last `days`."""
    cutoff = datetime.now() - timedelta(days=days)
    out = []
    for rec in history._data.get("prospects", []):
        if rec.get("vertical") != vertical_key:
            continue
        ts_str = rec.get("_history_added") or rec.get("discovered_at") or ""
        ts = _parse_iso(ts_str)
        if ts is None or ts >= cutoff:
            out.append(rec)
    return out


def build_memory_context(
    history: UnifiedHistory,
    vertical_key: str,
    days: int = 7,
    top_categories: int = 5,
    top_gaps: int = 5,
    top_performers: int = 3,
) -> str:
    """
    Build a markdown context block summarizing recent discoveries for this vertical.
    Returns an empty string if there's nothing useful to report yet.
    """
    recent = _recent_prospects(history, vertical_key, days)
    if not recent:
        return ""

    categories = Counter()
    locations = Counter()
    gaps = Counter()
    scores: list[float] = []
    by_score: list[tuple[float, str, str]] = []  # (score, name, url)

    for rec in recent:
        attrs = rec.get("attributes", {}) or {}
        if attrs.get("category"):
            categories[attrs["category"]] += 1
        if attrs.get("location"):
            locations[attrs["location"]] += 1

        for gap in (rec.get("geo_analysis", {}) or {}).get("gaps", []) or []:
            gaps[gap] += 1

        score = (rec.get("scoring", {}) or {}).get("normalized_score")
        if isinstance(score, (int, float)):
            scores.append(float(score))
            by_score.append((float(score), rec.get("name", "?"), rec.get("url", "")))

    avg_score = sum(scores) / len(scores) if scores else 0.0
    by_score.sort(reverse=True)

    lines = [
        f"## Prior Discovery Memory — last {days} days",
        f"You have already discovered **{len(recent)}** prospects in this vertical.",
        f"Average normalized score: **{avg_score:.2f}** (1.0 is best).",
        "",
    ]

    if categories:
        top_cats = categories.most_common(top_categories)
        lines.append("**Categories already covered (count):**")
        for cat, n in top_cats:
            lines.append(f"- {cat}: {n}")
        lines.append("")
        lines.append(
            "Bias toward categories NOT in this list to broaden coverage. "
            "Avoid re-saturating top categories unless quality has been low."
        )
        lines.append("")

    if locations:
        top_locs = locations.most_common(3)
        lines.append("**Locations already covered:** "
                     + ", ".join(f"{loc} ({n})" for loc, n in top_locs))
        lines.append("")

    if gaps:
        top_gap_list = gaps.most_common(top_gaps)
        lines.append("**Most-common GEO gaps observed:**")
        for gap, n in top_gap_list:
            lines.append(f"- {gap} ({n}×)")
        lines.append("")
        lines.append(
            "These gaps are now baseline expectations. Surface MORE NUANCED "
            "gaps (specific schema misuse, llms.txt presence/quality, citation "
            "patterns) when they apply — generic gaps are less useful to Scott."
        )
        lines.append("")

    if by_score and by_score[0][0] >= 0.7:
        lines.append(f"**Top prior performers (do NOT re-discover these):**")
        for score, name, url in by_score[:top_performers]:
            lines.append(f"- {name} ({url}) — score {score:.2f}")
        lines.append("")

    if avg_score < 0.5 and len(scores) >= 5:
        lines.append(
            "⚠️ Recent average score is low — vary your search query angle "
            "from prior runs (try different sub-niches, geographies, or revenue tiers)."
        )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
