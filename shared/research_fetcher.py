"""
Research Fetcher — Pull fresh SEO/GEO content from RSS feeds and Reddit.
"""

import json
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx


# ─── Source Config ───────────────────────────────────────────────────────────

RSS_SOURCES = {
    "Search Engine Land": "https://searchengineland.com/feed/",
    "Search Engine Journal": "https://www.searchenginejournal.com/feed/",
}

REDDIT_SOURCES = {
    "r/SEO": "https://www.reddit.com/r/SEO/top/.json?t=day&limit=10",
    "r/bigseo": "https://www.reddit.com/r/bigseo/top/.json?t=day&limit=10",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# ─── RSS Fetching ────────────────────────────────────────────────────────────

def _parse_rss(xml_bytes: bytes) -> list[dict[str, Any]]:
    """Parse RSS XML into a list of story dicts."""
    import xml.etree.ElementTree as ET
    stories = []
    try:
        root = ET.fromstring(xml_bytes)
        # Handle RSS 2.0
        channel = root.find("channel")
        if channel is not None:
            items = channel.findall("item")
        else:
            # Handle Atom
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall("atom:entry", ns)

        for item in items[:10]:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description") or item.find("summary")
            pub_el = item.find("pubDate") or item.find("published")

            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            desc = (desc_el.text or "").strip() if desc_el is not None else ""
            pub = (pub_el.text or "").strip() if pub_el is not None else ""

            # Clean HTML from description
            if desc:
                import re
                desc = re.sub(r"<[^>]+>", "", desc)
                desc = desc[:500]

            if title and link:
                stories.append({
                    "title": title,
                    "url": link,
                    "description": desc,
                    "published": pub,
                    "source": "rss",
                })
    except Exception as e:
        print(f"  ⚠️ RSS parse error: {e}")
    return stories


def fetch_rss_feeds() -> list[dict[str, Any]]:
    """Fetch all configured RSS feeds."""
    stories = []
    with httpx.Client(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
        for source_name, url in RSS_SOURCES.items():
            try:
                resp = client.get(url)
                resp.raise_for_status()
                feed_stories = _parse_rss(resp.content)
                for s in feed_stories:
                    s["feed_name"] = source_name
                stories.extend(feed_stories)
                print(f"  ✓ {source_name}: {len(feed_stories)} stories")
            except Exception as e:
                print(f"  ⚠️ {source_name} failed: {e}")
    return stories


# ─── Reddit Fetching ─────────────────────────────────────────────────────────

def fetch_reddit_posts() -> list[dict[str, Any]]:
    """Fetch top daily posts from configured subreddits."""
    posts = []
    with httpx.Client(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
        for subreddit, url in REDDIT_SOURCES.items():
            try:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                for child in children[:10]:
                    post = child.get("data", {})
                    title = post.get("title", "").strip()
                    permalink = post.get("permalink", "")
                    url_full = f"https://www.reddit.com{permalink}" if permalink else ""
                    score = post.get("score", 0)
                    num_comments = post.get("num_comments", 0)
                    selftext = post.get("selftext", "")[:800]

                    if title:
                        posts.append({
                            "title": title,
                            "url": url_full,
                            "description": selftext,
                            "published": datetime.utcnow().isoformat(),
                            "source": "reddit",
                            "feed_name": subreddit,
                            "metadata": {
                                "score": score,
                                "comments": num_comments,
                            },
                        })
                print(f"  ✓ {subreddit}: {len(children)} posts")
            except Exception as e:
                print(f"  ⚠️ {subreddit} failed: {e}")
    return posts


# ─── Unified Fetch ───────────────────────────────────────────────────────────

def fetch_all_sources() -> list[dict[str, Any]]:
    """Fetch all research sources and return combined stories."""
    print("\n[research] Fetching fresh content...")
    stories = []
    stories.extend(fetch_rss_feeds())
    stories.extend(fetch_reddit_posts())
    print(f"[research] Total stories fetched: {len(stories)}\n")
    return stories


if __name__ == "__main__":
    results = fetch_all_sources()
    for r in results[:5]:
        print(f"[{r['feed_name']}] {r['title']}")
