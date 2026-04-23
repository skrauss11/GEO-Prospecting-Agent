#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from tools import TOOL_DISPATCH

# -----------------------------------------------------------------------------


HISTORY_FILE = Path(__file__).parent / 'previous_reports.json'

# Domains that are search engines, directories, review platforms, or social media
# — not actual business websites to prospect
SKIP_DOMAINS = {
    'google.com', 'duckduckgo.com', 'bing.com', 'yahoo.com', 'baidu.com',
    'yelp.com', 'linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
    'youtube.com', 'pinterest.com', 'reddit.com', 'quora.com',
    'wikipedia.org', 'wikidata.org',
    'bbb.org', 'yellowpages.com', 'yellowbook.com', 'manta.com',
    'angieslist.com', 'houzz.com', 'thumbtack.com', 'homeadvisor.com',
    'craigslist.org', 'avvo.com', 'lawinfo.com', 'findlaw.com',
    'justia.com', 'martindale.com', 'nolo.com',
    'googleapis.com', 'googleusercontent.com', 'googletagmanager.com',
    'doubleclick.net', 'amazonaws.com', 'cloudfront.net',
    'sharethis.com', 'addthis.com',
}

# Substrings that indicate a URL is a search result, directory, or non-business page
SKIP_URL_SUBSTRINGS = [
    '/search=', 'google.com/search', 'bing.com/search',
    'policies.google.com', 'support.google.com',
    'linkedin.com/company/',     # company pages are OK; person profiles are not
    'linkedin.com/in/',
    'facebook.com/pages/', 'facebook.com/people/',
    'instagram.com/',
    'twitter.com/',
    'youtube.com/channel/', 'youtube.com/watch',
    'pinterest.com/pin/',
    'reddit.com/r/', 'reddit.com/user/',
    'amazon.com/dp/', 'amazon.com/gp/',
    '/search?q=', '/search?',
    'site:pinterest', 'site:youtube',
]


# -----------------------------------------------------------------------------
# History / dedup
# -----------------------------------------------------------------------------


def load_history() -> set[str]:
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text())
            return set(data.get('urls', []))
        except (json.JSONDecodeError, KeyError):
            return set()
    return set()


def add_to_history(urls: list[str]) -> None:
    """Add URLs (normalized to base domain) to the scoring history."""
    existing = load_history()
    # Normalize all incoming URLs to base domain before saving
    normalized = []
    for url in urls:
        normalized_url = extract_base_url(normalize_url(url))
        if normalized_url not in existing:
            normalized.append(normalized_url)

    combined = list(dict.fromkeys(list(existing) + normalized))
    trimmed = combined[-500:]
    HISTORY_FILE.write_text(json.dumps({
        'urls': trimmed,
        'last_updated': __import__('datetime').datetime.now().isoformat(),
    }, indent=2))


def is_already_scored(url: str) -> bool:
    """Check if this exact URL (as base domain) has been scored before."""
    normalized = normalize_url(url)
    base = extract_base_url(normalized)
    history = load_history()
    return base in history


