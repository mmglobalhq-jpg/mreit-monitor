# mREIT Monitor

Automated financial filing monitor, extractor, and analyzer for mortgage REITs.

Detects new monthly company updates, quarterly earnings releases, and SEC filings from mortgage REITs, extracts structured data using AI, runs period-over-period comparison analysis, and sends email alerts with key findings.

## Quick Start

```bash
cp .env.example .env
# Fill in your API keys

uv sync                    # Install dependencies
python -m src.main         # Run locally
```

## Architecture

- **FastAPI** service with APScheduler for daily polling
- **Claude API** for PDF extraction (native PDF input) and comparative analysis
- **Supabase** for structured data storage and file storage
- **Resend** for email alerts
- **Railway** for deployment

## Documentation

- [CLAUDE.md](./CLAUDE.md) — Full project specification (for Claude Code)
- [docs/DATA_SOURCES.md](./docs/DATA_SOURCES.md) — Detailed data source documentation
- [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) — Deployment guide
- [supabase/migrations/](./supabase/migrations/) — Database schema

## Currently Supported

- **ARMOUR Residential REIT (ARR)** — Monthly updates, quarterly earnings, 10-Q/10-K

## Planned

- AGNC Investment (AGNC)
- Annaly Capital (NLY)
- Two Harbors (TWO)
- Dynex Capital (DX)
- Next.js dashboard for visualization
