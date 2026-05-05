# mREIT Monitor

Automated financial filing monitor, extractor, and analyzer for mortgage REITs.

Monitors 7 companies (ARR, ORC, AGNC, NLY, CIM, DX, BMNM), detects new filings on their IR pages and SEC EDGAR, extracts structured data via LLM, generates comparative analyses, and produces consolidated desk-style summary reports.

## What it does

- **Detects** new filings on IR websites (BeautifulSoup first, Ollama fallback) and SEC EDGAR (free API, no auth)
- **Extracts** structured financial data from PDFs and HTML using OpenRouter-hosted models
- **Compares** sequential periods to flag metric changes and anomalies
- **Reports** via email (Resend) and/or webhook; stores all data in Supabase
- **Schedules** smartly — IR scraping only during known filing windows, EDGAR polling daily during windows / weekly otherwise
- **Exposes** an MCP endpoint at `/mcp` for LLM agent integration

## Quick start

```bash
# Install dependencies
pip install -e .
# or: uv sync

# Copy and fill in config
cp .env.example .env

# Run all 5 migrations against your Supabase project (in order)
# supabase/migrations/001_initial_schema.sql  through  005_extraction_comparisons.sql

# Seed the companies table from the registry
python -m scripts.seed_companies

# Start the server
python serve.py
# or: uvicorn src.main:app --host 127.0.0.1 --port 8012
```

Health check: `GET http://localhost:8012/health`

Manual poll: `POST http://localhost:8012/trigger/poll/ARR` (with `X-API-Key` header if configured)

## Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Service role key (bypasses RLS) |
| `OPENROUTER_API_KEY` | Yes | OpenRouter key for all LLM calls |
| `EDGAR_USER_AGENT` | Yes | `AppName your@email.com` (SEC policy) |
| `RESEND_API_KEY` | No | For email alerts on new extractions |
| `REIT_MONITOR_API_KEY` | No | Protects trigger/API endpoints |
| `GATEWAY_URL` | No | POST usage metrics to an external gateway |

See `.env.example` for all options including model selection and scheduler timing.

## Database

Run migrations in order from `supabase/migrations/`. They are additive — safe to apply to an existing Supabase project.

| Migration | What it adds |
|---|---|
| `001_initial_schema.sql` | Core tables: companies, filings, monthly/quarterly metrics, portfolio/repo/swap positions, analyses |
| `002_summary_reports.sql` | Summary reports and investor materials |
| `003_multi_company.sql` | `company_documents` + `universal_extractions` for the multi-company pipeline |
| `004_add_filing_types.sql` | Adds enum values (financial_supplement, monthly_book_value, press_release, monthly_dividend) |
| `005_extraction_comparisons.sql` | A/B extraction comparison table |

## Companies

| Ticker | Company | Focus | Monthly Updates |
|---|---|---|---|
| ARR | ARMOUR Residential REIT | Agency RMBS | Yes |
| ORC | Orchid Island Capital | Agency RMBS | Yes |
| AGNC | AGNC Investment Corp | Agency RMBS + TBAs | No (monthly BV press releases) |
| NLY | Annaly Capital Management | Agency + Residential Credit + MSR | No |
| CIM | Chimera Investment | Hybrid (agency + non-agency + loans + MSR) | No |
| DX | Dynex Capital | Agency RMBS + CMBS | No |
| BMNM | Bimini Capital Management | Agency RMBS + Advisory | No |

## Architecture

```
Scheduler (APScheduler)
  ├── Hourly Mon–Fri 6–20 ET: scrape IR pages → store detected docs
  ├── Daily during filing windows: check SEC EDGAR
  └── Nightly: download + extract pending docs

Extraction pipeline
  BeautifulSoup (free) → Ollama local (free) → OpenRouter LLM (paid)

API
  /health         — status
  /trigger/poll/* — manual poll
  /api/*          — frontend JSON API (companies, documents, reports, extractions)
  /review/*       — web UI for previewing reports
  /mcp            — MCP endpoint for LLM agent integration
```

## LLM costs

Extraction uses `claude-haiku-4.5` by default (~$0.001/doc). Comparison and summary use `claude-sonnet-4.6`. IR page scraping uses BeautifulSoup (free) with Ollama fallback (free). Set `LOCAL_EXTRACTION=true` to route all text-only extraction through a local Ollama model.

## Windows service

On Windows, run with NSSM:
```
nssm install REITMonitor python serve.py
nssm set REITMonitor AppDirectory C:\path\to\reit-monitor
nssm start REITMonitor
```