def extract_base_url(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return f'{parsed.scheme}://{parsed.netloc}'


# -----------------------------------------------------------------------------
# Search
# -----------------------------------------------------------------------------


SEARCH_API = 'https://html.duckduckgo.com/html/'


def search_duckduckgo(query: str) -> list[str]:
    try:
        resp = httpx.get(
            SEARCH_API,
            params={'q': query},
            headers={'User-Agent': 'Mozilla/5.0 (geo-discover)'},
            timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        urls = []
        for r in soup.select('.result'):
            link_el = r.select_one('.result__url')
            if link_el:
                url = link_el.get_text(strip=True)
                if url:
                    urls.append(url)
        return urls
    except Exception:
        return []


async def search_async(query: str) -> list[str]:
    return search_duckduckgo(query)


# -----------------------------------------------------------------------------
# Filters
# -----------------------------------------------------------------------------


def is_business_url(url: str) -> bool:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace('www.', '')

    # Skip known non-business domains
    if domain in SKIP_DOMAINS:
        return False

    # Skip URL patterns that are search/directory results
    path_and_query = (parsed.path + parsed.query).lower()
    for skip in SKIP_URL_SUBSTRINGS:
        if skip in path_and_query:
            return False

    # Must have a reasonable domain — skip bare IP addresses
    if re.match(r'\b(?:\b[0-9]{1,3}\b\bye\b){4}', domain):
        return False

    return True


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    # Strip trailing slashes for consistency
    url = url.rstrip('/')
    return url


def filter_candidates(urls: list[str]) -> list[str]:
    seen = set()
    result = []
    for url in urls:
        url = normalize_url(url)
        if not url:
            continue
        if not is_business_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
    return result


# -----------------------------------------------------------------------------
# Query generation
# -----------------------------------------------------------------------------


def build_queries(params: str, count: int = 6) -> list[str]:
    base = params.strip()

    # Extract parts for variations
    # Try to detect location and vertical from natural phrasing
    location = ''
    vertical = base

    location_hints = ['nyc', 'new york', 'brooklyn', 'manhattan', 'queens',
                      'bronx', 'long island', 'westchester', 'new jersey',
                      'los angeles', 'chicago', 'houston', 'miami', 'boston',
                      'austin', 'seattle', 'denver', 'phoenix', 'atlanta']

    verticals = ['law firm', 'law office', 'attorney', 'lawyer',
                 'healthcare', 'medical', 'doctor', 'hospital',
                 'financial advisor', 'wealth management', 'cpa', 'accountant',
                 'insurance', 'real estate', 'home services',
                 'higher education', 'university', 'college',
                 'ecommerce', 'retail', 'restaurant', 'hospitality',
                 'consulting', 'marketing agency', 'software']

    # Detect if location is already in the phrase
    lower_params = base.lower()
    for loc in location_hints:
        if loc in lower_params:
            location = loc
            break

    if not location:
        location = 'New York City'

    # Build query variations
    queries = []

    # Primary: match the user's phrasing as-closely as possible
    queries.append(base)

    # Variation 1: [vertical] + location
    queries.append(f'{vertical} {location}')

    # Variation 2: site:.com qualifier
    queries.append(f'{vertical} {location} site:.com')

    # Variation 3: top/premier framing
    queries.append(f'top {vertical} {location}')

    # Variation 4: location + vertical
    queries.append(f'{location} {vertical}')

    # Variation 5: best framing
    queries.append(f'best {vertical} {location}')

    # Variation 6: directory-free, exclude common non-businesses
    queries.append(f'{vertical} {location} -yelp -linkedin -facebook')

    return queries[:count]


# -----------------------------------------------------------------------------
# Snippet analysis — size/revenue signals
# -----------------------------------------------------------------------------


SIZE_SIGNALS = [
    'attorneys', 'lawyers', 'counsel', 'partners',
    'offices in', 'office locations', 'multiple locations',
    'employees', 'staff', 'team of',
    'founded in', 'established', 'since 19', 'since 20',
    'million', 'billion', 'revenue',
    'top firm', 'best law firm', 'leading', 'award-winning',
    'ranked', 'tier 1', 'am law',
    'fortune', 'inc. 5000', 'fast company',
]

JUNK_SIGNALS = [
    'jobs', 'careers', 'hiring', 'apply now',
    'get a quote', 'free consultation', 'sign up',
    'advertisement', 'sponsored',
    'click here', 'buy now', 'coupon',
]


def has_size_signal(snippet: str) -> bool:
    snippet = snippet.lower()
    junk = any(j in snippet for j in JUNK_SIGNALS)
    if junk:
        return False
    return any(s in snippet for s in SIZE_SIGNALS)


# -----------------------------------------------------------------------------
# Discoverer class
# -----------------------------------------------------------------------------


class Discoverer:
    def __init__(self, params: str, limit: int = 8):
        self.params = params
        self.limit = limit
        self.seen_domains: set[str] = set()
        self.candidates: list[str] = []

    def _already_scored(self, url: str) -> bool:
        return is_already_scored(url)

    def _already_seen_domain(self, url: str) -> bool:
        base = extract_base_url(normalize_url(url))
        if base in self.seen_domains:
            return True
        self.seen_domains.add(base)
        return False

    async def run(self) -> dict:
        queries = build_queries(self.params, count=6)
        print(f'  Generating {len(queries)} search queries from: \"{self.params}\"')

        # Run all searches concurrently
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            semaphore = asyncio.Semaphore(3)

            async def search_q(q: str) -> list[str]:
                async with semaphore:
                    try:
                        resp = await client.get(
                            SEARCH_API,
                            params={'q': q},
                            headers={'User-Agent': 'Mozilla/5.0 (geo-discover)'},
                        )
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        urls = []
                        for r in soup.select('.result'):
                            el = r.select_one('.result__url')
                            snippet_el = r.select_one('.result__snippet')
                            if el and el.get_text(strip=True):
                                urls.append({
                                    'url': el.get_text(strip=True),
                                    'snippet': snippet_el.get_text(strip=True) if snippet_el else '',
                                })
                        return urls
                    except Exception:
                        return []

            all_results = await asyncio.gather(*[search_q(q) for q in queries])

        # Flatten, deduplicate
        seen = set()
        all_urls = []
        for result_set in all_results:
            for item in result_set:
                url = normalize_url(item['url'])
                if url and url not in seen:
                    seen.add(url)
                    all_urls.append(item)

        print(f'  {len(all_urls)} unique URLs collected from {len(queries)} searches')

        # Filter to business URLs
        business = [u for u in all_urls if is_business_url(u['url'])]
        print(f'  {len(business)} are valid business URLs after filtering directories/search engines')

        # Filter out already-scored (exact domain)
        new_only = [u for u in business if not self._already_scored(u['url'])]
        already_done = [u['url'] for u in business if self._already_scored(u['url'])]

        if already_done:
            print(f'  {len(already_done)} already scored — skipping (exact domain dedup)')

        # Filter out same-domain duplicates (keep first seen)
        deduped = []
        for item in new_only:
            if not self._already_seen_domain(item['url']):
                deduped.append(item)

        # Sort by size signals (prioritize likely larger businesses)
        deduped.sort(
            key=lambda x: has_size_signal(x['snippet']),
            reverse=True,
        )

        final_urls = [u['url'] for u in deduped[:self.limit]]

        print(f'  → {len(final_urls)} new sites to analyze:')
        for url in final_urls:
            print(f'     • {url}')

        return {
            'params': self.params,
            'queries_used': queries,
            'total_found': len(all_urls),
            'business_filtered': len(business),
            'already_scored': len(already_done),
            'new_sites': final_urls,
        }


# -----------------------------------------------------------------------------
# Convenience function for geo_scanner.py
# -----------------------------------------------------------------------------

async def discover(params: str, limit: int = 8) -> dict:
    d = Discoverer(params, limit=limit)
    return await d.run()


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('Usage: python discover.py <search params> [--limit N]')
        sys.exit(1)

    limit = 8
    params_list = sys.argv[1:]
    if '--limit' in params_list:
        idx = params_list.index('--limit')
        limit = int(params_list[idx + 1])
        params_list = params_list[:idx]

    params = ' '.join(params_list)

    result = asyncio.run(discover(params, limit=limit))

    print()
    sites = result['new_sites']
    print(f'Sites to analyze: {len(sites)}')
    for u in sites:
        print(f'  {u}')

    if sites:
        add_to_history(sites)
        print(f'\nSaved {len(sites)} URLs to history.')