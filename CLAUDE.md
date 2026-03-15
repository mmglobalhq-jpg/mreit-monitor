# mREIT Monitor — Project Specification

## Overview

mREIT Monitor is a FastAPI service that automatically detects, downloads, and analyzes financial filings from mortgage REITs. It extracts structured data from monthly company update PDFs, quarterly earnings releases, and SEC filings, runs AI-powered comparative analysis, stores everything in Supabase, and sends email alerts when new data is processed.

The initial company is **ARMOUR Residential REIT (NYSE: ARR)**, but the system is designed to support multiple mREITs (AGNC, NLY, TWO, DX, etc.) via a company configuration table.

## Tech Stack

- **Runtime:** Python 3.12+
- **Framework:** FastAPI with uvicorn
- **Scheduling:** APScheduler (AsyncIOScheduler) running inside FastAPI lifespan
- **Database:** Supabase (PostgreSQL + Storage)
- **PDF Extraction:** Claude API native PDF input (base64) for monthly updates; pdfplumber for 10-Q/10-K section extraction
- **AI Analysis:** Anthropic Claude API (Sonnet for extraction, Opus for comparative briefs)
- **Email:** Resend API
- **Deployment:** Railway Pro
- **Package Management:** uv (preferred) or pip

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  APScheduler (inside FastAPI lifespan)               │
│  ├─ Daily 6am ET: Poll IR pages for new PDFs/links  │
│  └─ Daily 6am ET: Poll SEC EDGAR submissions API    │
└──────────────┬──────────────────────────┬───────────┘
               │                          │
               ▼                          ▼
┌──────────────────────┐   ┌──────────────────────────┐
│  IR Page Scraper     │   │  EDGAR Submissions Check  │
│  (BeautifulSoup)     │   │  (data.sec.gov REST API)  │
└──────────┬───────────┘   └──────────┬───────────────┘
           │                          │
           ▼                          ▼
┌─────────────────────────────────────────────────────┐
│  Document Fetcher + Dedup                            │
│  - Check filings table in Supabase before processing │
│  - Download PDF/HTML to Supabase Storage             │
│  - Log filing metadata to filings table              │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐   ┌───────────────────────────┐
│ Monthly PDFs     │   │ 10-Q/10-K PDFs            │
│ (2 pages)        │   │ (100+ pages)              │
│                  │   │                           │
│ Full PDF →       │   │ pdfplumber → extract TOC  │
│ Claude API       │   │ + key sections → Claude   │
│ (base64 input)   │   │ API per section           │
└────────┬─────────┘   └─────────┬─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────────────────┐
│  Structured Extraction                               │
│  - Claude returns JSON matching Pydantic schemas     │
│  - Validate against schema                           │
│  - Store structured metrics in Supabase              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Comparison Agent (Claude Opus)                      │
│  - Query prior period data from Supabase             │
│  - Generate delta analysis brief                     │
│  - Flag anomalies (>1-2 std dev from trend)          │
│  - Store analysis in agent_analyses table            │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Email Alert (Resend)                                │
│  - Summary brief with key deltas                     │
│  - Link to filing source                             │
│  - Sent to configured recipients                     │
└─────────────────────────────────────────────────────┘
```

## Project Structure

```
mreit-monitor/
├── CLAUDE.md                    # This file — project spec for Claude Code
├── README.md                    # Standard readme
├── pyproject.toml               # Python project config (uv/pip)
├── Procfile                     # Railway deployment
├── railway.toml                 # Railway config
├── .env.example                 # Environment variable template
├── src/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + lifespan (scheduler setup)
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py          # Pydantic Settings from env vars
│   │   └── companies.py         # Company registry (ARMOUR config, future companies)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py            # API endpoints (health, trigger, status)
│   │   └── dependencies.py      # Shared dependencies (supabase client, etc.)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── scheduler.py         # APScheduler setup and job definitions
│   │   ├── scraper.py           # IR page scraping (BeautifulSoup)
│   │   ├── edgar.py             # SEC EDGAR submissions API client
│   │   ├── downloader.py        # PDF/HTML download + Supabase Storage upload
│   │   ├── email_service.py     # Resend email sending
│   │   └── supabase_client.py   # Supabase client singleton
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── monthly_update.py    # Monthly PDF → Claude API → structured data
│   │   ├── earnings_release.py  # HTML earnings release → structured data
│   │   ├── quarterly_filing.py  # 10-Q/10-K PDF → pdfplumber + Claude
│   │   └── annual_report.py     # Annual report PDF handling
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── extraction_agent.py  # Claude API calls for structured extraction
│   │   ├── comparison_agent.py  # Period-over-period delta analysis
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── monthly_extraction.py   # Prompt + schema for monthly PDFs
│   │       ├── quarterly_extraction.py # Prompt + schema for quarterly data
│   │       └── comparison_analysis.py  # Prompt for comparative brief
│   └── models/
│       ├── __init__.py
│       ├── database.py          # Supabase table interaction helpers
│       ├── schemas.py           # Pydantic models for all extracted data
│       └── enums.py             # Filing types, company identifiers, etc.
├── supabase/
│   └── migrations/
│       └── 001_initial_schema.sql  # Full database schema
├── scripts/
│   ├── backfill_armour.py       # One-time backfill of 12 months of monthly updates
│   ├── test_extraction.py       # Test extraction on a single PDF
│   └── seed_companies.py        # Seed the companies table
├── tests/
│   ├── __init__.py
│   ├── test_scraper.py
│   ├── test_extraction.py
│   └── test_comparison.py
└── docs/
    ├── DATA_SOURCES.md          # Detailed source documentation
    ├── SCHEMAS.md               # Data model documentation
    └── DEPLOYMENT.md            # Railway deployment guide
