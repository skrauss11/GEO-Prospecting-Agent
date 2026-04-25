# MadTech Growth — GEO Prospecting & Content Agent

An autonomous research and prospecting pipeline for MadTech Growth, a GEO (Generative Engine Optimization) advisory firm.

## What It Does

This agentic system runs daily to:

1. **Discover GEO prospects** across Professional Services and DTC/eCommerce verticals
2. **Score their AI visibility** across 8 pillars (schema, crawl access, content depth, etc.)
3. **Generate branded snapshot reports** as PDF or markdown
4. **Curate daily GEO news** from RSS/Reddit and cross-reference with internal frameworks
5. **Propose 1-2 blog post ideas per day** mapped to MadTech's methodology
6. **Deliver everything to Discord** and log to an Obsidian vault

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set env vars
export NOUS_API_KEY="..."
export DISCORD_WEBHOOK_URL="..."

# Run smoke test (no API calls)
python3 smoke_test.py

# Generate a snapshot for any URL
python3 generate_geo_report.py https://example.com

# Generate PDF from the markdown report
python3 generate_pdf_from_md.py proposals/geo_snapshot_example_com_2026-04-25.md --output ~/Desktop

# Run full discovery (orchestrator mode)
python3 geo_orchestrator.py --vertical ps --test
python3 geo_orchestrator.py --vertical dtc --test
```

## Architecture

### Discovery Pipeline
```
geo_orchestrator.py
  → verticals/professional_services.py  (Mon/Thu cron)
  → verticals/dtc_ecommerce.py         (Wed/Sat cron)
  → shared/agent_runner.py              (LLM discovery agent)
  → geo_scanner.py                     (batch GEO scoring)
  → shared/output.py                   (Discord + CRM formatting)
  → shared/daily_report.py             (human-readable digest)
```

### Content Pipeline
```
geo_content_strategist.py
  → web search for fresh GEO articles
  → load frameworks from ~/Desktop/ScottOS/GEO Frameworks/
  → LLM cross-reference analysis
  → save to Obsidian vault + post to Discord
```

### Landing Page
```
geo-snapshot-landing/
  → index.html                       (lead capture form)
  → netlify/functions/geo-snapshot.mjs (Resend SMTP delivery)
```

## Cron Schedule

All jobs run via Hermes cron and deliver to `#hermes-agent`:

| Job | Schedule | Script |
|---|---|---|
| Knowledge Base Update | Daily 6:00 AM | `geo_kb_updater.py` |
| NYC Vertical Prospector | Daily 7:00 AM | `geo_orchestrator.py` (NYC) |
| PS Discovery | Mon/Thu 8:00 AM | `geo_orchestrator.py --vertical ps` |
| DTC Discovery | Wed/Sat 8:00 AM | `geo_orchestrator.py --vertical dtc` |
| Snapshot Pipeline | Daily 8:00 AM | `geo_orchestrator.py` (snapshot is default) |
| Daily Briefing | Tue–Sat 9:00 AM | `geo_daily_briefing.py` |
| Content Strategist | Daily 10:00 AM | `geo_content_strategist.py` |

## Output Locations

| Type | Path |
|---|---|
| Lead digests | `reports/daily_leads_YYYY-MM-DD.md` |
| Snapshot reports | `proposals/geo_snapshot_<domain>_YYYY-MM-DD.md` |
| PDF snapshots | `snapshots/YYYY-MM-DD/` |
| Research briefings | `research/YYYY-MM-DD_briefing.md` |
| Content briefs | `~/Desktop/ScottOS/Cron Outputs/geo_content_brief_YYYY-MM-DD.md` |

## Environment Variables

```bash
NOUS_API_KEY=                    # Nous gateway API key
NOUS_BASE_URL=https://gateway.nous.uno/v1
DEFAULT_MODEL=moonshotai/kimi-k2.6
DISCORD_WEBHOOK_URL=             # Discord webhook for deliveries
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USER=resend                 # literally "resend"
SMTP_PASS=re_xxxxxx              # Resend API key
FROM_EMAIL=snapshot@email.madtechgrowth.com
FROM_NAME=MadTech Growth
```

## Key Files

| File | Purpose |
|---|---|
| `geo_orchestrator.py` | Main discovery orchestrator — routes to verticals, handles dedup, scoring, output |
| `geo_scanner.py` | Batch GEO scorer for any URL list (CSV, Sheets, or CLI args) |
| `generate_geo_report.py` | Single-URL markdown snapshot report generator |
| `generate_pdf_from_md.py` | Manual PDF generator from markdown reports |
| `geo_content_strategist.py` | Daily article curation → blog post ideation pipeline |
| `shared/snapshot_pdf.py` | Branded PDF renderer (Playwright + HTML template) |
| `shared/daily_report.py` | Human-readable daily lead digest writer |
| `smoke_test.py` | Warm-up test suite — run before deployments |

## License

Proprietary — MadTech Growth. Not for public distribution.
