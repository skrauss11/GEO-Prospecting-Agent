# MadTech Growth — GEO Prospecting Agent

## Who
**Scott Krauss** — Founder, MadTech Growth
scott@madtechgrowth.com | madtechgrowth.com

---

## Core Thesis
GEO (Generative Engine Optimization) = **brand narrative control for the AI layer**.
As AI search engines (ChatGPT, Perplexity, Google AI Overviews, Claude for Search)
become primary discovery channels, businesses with weak AI visibility lose control
of their narrative — and their pipeline.

The service: find businesses with zero AI visibility, prove it with a data-driven
snapshot, and close them on a full GEO audit + retainer.

---

## Vertical Focus
1. **Professional Services** — law firms, accounting firms, consulting, financial advisors
   - Universal gap: NO JSON-LD / Schema.org markup. Near-zero FAQ content.
   - GEO lever: structured data implementation, FAQ content strategy
2. **DTC/eCommerce** ($100M+ brands) — apparel, beauty, health, food & beverage
   - Common gap: no product schema, thin AI-visible copy, AI bots blocked
   - GEO lever: product structured data, brand content optimization

---

## Service Tiers
- **Lead Magnet** (free): GEO Snapshot — 8-dimension analysis delivered by email
- **Starter** ($3K–$8K): Snapshot + initial implementation
- **Growth** ($5K–$15K/mo): Full GEO program, ongoing optimization
- **Enterprise** ($15K–$50K+/mo): Dedicated GEO strategy, API integration, benchmarking

---

## Sales Funnel
1. **Snapshot** — free GEO Snapshot from landing page (geo-snapshot-landing/)
   - Netlify function: netlify/functions/geo-snapshot.py
   - Delivered via SMTP email
2. **Discovery** — 30-min call, identify top 3 GEO gaps
3. **Audit Proposal** — paid or unpaid audit, deliver prioritized roadmap
4. **Retainer** — monthly GEO execution retainer

---

## GEO Framework (8 Pillars)
1. E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness)
2. Structured Content (well-organized, scannable by AI)
3. Schema Markup (JSON-LD, Schema.org types)
4. Citation Authority (backlink profile, brand mentions)
5. Fact Density (specific numbers, dates, named entities)
6. Freshness (content recency signals)
7. Technical Accessibility (AI bot access, sitemap, robots.txt)
8. Brand Reputation (GMB, reviews, citations across the web)

---

## Brand Identity
- **Colors**: #0B1120 (navy), #C45D3E (terracotta)
- **Fonts**: DM Serif Display (headings), Outfit (body)
- **Voice**: Authoritative senior consultant. No hedging. No fluff.
- **Tagline concept**: "Agentic Commerce Advisory"

---

## Codebase
- **Primary repo**: `~/Desktop/Claude Code Test/web-research-agent/`
- **GEO repo**: https://github.com/skrauss11/GEO-Prospecting-Agent
- **Landing page**: geo-snapshot-landing/ (Netlify Functions)
- **Tools**: tools.py (web_search, fetch_page, analyze_site_geo, extract_contacts, send_slack_report)
- **Key scripts**:
  - `geo_prospector.py` — multi-vertical daily discovery → Slack
  - `ps_discovery.py` — Professional Services discovery → Discord
  - `dtc_discovery.py` — DTC/eCommerce discovery → Discord
  - `geo_daily_briefing.py` — KB highlights → Discord (via cron deliver)
  - `geo-snapshot-landing/netlify/functions/geo-snapshot.py` — snapshot email delivery

---

## Current Priorities
1. Close first paying client
2. Get geo-snapshot landing page live with SMTP (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, FROM_EMAIL env vars needed in Netlify)
3. Expand to DTC vertical (dtc_discovery.py now built)
4. Set up recurring cron jobs for both verticals

---

## Key Known Bugs
- `geo-snapshot.py` line 70: `urlparse` was not imported — **FIXED** (added import)
- `geo_daily_briefing.py`: only prints to stdout, no Discord send — output routed via cron `deliver` param

---

## Deduplication
Scott prefers **exact-domain dedup** (not root domain).
History files: `previous_reports.json` (geo_prospector), `ps_discovery_history.json`, `dtc_discovery_history.json`