```

## Key Implementation Details

### 1. Scheduler (src/services/scheduler.py)

Use APScheduler's `AsyncIOScheduler` with a `CronTrigger`. Register it in FastAPI's lifespan context manager.

```python
# Runs once daily at 6:00 AM Eastern Time
scheduler.add_job(
    poll_all_companies,
    CronTrigger(hour=6, minute=0, timezone="US/Eastern"),
    id="daily_poll",
    replace_existing=True,
)
```

During the 10th–24th of each month (when monthly updates typically post), optionally add a second poll at 4pm ET for faster detection. This is a future optimization — start with once daily.

### 2. IR Page Scraper (src/services/scraper.py)

For ARMOUR, scrape these pages:
- `https://www.armourreit.com/news-events/monthly-company-updates` — Monthly PDFs
- `https://www.armourreit.com/financials/quarterly-reports` — 10-Q/10-K PDFs + earnings release links
- `https://www.armourreit.com/financials/annual-reports` — Annual report PDFs
- `https://www.armourreit.com/news-events/news` — News releases (earnings, dividends)

Each company in the `companies` table has a JSON field `scrape_config` that defines which URLs to scrape and what CSS selectors to use for finding PDF links and news links.

ARMOUR's monthly updates page structure:
- Each entry is a date string + an `<a>` tag linking to `/static-files/{uuid}`
- The `title` attribute of the `<a>` tag contains the PDF filename (e.g., "March 2026 Company Update (1).pdf")
- Extract the date from the preceding text node and the PDF URL from the href

ARMOUR's quarterly reports page structure:
- Organized by year → quarter headers (H3)
- Each quarter has links to: Earnings Release (HTML page), 10-Q or 10-K PDF (static-files URL), Webcast link, optional Investor Presentation PDF
- Parse the year/quarter from headings, then extract all links within each quarter section

### 3. EDGAR Submissions API (src/services/edgar.py)

Free REST API, no auth required. Requires a User-Agent header with contact info per SEC policy.

```python
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

headers = {
    "User-Agent": "mREIT-Monitor contact@youremail.com",
    "Accept": "application/json",
}
```

The response JSON has `recentFilings` with `form` (8-K, 10-Q, 10-K), `filingDate`, `accessionNumber`, and `primaryDocument` fields. Check for new filings since the last poll timestamp stored in Supabase.

