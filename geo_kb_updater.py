#!/usr/bin/env python3
"""
geo_kb_updater.py
Scans for new GEO articles, podcasts, and videos and updates geo_knowledge_base.json + GEO_KNOWLEDGE_BASE.md
Run: python3 geo_kb_updater.py
"""

import json
import os
import sys
from datetime import datetime, timedelta
from urllib.request import urlopen
from urllib.error import URLError
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

KB_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geo_knowledge_base.json")
KB_MD  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "GEO_KNOWLEDGE_BASE.md")

# ─── Search functions ──────────────────────────────────────────────────────────

def web_search(query, limit=5):
    try:
        from hermes_tools import web_search as ws
        result = ws(query, limit=limit)
        return result.get("data", {}).get("web", [])
    except Exception:
        return []

def web_extract(urls):
    try:
        from hermes_tools import web_extract as we
        return we(urls)
    except Exception:
        return {"results": []}

# ─── Load existing KB ───────────────────────────────────────────────────────────

def load_kb():
    if not os.path.exists(KB_JSON):
        return None
    with open(KB_JSON) as f:
        return json.load(f)

def save_kb(kb):
    with open(KB_JSON, "w") as f:
        json.dump(kb, f, indent=2)
    print(f"[geo_kb_updater] Saved {KB_JSON}")

def is_new_url(kb, url):
    """Return True if URL not already in any article/podcast/youtube list."""
    existing = set()
    for section in ["articles", "podcasts", "youtube"]:
        for item in kb.get(section, []):
            if item.get("url"):
                existing.add(item["url"])
    return url not in existing

# ─── Article enrichment ─────────────────────────────────────────────────────────

def extract_key_takeaways(url, max_kpts=5):
    """Try to pull first 3-5 bullet-worthy sentences from article."""
    data = web_extract([url])
    for r in data.get("results", []):
        if r.get("url") != url:
            continue
        content = r.get("content", "")
        # Strip markdown headings
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        # Collect non-heading, non-empty lines
        sentences = []
        for line in lines:
            # Skip headings (lines starting with #)
            if line.startswith("#"):
                continue
            # Skip lines that are too short or look like nav/boilerplate
            if len(line) < 80:
                continue
            sentences.append(line)
            if len(sentences) >= max_kpts:
                break
        if sentences:
            return sentences[:max_kpts]
    return []

# ─── Scan for new GEO content ──────────────────────────────────────────────────

SEARCH_QUERIES = [
    "Generative Engine Optimization GEO 2026",
    "GEO SEO AI search optimization",
    "Answer Engine Optimization AEO 2026",
    "ChatGPT Perplexity search brand citations 2026",
]

def scan_new_content():
    new_articles = []
    seen_urls = set()

    for query in SEARCH_QUERIES:
        print(f"[geo_kb_updater] Searching: {query}")
        results = web_search(query, limit=8)
        for r in results:
            url = r.get("url", "")
            if not url or url in seen_urls:
                continue
            # Filter out non-article sources (skip products, tools, local nav)
            skip_patterns = ["youtube.com", "podcasts.apple", "audible.com", "geoptie.com",
                             "schema.org", "llms.txt", "google.com/search"]
            if any(p in url for p in skip_patterns):
                continue
            seen_urls.add(url)
            title = r.get("title", "Unknown")
            new_articles.append({
                "title": title,
                "source": r.get("source", "Web") or "Web",
                "url": url,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "key_takeaways": []
            })

    return new_articles

# ─── Rebuild markdown ──────────────────────────────────────────────────────────

def rebuild_markdown(kb):
    md_lines = [
        "# GEO Knowledge Base",
        "*MadTech Growth — Internal Resource*",
        f"Updated: {kb.get('last_updated', 'unknown')}",
        "",
        "---",
        "",
        "## Key Statistics",
        "",
        "| Metric | Stat | Source |",
        "|--------|------|--------|",
    ]
    for s in kb.get("statistics", []):
        md_lines.append(f"| {s['metric']} | **{s['stat']}** | {s['source']} |")

    md_lines += ["", "---", "", "## GEO vs SEO", "",
        "| Aspect | SEO (Traditional) | GEO (AI-first) |",
        "|--------|------------------|----------------|"]
    geo_seo = next((f for f in kb.get("frameworks", []) if f["name"] == "GEO vs SEO Comparison"), None)
    if geo_seo:
        for row in geo_seo.get("rows", []):
            md_lines.append(f"| {' | '.join(row)} |")

    md_lines += ["", "---", "", "## 4-Phase GEO Framework", ""]
    framework = next((f for f in kb.get("frameworks", []) if f["name"] == "4-Phase GEO Framework"), None)
    if framework:
        for i, step in enumerate(framework.get("steps", []), 1):
            md_lines.append(f"{i}. **{step.split('—')[0].strip()}** — {step.split('—')[1].strip() if '—' in step else step}")

    md_lines += ["", "---", "", "## 8 GEO Pillars", ""]
    pillars_f = next((f for f in kb.get("frameworks", []) if f["name"] == "8 GEO Pillars"), None)
    if pillars_f:
        for i, p in enumerate(pillars_f.get("pillars", []), 1):
            md_lines.append(f"{i}. {p}")

    # Articles
    md_lines += ["", "---", "", "## Must-Read Articles", ""]
    for a in kb.get("articles", []):
        md_lines.append(f"- [{a['title']}]({a['url']}) — *{a['source']}*")

    # Podcasts
    md_lines += ["", "---", "", "## Podcasts", ""]
    for p in kb.get("podcasts", []):
        md_lines.append(f"- [{p['title']}]({p['url']}) — {p.get('platform','Podcast')}")

    # YouTube
    md_lines += ["", "---", "", "## YouTube", ""]
    for y in kb.get("youtube", []):
        md_lines.append(f"- [{y['title']}]({y['url']})")

    # Tools
    md_lines += ["", "---", "", "## Tools", ""]
    for t in kb.get("tools", []):
        md_lines.append(f"- [{t['name']}]({t['url']}) — {t['use']}")

    # Sales talking points
    md_lines += ["", "---", "", "## Sales Talking Points", ""]
    for i, pt in enumerate(kb.get("geo_sales_talking_points", []), 1):
        md_lines.append(f"{i}. {pt}")

    with open(KB_MD, "w") as f:
        f.write("\n".join(md_lines))
    print(f"[geo_kb_updater] Rebuilt {KB_MD}")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"[geo_kb_updater] Starting — {datetime.now().isoformat()}")

    kb = load_kb()
    if kb is None:
        print("[geo_kb_updater] No existing KB found. Run geo_scanner.py first to create it.")
        return

    kb["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    # Scan for new content
    new_articles = scan_new_content()
    added = 0
    for article in new_articles:
        if is_new_url(kb, article["url"]):
            # Try to get key takeaways
            kpts = extract_key_takeaways(article["url"])
            article["key_takeaways"] = kpts
            kb["articles"].insert(0, article)
            added += 1
            print(f"[geo_kb_updater] NEW article added: {article['title']}")

    if added:
        print(f"[geo_kb_updater] Added {added} new article(s)")
        save_kb(kb)
        rebuild_markdown(kb)
    else:
        print("[geo_kb_updater] No new content found — KB is current")

    print(f"[geo_kb_updater] Done — {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()
