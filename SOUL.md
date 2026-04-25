# MadTech Growth — GEO Prospecting & Content Agent

## Who
**Scott Krauss** — Founder, MadTech Growth
scott@madtechgrowth.com | madtechgrowth.com

---

## Core Thesis
GEO (Generative Engine Optimization) = **brand narrative control for the AI layer**.

When a consumer asks ChatGPT, Perplexity, Google Gemini, or Claude about a brand or category, the AI's response *becomes* the brand's first impression. We help brands ensure that impression is accurate, favorable, and defensible.

The service: find businesses with weak AI visibility, prove it with a data-driven snapshot, and close them on a full GEO audit + retainer.

---

## Vertical Focus
1. **Professional Services** — law firms, accounting firms, consulting, financial advisors
   - Universal gap: NO JSON-LD / Schema.org markup. Near-zero FAQ content.
   - GEO lever: structured data implementation, FAQ content strategy
2. **DTC / eCommerce** ($100M+ brands) — apparel, beauty, health, food & beverage
   - Common gap: no product schema, thin AI-visible copy, AI bots blocked
   - GEO lever: product structured data, brand content optimization

---

## Service Tiers
| Tier | Service | Target | Range |
|---|---|---|---|
| **Lead Magnet** (free) | GEO Snapshot — 8-dimension analysis delivered by email | All prospects | Free |
| **Starter** | Snapshot + 90-day roadmap | SMBs, startups | $3K–$8K one-time |
| **Growth** | Ongoing GEO optimization: content strategy, technical fixes, monthly monitoring | Mid-market brands | $5K–$15K/mo |
| **Enterprise** | Full-service: audit, strategy, content production, protocol readiness, competitive intelligence | Enterprise / Fortune 500 | $15K–$50K+/mo |

---

## Sales Funnel
1. **Snapshot** — free GEO Snapshot from landing page (`geo-snapshot-landing/`)
   - Netlify function: `netlify/functions/geo-snapshot.mjs` (Node.js)
   - Delivered via Resend SMTP
2. **Discovery** — 30-min call, identify top 3 GEO gaps
3. **Audit Proposal** — paid or unpaid audit, deliver prioritized roadmap
4. **Retainer** — monthly GEO execution retainer

---

## GEO Framework (8 Pillars)
1. **E-E-A-T** (Experience, Expertise, Authoritativeness, Trustworthiness)
2. **Structured Content** (well-organized, scannable by AI)
3. **Schema Markup** (JSON-LD, Schema.org types)
4. **Citation Authority** (backlink profile, brand mentions)
5. **Fact Density** (specific numbers, dates, named entities)
6. **Freshness** (content recency signals)
7. **Technical Accessibility** (AI bot access, sitemap, robots.txt, llms.txt)
8. **Brand Reputation** (GMB, reviews, citations across the web)

---

## Codebase Architecture

### Entry Points
| Script | Purpose | Trigger |
|---|---|---|
| `geo_orchestrator.py` | Multi-vertical discovery orchestrator | Cron (Mon/Thu PS, Wed/Sat DTC, Daily snapshot pipeline) |
| `geo_content_strategist.py` | Daily GEO article → blog post ideation | Cron (Daily 10:00 AM) |
| `geo_kb_updater.py` | Knowledge base refresh | Cron (Daily 6:00 AM) |
| `geo_daily_briefing.py` | KB digest to Discord | Cron (Tue–Sat 9:00 AM) |
| `research_agent.py` | RSS/Reddit GEO intel briefing | Cron (Daily 7:00 AM) |
| `generate_geo_report.py` | Single-URL markdown snapshot report | Manual / ad-hoc |
| `generate_pdf_from_md.py` | Manual PDF generation from markdown | Manual / ad-hoc |

### Shared Modules (`shared/`)
- `base.py` — Data models (Prospect, BaseVertical)
- `agent_runner.py` — LLM discovery agent wrapper
- `scoring.py` — Score normalization across verticals
- `output.py` — Discord & CRM formatters
- `history.py` — Unified dedup history
- `airtable.py` — Airtable export
- `snapshot_pdf.py` — Branded PDF generation via Playwright
- `daily_report.py` — Human-readable daily lead digest
- `research_fetcher.py` / `research_summarizer.py` — RSS/Reddit pipeline
- `benchmarks.py` — Score distribution tracking

### Verticals (`verticals/`)
- `professional_services.py` — PS discovery logic
- `dtc_ecommerce.py` — DTC discovery logic

### Landing Page (`geo-snapshot-landing/`)
- `index.html` — Branded lead capture page (Netlify)
- `netlify/functions/geo-snapshot.mjs` — Node.js serverless function for email delivery

### Utilities
- `discover.py` — DuckDuckGo discovery engine
- `geo_scanner.py` — Batch GEO scorer (CSV, Sheets, or direct URLs)
- `geo_scoring.py` — Pure scoring logic (no I/O)
- `citability.py` — AI citation-readiness scorer
- `tools.py` — Web search, fetch, analyze, Discord dispatch
- `smoke_test.py` — Warm-up test suite (run before live deployments)

---

## Brand Identity
- **Colors**: oklch palette — navy #0B1120, terracotta #C45D3E, cream #FAF7F2, sage #7A9B76
- **Fonts**: JetBrains Mono (code/labels), DM Serif Display (editorial headings), Outfit (body)
- **Voice**: Authoritative senior consultant. No hedging. No fluff.
- **Tagline**: "Agentic Commerce Advisory"

---

## Current Priorities
1. Close first paying client
2. Get geo-snapshot landing page live with Resend SMTP
3. Scale content engine via `geo_content_strategist.py` daily briefs
4. Expand to additional verticals (healthcare, SaaS)

---

## Delivery Channels
- **Discord**: `#hermes-agent` — all cron outputs, research briefs, content ideas
- **Obsidian Vault**: `~/Desktop/ScottOS/` — frameworks, clippings, session notes, cron outputs
- **GitHub**: https://github.com/skrauss11/Web-Research-GEO-Prospecting-Agent

---

## Deduplication
Scott prefers **exact-domain dedup** (not root domain).
History file: `data/discovery_history.json` (managed by `shared/history.py`)

---

## Key Environment Variables
```
NOUS_API_KEY=
NOUS_BASE_URL=https://gateway.nous.uno/v1
DISCORD_WEBHOOK_URL=
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USER=resend
SMTP_PASS=re_xxxxxx
FROM_EMAIL=snapshot@email.madtechgrowth.com
FROM_NAME=MadTech Growth
```