ARMOUR's CIK: `0001428205`

### 4. Monthly Update Extraction (src/parsers/monthly_update.py)

Send the full PDF to Claude API as base64. The prompt instructs Claude to extract ALL data into a structured JSON format matching the Pydantic schema.

Key extraction fields (see models/schemas.py for full schema):
- **Portfolio positions:** security_type, coupon, pct_portfolio, market_value_millions, effective_duration
- **Key metrics:** stock_price, debt_equity, implied_leverage, liquidity_millions, liquidity_pct_capital, market_cap_millions
- **Dividend info:** monthly_dividend, ex_date, record_date, pay_date, dividend_yield
- **Repo composition:** counterparty, principal_borrowed_millions, pct_of_repo, wtd_avg_original_term_days, wtd_avg_remaining_term_days, longest_maturity_days
- **Interest rate swaps:** maturity_bucket, notional_millions, wtd_avg_remaining_term_months, wtd_avg_rate
- **Hedge summary:** hedge_type, notional_millions
- **CPR data:** month, cpr_value (from the chart — Claude vision can read bar charts)
- **Footnotes:** list of footnote texts (for change detection)
- **As-of date:** The date the portfolio data is as of (from the PDF header)

The extraction prompt should explicitly tell Claude:
1. Extract every single number from every table
2. Return JSON matching the provided schema exactly
3. If a field is not found, return null (not a guess)
4. Note any new sections or fields not in the schema under an "unrecognized_data" key
5. Note any changes to footnote text compared to prior month (if prior footnotes are provided)

### 5. Quarterly/Annual Filing Extraction (src/parsers/quarterly_filing.py)

For 10-Q/10-K PDFs (100+ pages):
1. Use `pdfplumber` to extract all text and identify page ranges for key sections:
   - Financial Statements (Balance Sheet, Income Statement, Cash Flow)
   - Schedule of Investments (the detailed MBS holdings table)
   - Derivatives and Hedging tables
   - Management Discussion & Analysis (MD&A)
2. Extract those sections as text blocks
3. Send each section to Claude API with section-specific extraction prompts
4. For the investment schedule specifically — this contains every CUSIP and position — extract into a detailed holdings table

For earnings releases (HTML pages):
- Fetch the HTML, parse with BeautifulSoup
- Extract the headline metrics from the structured tables in the press release
- These are simpler and more predictable than the full 10-Q

### 6. Comparison Agent (src/agents/comparison_agent.py)

After structured extraction completes, query Supabase for the prior period's data:
- For monthly updates: prior month's monthly_metrics + portfolio_positions
- For quarterly: prior quarter's quarterly_metrics

Send both periods' data to Claude (Opus for quality) with a comparison prompt that asks for:

1. **Portfolio composition changes:** Which coupons gained/lost allocation? What's the net duration shift?
2. **Leverage & liquidity:** Did debt-equity or implied leverage change? Liquidity as % of capital?
3. **Hedging shifts:** Changes in swap notional, maturity profile, or hedge composition?
4. **Repo changes:** Counterparty concentration shifts? Term changes?
5. **Dividend coverage:** Is distributable earnings covering the dividend?
6. **Book value movement:** Direction and magnitude
7. **Anomaly flags:** Any metric that moved more than its typical monthly/quarterly range
8. **New/removed items:** Anything in this period that wasn't in the prior period
9. **Footnote changes:** Any wording changes in the footnotes/disclaimers

The output is stored in `agent_analyses` table and included in the email alert.

### 7. Email Alerts (src/services/email_service.py)

Use Resend API. Send a well-formatted HTML email with:
- Subject: "[mREIT Monitor] ARMOUR — March 2026 Monthly Update Processed"
- Header section with company name, filing type, date
- Key metrics summary table (current vs prior, with delta)
- Agent analysis brief (the comparison narrative)
- Anomaly flags highlighted in yellow/red
- Link to the original filing source
- Link to the raw data in Supabase (or future dashboard)

### 8. Manual Trigger Endpoints (src/api/routes.py)

