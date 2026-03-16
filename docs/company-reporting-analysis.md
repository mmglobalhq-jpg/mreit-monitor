# Company Reporting Analysis & Universal Agent Prompt

## Company-by-Company Reporting Profiles

---

### 1. ARMOUR Residential (ARR) — Already Implemented
- **Ticker:** ARR | **CIK:** 0001428205 | **Focus:** Pure Agency RMBS
- **Monthly Updates:** ✅ Yes — PDF posted to website + SEC (8-K). Detailed portfolio data, coupons, CPR, book value, leverage.
- **Quarterly Earnings:** Press release + presentation
- **Financial Supplement:** Embedded in monthly update PDFs
- **SEC Filings:** 10-Q, 10-K, 8-K
- **Investor Presentations:** Occasional
- **Cadence:** Monthly PDF is the primary data source. Richest detail of all six companies.

---

### 2. Bimini Capital (BMNM)
- **Ticker:** BMNM | **CIK:** 0001275477 | **Focus:** Agency RMBS + Advisory (manages Orchid Island Capital)
- **Monthly Updates:** ❌ None
- **Quarterly Earnings:** Press release via GlobeNewswire, filed as 8-K exhibit. Includes balance sheet, income statement, MBS segment detail, advisory revenues.
- **Financial Supplement:** ❌ None — all data is in the earnings press release
- **SEC Filings:** 10-Q, 10-K, 8-K
- **Investor Presentations:** ❌ None found (smallest company in the group)
- **Key Differences from ARMOUR:**
  - No monthly cadence — quarterly only
  - Two business segments: MBS portfolio + advisory services (Orchid)
  - Much smaller portfolio — data is less granular
  - Orchid Island performance directly affects Bimini's advisory revenue
  - Press release is the primary data source (no separate supplement)
- **Data Sources:**
  - `https://www.biminicapital.com/financials/quarterly-results`
  - `https://www.biminicapital.com/financials/sec-filings`
  - `https://www.biminicapital.com/news`
  - EDGAR: CIK 0001275477

---

### 3. Chimera Investment (CIM)
- **Ticker:** CIM | **CIK:** 0001409493 | **Focus:** Hybrid — Agency RMBS, Non-Agency RMBS, residential loans, MSRs, origination (HomeXpress)
- **Monthly Updates:** ❌ None
- **Quarterly Earnings:** Press release (8-K) + Financial Supplement (separate document)
- **Financial Supplement:** ✅ Yes — detailed tables for portfolio composition, net interest income, financing, securitization activity
- **SEC Filings:** 10-Q, 10-K, 8-K
- **Investor Presentations:** ✅ Yes — quarterly presentation PDFs filed with SEC
- **Key Differences from ARMOUR:**
  - No monthly cadence — quarterly only
  - Hybrid REIT: invests in BOTH Agency and Non-Agency assets
  - Has a mortgage origination subsidiary (HomeXpress) — origination volume data
  - Separate financial supplement document (not embedded in press release)
  - Investor presentation is a separate filing from the supplement
  - Multiple asset classes: residential loans, Non-Agency RMBS, Agency RMBS, BPLs, MSRs, CMBS
  - Securitization activity details
- **Data Sources:**
  - `https://www.chimerareit.com/financial-information/financial-results`
  - `https://www.chimerareit.com/sec-filings/all-sec-filings`
  - `https://www.chimerareit.com/news-events/press-releases`
  - EDGAR: CIK 0001409493

---

### 4. AGNC Investment (AGNC)
- **Ticker:** AGNC | **CIK:** 0001423689 | **Focus:** Pure Agency RMBS (closest to ARMOUR)
- **Monthly Updates:** ❌ No formal monthly PDF. Provides monthly estimated net book value via press release (typically mid-month).
- **Quarterly Earnings:** Press release (8-K) — VERY detailed, functions as its own supplement. Includes full portfolio breakdown, coupon distribution, TBA positions, hedge book, leverage, CPR, net spread tables.
- **Financial Supplement:** ❌ No separate document — the earnings release IS the supplement (20+ pages of tables)
- **SEC Filings:** 10-Q, 10-K, 8-K
- **Investor Presentations:** ✅ Listed on events page, occasional
- **Key Differences from ARMOUR:**
  - No monthly PDF (but monthly book value estimate press releases)
  - Quarterly earnings release is extremely detailed — portfolio by coupon, tenor, TBA detail, hedge composition, leverage tables
  - Largest pure Agency REIT — $94.8B portfolio
  - TBA securities are a significant portfolio component ($13B+)
  - CRT and non-Agency bucket is tiny ($0.7B)
  - Comprehensive hedge disclosure: swaps, swaptions, SOFR futures, Treasuries
