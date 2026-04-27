#!/usr/bin/env python3
"""
geo_daily_briefing.py
Compiles today's GEO knowledge base snapshot and sends it as a briefing to Discord.
Run: python3 geo_daily_briefing.py
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared.cron_wrapper import cron_job

KB_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geo_knowledge_base.json")

DISCORD_CHANNEL = "hermes-agent"  # posts to #hermes-agent

def load_kb():
    if not os.path.exists(KB_JSON):
        return None
    with open(KB_JSON) as f:
        return json.load(f)

def build_briefing(kb):
    lines = []
    lines.append(f"**GEO Daily Briefing — {datetime.now().strftime('%B %d, %Y')}**\n")

    # Stats highlight
    lines.append("**📊 Key Stats**")
    for s in kb.get("statistics", [])[:6]:
        lines.append(f"  • {s['metric']}: **{s['stat']}**")
    lines.append("")

    # New articles
    articles = kb.get("articles", [])
    if articles:
        lines.append(f"**📰 Latest Articles ({len(articles)} total)**")
        for a in articles[:5]:
            kpts = a.get("key_takeaways", [])
            kpt = kpts[0][:120] + "..." if kpts and len(kpts[0]) > 120 else (kpts[0] if kpts else "No takeaways yet")
            lines.append(f"  • [{a['title']}]({a['url']}) — {kpt}")
        lines.append("")

    # Sales talking points
    pts = kb.get("geo_sales_talking_points", [])
    if pts:
        lines.append("**🎯 Sales Talking Points**")
        for pt in pts[:4]:
            lines.append(f"  • {pt}")
        lines.append("")

    # Levers by vertical
    verticals = kb.get("verticals", {})
    if verticals:
        lines.append("**🛠️ Top GEO Levers by Vertical**")
        for vert, data in verticals.items():
            name = vert.replace("_", " ").title()
            levers = data.get("geo_levers", [])[:3]
            lines.append(f"  *{name}:*")
            for l in levers:
                lines.append(f"    — {l}")
        lines.append("")

    # Tools
    tools = kb.get("tools", [])
    if tools:
        lines.append("**🧰 Tools**")
        for t in tools:
            lines.append(f"  • [{t['name']}]({t['url']}) — {t['use']}")
        lines.append("")

    lines.append(f"_GEO Knowledge Base updated {kb.get('last_updated','unknown')}_")
    return "\n".join(lines)

@cron_job("geo_daily_briefing", expected_interval_hours=72)
def main():
    print(f"[geo_daily_briefing] {datetime.now().isoformat()}")

    kb = load_kb()
    if kb is None:
        print("No GEO Knowledge Base found — run geo_kb_updater.py first")
        return

    briefing = build_briefing(kb)
    print(briefing)

if __name__ == "__main__":
    main()