```
GET  /health                              — Health check
POST /trigger/poll/{company_ticker}       — Manually trigger a poll for a company
POST /trigger/process                     — Manually process a specific filing URL
POST /trigger/backfill/{company_ticker}   — Trigger historical backfill
GET  /status/latest/{company_ticker}      — Get latest processed filing info
GET  /status/filings/{company_ticker}     — List all processed filings
```

## Environment Variables

```
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Resend
RESEND_API_KEY=re_...
ALERT_EMAIL_TO=heath@example.com
ALERT_EMAIL_FROM=alerts@yourdomain.com

# SEC EDGAR
EDGAR_USER_AGENT=mREIT-Monitor heath@example.com

# App
LOG_LEVEL=INFO
ENVIRONMENT=production
```

## Data Flow Example: Monthly Update

1. **6:00 AM ET** — Scheduler fires `poll_all_companies()`
2. **Scraper** fetches `https://www.armourreit.com/news-events/monthly-company-updates`
3. **Scraper** finds a new PDF link not in the `filings` table → returns the URL
4. **Downloader** fetches the PDF, uploads to Supabase Storage (`filings/armour/monthly/2026-03.pdf`)
5. **Downloader** inserts a row into `filings` table with status `pending`
6. **Monthly parser** reads the PDF from storage, base64 encodes it
7. **Extraction agent** sends PDF to Claude Sonnet API with the monthly extraction prompt
8. **Claude** returns structured JSON matching the Pydantic schema
9. **Parser** validates the JSON, inserts into `monthly_metrics`, `portfolio_positions`, `repo_positions`, `swap_positions`, `hedge_summary` tables
10. **Parser** updates `filings` row status to `extracted`
11. **Comparison agent** queries prior month's data from Supabase
12. **Comparison agent** sends current + prior data to Claude Opus with comparison prompt
13. **Claude** returns the comparative analysis brief
14. **Agent** stores the brief in `agent_analyses` table
15. **Email service** composes and sends the alert email via Resend
16. **Parser** updates `filings` row status to `completed`

## ARMOUR Monthly Update PDF Structure Reference

Based on the March 2026 PDF, every monthly update contains these sections:

### Page 1: Portfolio & Key Data
- **Header:** Company name, "Monthly Update", month/year
- **Portfolio table:** Columns = Security type, % of Portfolio, Market Value (millions), Effective Duration
  - Rows: Agency CMBS, 30Y Fixed Rate Pools (with sub-rows per coupon: 2.0s through 6.5s, split by Conventionals and Ginnie Mae), Net TBA Positions, US Treasury Long Positions, Total Portfolio
- **Key Data box:** Stock Price, Debt-Equity, Implied Leverage, Liquidity (millions), Liquidity as % of Capital, Market Cap
- **Dividend box:** Monthly Common Dividend, Ex-Date, Record Date, Pay Date, Current Yield
- **CPR chart:** Bar chart showing portfolio CPR by month (trailing ~26 months)

### Page 2: Repo, Swaps, Hedges
- **Repo Composition table:** Columns = Counterparty, Principal Borrowed (millions), % of Repo, Wtd Avg Original Term (days), Wtd Avg Remaining Term (days), Longest Maturity (days)
  - Rows: BUCKLER Securities LLC, All Other Counterparties, Total
- **Interest Rate Swaps table:** Columns = Maturity bucket (months), Notional Amount (millions), Wtd Avg Remaining Term (months), Wtd Avg Rate
  - Rows: 0-12, 13-24, 25-36, 37-48, 49-60, 61-72, 73-84, 85-96, 97-108, 109-120, >120, Total
- **Hedge Type summary:** Hedge Type, Notional (millions) — Interest Rate Swaps and Treasury Futures
- **Forward-looking disclaimer paragraph**
- **Footnotes (numbered 1-6)**

### Data as-of dates
- Portfolio data: as of end of prior month (e.g., 02/28/26 for March 2026 update)
- CPR: as of a date ~1 week after month-end (e.g., 03/05/26)
- Stock price and key data: as of end of prior month