- **Data Sources:**
  - `https://investors.agnc.com/financial-information/quarterly-results`
  - `https://investors.agnc.com/financial-information/sec-filings`
  - `https://investors.agnc.com/annual-reports`
  - `https://investors.agnc.com/events-and-presentations/upcoming-events`
  - EDGAR: CIK 0001423689

---

### 5. Annaly Capital (NLY)
- **Ticker:** NLY | **CIK:** 0001043219 | **Focus:** Agency RMBS + Residential Credit + MSR (three segments)
- **Monthly Updates:** ❌ None
- **Quarterly Earnings:** Press release (8-K) + Financial Supplement (separate) + Investor Presentation (separate)
- **Financial Supplement:** ✅ Yes — very detailed. Balance sheet rollforward, NIM waterfall, EAD reconciliation, portfolio composition by type/coupon/duration, financing data, hedge data. Multi-quarter comparison built in.
- **Investor Presentations:** ✅ Yes — separate quarterly PDF with strategic commentary, market outlook, portfolio positioning. Filed with SEC.
- **SEC Filings:** 10-Q, 10-K, 8-K
- **Key Differences from ARMOUR:**
  - No monthly cadence — quarterly only
  - THREE published documents per quarter: earnings release, financial supplement, investor presentation
  - Three business segments: Agency MBS, Residential Credit, MSR
  - Largest mREIT overall (~$132B portfolio)
  - Financial supplement has pre-built period-over-period tables (5 quarters)
  - PAA (premium amortization adjustment) is a key non-GAAP metric
  - MSR and residential credit data requires different extraction fields
- **Data Sources:**
  - `https://www.annaly.com/investors/earnings-and-financials/quarterly-earnings`
  - `https://www.annaly.com/investors/earnings-and-financials/annual-reports`
  - `https://www.annaly.com/investors/earnings-and-financials/presentations/2026`
  - `https://www.annaly.com/investors/events`
  - EDGAR: CIK 0001043219

---

### 6. Dynex Capital (DX)
- **Ticker:** DX | **CIK:** 0000826675 | **Focus:** Agency RMBS + Agency CMBS
- **Monthly Updates:** ⚠️ Partial — Monthly dividend declaration press releases sometimes include market commentary and estimated book value (not every month, and not structured data)
- **Quarterly Earnings:** Press release (8-K) with detailed tables
- **Financial Supplement:** ❌ No separate supplement — data is in the press release
- **Investor Presentations:** ✅ Yes — quarterly presentation PDF with market outlook, portfolio positioning, financing/hedge data. Filed with SEC.
- **SEC Filings:** 10-Q, 10-K, 8-K
- **Key Differences from ARMOUR:**
  - Monthly dividend announcements may contain market commentary (unstructured)
  - Both Agency RMBS AND Agency CMBS (unique in this group)
  - Quarterly presentation is rich with market analysis and positioning commentary
  - Internally managed (like Annaly, unlike ARMOUR/Bimini)
  - Detailed TBA and hedge data in earnings release
  - Deferred tax hedge gains are a notable feature
- **Data Sources:**
  - `https://www.dynexcapital.com/investors/news-events/press-releases`
  - `https://www.dynexcapital.com/investors/financial-info/financial-results`
  - `https://www.dynexcapital.com/investors/sec-filings/all-sec-filings`
  - `https://www.dynexcapital.com/investors/news-events/presentations`
  - EDGAR: CIK 0000826675

---

## Reporting Pattern Matrix

| Feature | ARR | BMNM | CIM | AGNC | NLY | DX |
|---|---|---|---|---|---|---|
| Monthly Updates | ✅ PDF | ❌ | ❌ | ⚠️ BV estimate | ❌ | ⚠️ Div + commentary |
| Quarterly Press Release | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Financial Supplement | In PDF | ❌ | ✅ Separate | In press release | ✅ Separate | ❌ |
| Investor Presentation | Occasional | ❌ | ✅ Quarterly | Occasional | ✅ Quarterly | ✅ Quarterly |
| 10-Q / 10-K | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Agency MBS | ✅ Pure | ✅ Pure | ✅ Partial | ✅ Pure | ✅ Primary | ✅ Primary |
| Non-Agency / Credit | ❌ | ❌ | ✅ Major | ❌ | ✅ Segment | ❌ |
| MSR | ❌ | ❌ | ✅ | ❌ | ✅ Segment | ❌ |
| CMBS | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ Agency |
| Mortgage Origination | ❌ | ❌ | ✅ HomeXpress | ❌ | ❌ | ❌ |

---

## Universal Design Principles

### The Core Problem
Every company publishes different documents, at different frequencies, in different formats, with different data fields. But the SUMMARY AGENT doesn't care — it consumes text and produces analysis. The key is making the **ingestion layer** flexible while keeping the **analysis layer** universal.

### Architecture: Three-Layer Approach

```
Layer 1: SCRAPER (company-specific)
  Each company gets its own scraper config that knows:
  - Where to find documents (URLs, EDGAR CIK)
  - What document types to expect
  - What cadence to check (monthly vs quarterly)
  - How to detect new postings

Layer 2: EXTRACTION (document-type-specific, not company-specific)
  Extractors are organized by document FORMAT, not company:
  - press_release_extractor (handles all earnings press releases)
  - financial_supplement_extractor (handles CIM/NLY supplements)
  - investor_presentation_extractor (handles all presentations)
  - monthly_update_extractor (handles ARR monthly PDFs)
  - sec_filing_extractor (handles 10-Q/10-K for all companies)
  Each extractor uses Claude API with a document-type prompt.
  Output is normalized into a common schema with company-specific
  fields stored in a flexible JSONB column.

Layer 3: SUMMARY AGENT (universal)
  The summary agent we already designed. It consumes ALL extracted
  data for a company+period and produces the standardized report.
  It doesn't care what document types fed it — it works from the
  extracted data in Supabase.
```

### What This Means for the Config

Each company is defined by a config that tells the system what to look for:

```python
COMPANY_REGISTRY = {
    "ARR": {
        "name": "ARMOUR Residential REIT",
        "cik": "0001428205",
        "document_types": ["monthly_update", "quarterly_earnings", "sec_filing"],
        "monthly_update_url": "https://www.armourreit.com/news-events/monthly-company-updates",
        "quarterly_url": "https://www.armourreit.com/financials/quarterly-reports",
        "news_url": "https://www.armourreit.com/news-events/news",
        "check_cadence": "weekly",  # Check weekly since monthly updates
        "primary_focus": ["agency_rmbs"],
    },
    "BMNM": {
        "name": "Bimini Capital Management",
        "cik": "0001275477",
        "document_types": ["quarterly_earnings", "sec_filing"],
        "quarterly_url": "https://www.biminicapital.com/financials/quarterly-results",
        "sec_filings_url": "https://www.biminicapital.com/financials/sec-filings",
        "news_url": "https://www.biminicapital.com/news",
        "check_cadence": "weekly",
        "primary_focus": ["agency_rmbs", "advisory_services"],
        "notes": "Also track Orchid Island Capital performance for advisory revenue context",
    },
    "CIM": {
        "name": "Chimera Investment Corporation",
        "cik": "0001409493",
        "document_types": ["quarterly_earnings", "financial_supplement", "investor_presentation", "sec_filing"],
        "quarterly_url": "https://www.chimerareit.com/financial-information/financial-results",
        "sec_filings_url": "https://www.chimerareit.com/sec-filings/all-sec-filings",
        "press_releases_url": "https://www.chimerareit.com/news-events/press-releases",
        "check_cadence": "weekly",
        "primary_focus": ["agency_rmbs", "non_agency_rmbs", "residential_loans", "msr", "cmbs", "origination"],
        "notes": "Hybrid REIT. Financial supplement is a separate document from press release. HomeXpress origination data.",
    },
    "AGNC": {
        "name": "AGNC Investment Corp",
        "cik": "0001423689",
        "document_types": ["quarterly_earnings", "monthly_book_value", "investor_presentation", "sec_filing"],
        "quarterly_url": "https://investors.agnc.com/financial-information/quarterly-results",
        "sec_filings_url": "https://investors.agnc.com/financial-information/sec-filings",
        "events_url": "https://investors.agnc.com/events-and-presentations/upcoming-events",
        "annual_reports_url": "https://investors.agnc.com/annual-reports",
        "check_cadence": "weekly",
        "primary_focus": ["agency_rmbs", "tba_securities"],
        "notes": "Earnings press release IS the financial supplement (20+ pages of tables). Monthly BV estimate press releases. Largest pure Agency REIT.",
    },
    "NLY": {
        "name": "Annaly Capital Management",
        "cik": "0001043219",
        "document_types": ["quarterly_earnings", "financial_supplement", "investor_presentation", "sec_filing"],
        "quarterly_url": "https://www.annaly.com/investors/earnings-and-financials/quarterly-earnings",
        "annual_reports_url": "https://www.annaly.com/investors/earnings-and-financials/annual-reports",
        "presentations_url": "https://www.annaly.com/investors/earnings-and-financials/presentations/2026",
        "events_url": "https://www.annaly.com/investors/events",
        "check_cadence": "weekly",
        "primary_focus": ["agency_rmbs", "residential_credit", "msr"],
        "notes": "Three segments: Agency, Residential Credit, MSR. Three docs per quarter: press release, supplement, presentation. Largest mREIT overall.",
    },
    "DX": {
        "name": "Dynex Capital",
        "cik": "0000826675",
        "document_types": ["quarterly_earnings", "investor_presentation", "monthly_dividend", "sec_filing"],
        "quarterly_url": "https://www.dynexcapital.com/investors/financial-info/financial-results",
        "sec_filings_url": "https://www.dynexcapital.com/investors/sec-filings/all-sec-filings",
        "press_releases_url": "https://www.dynexcapital.com/investors/news-events/press-releases",
        "presentations_url": "https://www.dynexcapital.com/investors/news-events/presentations",
        "check_cadence": "weekly",
        "primary_focus": ["agency_rmbs", "agency_cmbs"],
        "notes": "Monthly dividend press releases sometimes include market commentary and BV estimates. Both RMBS and CMBS. Quarterly presentations are rich with market analysis.",
    },
}
```