## Posting Schedule

Monthly updates post between the **12th–17th** of each month (non-earnings months) or the **22nd–23rd** (earnings-quarter months). Almost always on a Friday (non-earnings) or Wednesday (earnings). Daily polling at 6am ET is sufficient.

Earnings releases post the same day as the quarterly company update in earnings months (April, July, October, January/February for Q4).

## Backfill Strategy

For the initial 12-month backfill of ARMOUR monthly updates, use `scripts/backfill_armour.py`:

1. Fetch the monthly updates page
2. Extract all PDF URLs with dates from March 2025 through March 2026
3. Process each PDF sequentially (with rate limiting for Claude API)
4. Skip comparison agent on the oldest month (no prior data)
5. Run comparison agent on each subsequent month against the prior month's data

PDF URLs for the 12-month backfill (extracted from the IR page):

```python
ARMOUR_MONTHLY_BACKFILL = [
    ("2025-03", "https://www.armourreit.com/static-files/d0ebe47c-bc3c-4db7-9211-4765d82a3d71"),
    ("2025-04", "https://www.armourreit.com/static-files/2e359796-86ae-4c9a-9cce-47fc8ff2bcb2"),
    ("2025-05", "https://www.armourreit.com/static-files/a9e91427-7c9e-4886-8aaf-a8b4a13c4ae7"),
    ("2025-06", "https://www.armourreit.com/static-files/6352ff4f-4019-4cd8-9875-043b51bffc3a"),
    ("2025-07", "https://www.armourreit.com/static-files/5cd266ad-2264-4207-9370-d17b09d160c2"),
    ("2025-08", "https://www.armourreit.com/static-files/d090ab31-c67a-4dc2-880e-42904355425c"),
    ("2025-09", "https://www.armourreit.com/static-files/a6cc08fe-f154-4a7a-b7b1-699cfd08335e"),
    ("2025-10", "https://www.armourreit.com/static-files/50a84238-6dd3-4051-a3ee-3ea7a8276791"),
    ("2025-11", "https://www.armourreit.com/static-files/3288975d-7fbf-4b9a-99a0-695ade9f9c42"),
    ("2025-12", "https://www.armourreit.com/static-files/1942b9f3-78b4-44b8-bea5-b9f3251a49ac"),
    ("2026-01", "https://www.armourreit.com/static-files/6b3741b5-1cb3-4f01-8895-e8903e64b8d0"),
    ("2026-02", "https://www.armourreit.com/static-files/68039465-ebb5-49ba-8cc6-33e6f20ba32e"),
    ("2026-03", "https://www.armourreit.com/static-files/c40ff395-3917-41f6-8698-19c87315f4bc"),
]
```

## Adding New Companies

To add a new mREIT (e.g., AGNC):

1. Add a row to the `companies` table with CIK, ticker, name, and `scrape_config` JSON
2. The `scrape_config` defines:
   - Monthly updates URL + CSS selector pattern
   - Quarterly reports URL + CSS selector pattern
   - News page URL + CSS selector pattern
   - Any company-specific parsing quirks
3. The extraction schemas are shared across companies (they all report similar metrics)
4. The comparison agent works identically — it just pulls from the same tables filtered by company_id

## Error Handling

- All scraper/downloader operations wrapped in try/except with structured logging
- Failed extractions: set filing status to `extraction_failed`, log the error, skip comparison/email
- Claude API errors: retry up to 3 times with exponential backoff
- Validation failures: store the raw Claude response in `filings.raw_extraction_json` for debugging, set status to `validation_failed`
- Email failures: log but don't block the pipeline — data is already stored
- If a monthly update adds a new field not in the schema, the `unrecognized_data` key captures it, and an alert is included in the email

## Testing Strategy

- Unit tests for scraper (mock HTML responses)
- Unit tests for schema validation (known good/bad JSON)
- Integration test: download a real ARMOUR PDF, run extraction, validate output
- The `scripts/test_extraction.py` script processes a single PDF end-to-end for manual verification