---

## Normalized Extraction Schema

The key to making this universal is a flexible extraction output that works for all document types:

```python
class UniversalExtraction(BaseModel):
    """Normalized extraction output for any company/document type."""
    # Identifiers
    company_ticker: str
    document_type: str  # "monthly_update", "quarterly_earnings", "financial_supplement", etc.
    document_date: date
    period_end: date
    fiscal_quarter: Optional[int] = None
    fiscal_year: int
    source_url: str

    # Universal Fields (present for all/most companies)
    book_value_per_share: Optional[float] = None
    earnings_per_share: Optional[float] = None
    dividends_per_share: Optional[float] = None
    economic_return_pct: Optional[float] = None
    net_interest_income: Optional[float] = None
    net_interest_spread: Optional[float] = None
    leverage_ratio: Optional[float] = None
    total_assets: Optional[float] = None
    portfolio_size: Optional[float] = None

    # Agency MBS Fields (ARR, AGNC, DX, portions of CIM/NLY)
    agency_rmbs_holdings: Optional[float] = None
    weighted_avg_coupon: Optional[float] = None
    weighted_avg_life: Optional[float] = None
    cpr_experience: Optional[float] = None
    tba_position: Optional[float] = None
    avg_asset_yield: Optional[float] = None
    avg_cost_of_funds: Optional[float] = None

    # Hedge Fields
    hedge_ratio: Optional[float] = None
    swap_notional: Optional[float] = None
    hedge_composition_notes: Optional[str] = None

    # Non-Agency / Credit Fields (CIM, NLY)
    non_agency_rmbs_holdings: Optional[float] = None
    residential_loan_portfolio: Optional[float] = None
    msr_portfolio: Optional[float] = None
    cmbs_holdings: Optional[float] = None
    origination_volume: Optional[float] = None

    # Flexible Fields
    management_commentary: Optional[str] = None
    key_highlights: list[str] = []
    portfolio_changes_notes: Optional[str] = None
    risk_factors_notes: Optional[str] = None

    # Raw catch-all for company-specific data
    additional_data: dict = {}

    # Metadata
    extraction_confidence: float = 0.0
    fields_extracted: list[str] = []
    fields_unavailable: list[str] = []
```

---

## Summary Report Triggers by Company

| Company | Monthly Summary | Quarterly Summary | Annual Summary | Ad-hoc |
|---|---|---|---|---|
| ARR | ✅ After monthly PDF | ✅ After Q earnings | ✅ After 10-K | Investor presentations |
| BMNM | ❌ N/A | ✅ After Q earnings | ✅ After 10-K | News releases |
| CIM | ❌ N/A | ✅ After earnings + supplement + presentation | ✅ After 10-K | Press releases |
| AGNC | ⚠️ After monthly BV estimate (lightweight) | ✅ After Q earnings | ✅ After 10-K | Events/presentations |
| NLY | ❌ N/A | ✅ After earnings + supplement + presentation | ✅ After 10-K | Presentations |
| DX | ⚠️ After monthly dividend (if commentary) | ✅ After earnings + presentation | ✅ After 10-K | Presentations |
