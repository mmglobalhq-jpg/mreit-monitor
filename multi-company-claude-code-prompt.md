# Claude Code Prompt — Universal Multi-Company mREIT Pipeline

## Context

Read `CLAUDE.md` first for the existing project architecture. Then read the companion document `company-reporting-analysis.md` (included below in this prompt) for the full analysis of how each company reports.

We're expanding the mREIT Monitor from ARMOUR-only to six companies. Each company reports differently — different documents, different cadences, different data granularity. The architecture needs to handle this without writing company-specific code for every new REIT we add.

The six companies are:

| Ticker | Company | CIK | Focus |
|---|---|---|---|
| ARR | ARMOUR Residential REIT | 0001428205 | Pure Agency RMBS |
| BMNM | Bimini Capital Management | 0001275477 | Agency RMBS + Advisory |
| CIM | Chimera Investment Corp | 0001409493 | Hybrid (Agency + Non-Agency + Loans + MSR + Origination) |
| AGNC | AGNC Investment Corp | 0001423689 | Pure Agency RMBS + TBA |
| NLY | Annaly Capital Management | 0001043219 | Agency RMBS + Residential Credit + MSR |
| DX | Dynex Capital | 0000826675 | Agency RMBS + Agency CMBS |

---

## What Exists Today

The existing pipeline handles ARMOUR only:
- Scraper → detects new monthly PDFs on armourreit.com
- Downloader → pulls PDFs
- Extraction agent → Claude API extracts structured data from PDFs
- Comparison agent → compares month-over-month
- Email service → sends report
- Summary agent → produces monthly/quarterly/annual summary reports (from our recent addition)

All data is stored in Supabase. The extraction models are ARMOUR-specific (MonthlyUpdateExtraction, etc).

---

## What to Build

### Phase 1: Company Registry & Config Layer

**Create `src/config/company_registry.py`**

Replace the current single-company config with a registry that defines each company's reporting profile. Each company entry should specify:

```python
COMPANY_REGISTRY = {
    "ARR": {
        "name": "ARMOUR Residential REIT",
        "cik": "0001428205",
        "document_types": ["monthly_update", "quarterly_earnings", "sec_filing"],
        "scrape_sources": [
            {"type": "website", "url": "https://www.armourreit.com/news-events/monthly-company-updates", "doc_type": "monthly_update"},
            {"type": "website", "url": "https://www.armourreit.com/financials/quarterly-reports", "doc_type": "quarterly_earnings"},
            {"type": "website", "url": "https://www.armourreit.com/news-events/news", "doc_type": "press_release"},
            {"type": "edgar", "filing_types": ["10-Q", "10-K", "8-K"]},
        ],
        "check_cadence": "weekly",
        "primary_focus": ["agency_rmbs"],
        "has_monthly_update": True,
        "has_financial_supplement": False,
        "has_investor_presentation": False,
    },
    "BMNM": {
        "name": "Bimini Capital Management",
        "cik": "0001275477",
        "document_types": ["quarterly_earnings", "sec_filing"],
        "scrape_sources": [
            {"type": "website", "url": "https://www.biminicapital.com/financials/quarterly-results", "doc_type": "quarterly_earnings"},
            {"type": "website", "url": "https://www.biminicapital.com/financials/sec-filings", "doc_type": "sec_filing"},
            {"type": "website", "url": "https://www.biminicapital.com/news", "doc_type": "press_release"},
            {"type": "edgar", "filing_types": ["10-Q", "10-K", "8-K"]},
        ],
        "check_cadence": "weekly",
        "primary_focus": ["agency_rmbs", "advisory_services"],
        "has_monthly_update": False,
        "has_financial_supplement": False,
        "has_investor_presentation": False,
        "notes": "Track Orchid Island Capital advisory revenue. Smallest company in group.",
    },
    "CIM": {
        "name": "Chimera Investment Corporation",
        "cik": "0001409493",
        "document_types": ["quarterly_earnings", "financial_supplement", "investor_presentation", "sec_filing"],
        "scrape_sources": [
            {"type": "website", "url": "https://www.chimerareit.com/financial-information/financial-results", "doc_type": "quarterly_earnings"},
            {"type": "website", "url": "https://www.chimerareit.com/sec-filings/all-sec-filings", "doc_type": "sec_filing"},
            {"type": "website", "url": "https://www.chimerareit.com/news-events/press-releases", "doc_type": "press_release"},
            {"type": "edgar", "filing_types": ["10-Q", "10-K", "8-K"]},
        ],
        "check_cadence": "weekly",
        "primary_focus": ["agency_rmbs", "non_agency_rmbs", "residential_loans", "msr", "cmbs", "origination"],
        "has_monthly_update": False,
        "has_financial_supplement": True,
        "has_investor_presentation": True,
        "notes": "Hybrid REIT. Separate financial supplement. HomeXpress origination data.",
    },
    "AGNC": {
        "name": "AGNC Investment Corp",
        "cik": "0001423689",
        "document_types": ["quarterly_earnings", "monthly_book_value", "investor_presentation", "sec_filing"],
        "scrape_sources": [
            {"type": "website", "url": "https://investors.agnc.com/financial-information/quarterly-results", "doc_type": "quarterly_earnings"},
            {"type": "website", "url": "https://investors.agnc.com/financial-information/sec-filings", "doc_type": "sec_filing"},
            {"type": "website", "url": "https://investors.agnc.com/events-and-presentations/upcoming-events", "doc_type": "investor_presentation"},
            {"type": "website", "url": "https://investors.agnc.com/annual-reports", "doc_type": "annual_report"},
            {"type": "edgar", "filing_types": ["10-Q", "10-K", "8-K"]},
        ],
        "check_cadence": "weekly",
        "primary_focus": ["agency_rmbs", "tba_securities"],
        "has_monthly_update": False,
        "has_financial_supplement": False,
        "has_investor_presentation": True,
        "notes": "Earnings press release IS the supplement (20+ pages). Monthly BV estimate press releases. Largest pure Agency REIT ($94.8B portfolio).",
    },
    "NLY": {
        "name": "Annaly Capital Management",
        "cik": "0001043219",
        "document_types": ["quarterly_earnings", "financial_supplement", "investor_presentation", "sec_filing"],
        "scrape_sources": [
            {"type": "website", "url": "https://www.annaly.com/investors/earnings-and-financials/quarterly-earnings", "doc_type": "quarterly_earnings"},
            {"type": "website", "url": "https://www.annaly.com/investors/earnings-and-financials/annual-reports", "doc_type": "annual_report"},
            {"type": "website", "url": "https://www.annaly.com/investors/earnings-and-financials/presentations/2026", "doc_type": "investor_presentation"},
            {"type": "website", "url": "https://www.annaly.com/investors/events", "doc_type": "events"},
            {"type": "edgar", "filing_types": ["10-Q", "10-K", "8-K"]},
        ],
        "check_cadence": "weekly",
        "primary_focus": ["agency_rmbs", "residential_credit", "msr"],
        "has_monthly_update": False,
        "has_financial_supplement": True,
        "has_investor_presentation": True,
        "notes": "Three segments: Agency, Residential Credit, MSR. Three docs per quarter. Largest mREIT overall (~$132B). PAA is key non-GAAP metric.",
    },
    "DX": {
        "name": "Dynex Capital",
        "cik": "0000826675",
        "document_types": ["quarterly_earnings", "investor_presentation", "monthly_dividend", "sec_filing"],
        "scrape_sources": [
            {"type": "website", "url": "https://www.dynexcapital.com/investors/financial-info/financial-results", "doc_type": "quarterly_earnings"},
            {"type": "website", "url": "https://www.dynexcapital.com/investors/sec-filings/all-sec-filings", "doc_type": "sec_filing"},
            {"type": "website", "url": "https://www.dynexcapital.com/investors/news-events/press-releases", "doc_type": "press_release"},
            {"type": "website", "url": "https://www.dynexcapital.com/investors/news-events/presentations", "doc_type": "investor_presentation"},
            {"type": "edgar", "filing_types": ["10-Q", "10-K", "8-K"]},
        ],
        "check_cadence": "weekly",
        "primary_focus": ["agency_rmbs", "agency_cmbs"],
        "has_monthly_update": False,
        "has_financial_supplement": False,
        "has_investor_presentation": True,
        "notes": "Monthly dividend press releases may include market commentary. Both RMBS and CMBS. Rich quarterly presentations.",
    },
}
```

### Phase 2: Database Migration — Multi-Company Support

**Create `supabase/migrations/003_multi_company.sql`**

The existing schema may need updates. Ensure:

1. The `companies` table can hold all 6 companies with their registry config
2. Add a `documents` table to track ALL document types (not just monthly PDFs):
   ```sql
   CREATE TABLE documents (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       company_id UUID REFERENCES companies(id),
       document_type TEXT NOT NULL,  -- 'monthly_update', 'quarterly_earnings', 'financial_supplement', 'investor_presentation', 'sec_filing', 'press_release', 'monthly_dividend'
       document_date DATE NOT NULL,
       period_end DATE,
       fiscal_quarter INT,
       fiscal_year INT,
       title TEXT,
       source_url TEXT,
       file_path TEXT,
       raw_content TEXT,
       content_hash TEXT,  -- For dedup / change detection
       created_at TIMESTAMPTZ DEFAULT now(),
       UNIQUE(company_id, document_type, source_url)
   );
   ```
3. Add a `universal_extractions` table with JSONB for flexible storage:
   ```sql
   CREATE TABLE universal_extractions (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       company_id UUID REFERENCES companies(id),
       document_id UUID REFERENCES documents(id),
       document_type TEXT NOT NULL,
       period_end DATE NOT NULL,
       fiscal_quarter INT,
       fiscal_year INT NOT NULL,
       -- Universal fields as columns for easy querying
       book_value_per_share NUMERIC,
       earnings_per_share NUMERIC,
       dividends_per_share NUMERIC,
       economic_return_pct NUMERIC,
       net_interest_spread NUMERIC,
       leverage_ratio NUMERIC,
       portfolio_size NUMERIC,
       agency_rmbs_holdings NUMERIC,
       weighted_avg_coupon NUMERIC,
       avg_asset_yield NUMERIC,
       avg_cost_of_funds NUMERIC,
       -- Flexible storage for everything else
       extraction_data JSONB NOT NULL,  -- Full UniversalExtraction serialized
       management_commentary TEXT,
       key_highlights JSONB,  -- list of strings
       extraction_confidence NUMERIC,
       created_at TIMESTAMPTZ DEFAULT now(),
       UNIQUE(document_id)
   );
   ```
4. Seed all 6 companies into the `companies` table

### Phase 3: Universal Extraction Agent

**Create `src/agents/universal_extractor.py`**

This replaces the ARMOUR-specific extraction agent with a document-type-aware extractor. The approach:

1. **One Claude API prompt per document type**, not per company. The prompt receives:
   - The document text/content
   - The company's registry config (so it knows what to look for)
   - The target output schema (UniversalExtraction)

2. **Document type prompts** (store in `src/agents/prompts/extraction_prompts.py`):
   - `QUARTERLY_EARNINGS_PROMPT` — Works for all 6 companies' press releases
   - `FINANCIAL_SUPPLEMENT_PROMPT` — Works for CIM and NLY supplements
   - `INVESTOR_PRESENTATION_PROMPT` — Works for CIM, AGNC, NLY, DX presentations
   - `MONTHLY_UPDATE_PROMPT` — Works for ARR monthly PDFs (keep existing)
   - `SEC_FILING_PROMPT` — Works for 10-Q/10-K from any company
   - `PRESS_RELEASE_PROMPT` — Works for general press releases, monthly dividends, etc.

3. **Each prompt should include this preamble:**
   ```
   You are extracting financial data from a {document_type} published by {company_name} ({ticker}).
   This company focuses on: {primary_focus}.
   Additional context: {notes}

   Extract all available data into the following structured format. If a field is not present
   in this document, set it to null — do not infer or calculate values not explicitly stated.
   For fields that ARE present, be precise — include exact figures, dates, and percentages.
   ```

4. **Output** is always `UniversalExtraction` — the same Pydantic model regardless of company or document type. Fields that don't apply get null.

### Phase 4: Universal Scraper

**Refactor `src/services/scraper.py`**

The scraper should iterate over the company registry and, for each company:

1. Check each `scrape_source` in the config
2. For website sources: fetch the page, detect new documents (by URL/title/date not previously seen)
3. For EDGAR sources: query EDGAR's full-text search or RSS for the company's CIK + filing types
4. Download new documents → store in `documents` table
5. Trigger extraction for each new document
6. After extraction completes, check if a summary should be triggered

**EDGAR integration** should be universal — it takes a CIK and filing types and returns new filings. The existing EDGAR client in the project should work for all 6 companies with no changes beyond passing the CIK.

**Website scraping** is the tricky part. Each company's IR page has different HTML structure. Options:
- **Option A (recommended):** Use Claude API to parse each IR page. Send the page HTML + "find all document links with their dates and types" → get back structured list. This is slower but works universally without writing CSS selectors per site.
- **Option B:** Write per-site scraping logic with BeautifulSoup/CSS selectors. Faster but brittle and requires maintenance when sites change.

Go with Option A for the initial build. We can optimize to Option B for specific high-frequency sites later.

### Phase 5: Summary Agent (already designed — wire it up for all companies)

The summary agent from our previous prompt should already work for all companies IF:
- It pulls from `universal_extractions` instead of ARMOUR-specific tables
- It uses the company registry to know what document types to look for
- It handles companies with no monthly data (BMNM, CIM, NLY) by only generating quarterly/annual summaries

Update the summary agent's **context gathering** to:
```python
def gather_context(company_id, period_start, period_end):
    """Pull all extractions for this company in this period."""
    extractions = supabase.table("universal_extractions") \
        .select("*") \
        .eq("company_id", company_id) \
        .gte("period_end", period_start) \
        .lte("period_end", period_end) \
        .execute()

    documents = supabase.table("documents") \
        .select("*") \
        .eq("company_id", company_id) \
        .gte("document_date", period_start) \
        .lte("document_date", period_end) \
        .execute()

    return extractions, documents
```

The summary agent's system prompt (from our previous design) works as-is — it's already written to be company-agnostic:

```
Role:
Act as a financial institution analyst with deep expertise in REITs, banks, money managers, asset managers, and other financial institutions. Focus on the securities aspects of financial reports. Accuracy and detail take priority over speed.

Objective:
Review monthly, quarterly, and annual reports for securities activity. Detail any changes, trends, or commentary provided. Compare current reports to the prior month, quarter, and year. Additionally, analyze any supplemental presentations, investor materials, or documentation for information that can be derived about security performance, selection, strategy, or positioning. Any details on specific trades, coupons, yields, or bond characteristics should be included.

Data Sources:
You have access to the following, stored in Supabase:
- Monthly, quarterly, and annual reports pulled from company websites
- SEC filings via EDGAR
- Investor presentations and supplemental materials available on company websites

Focus Area:
The goal is to provide an up-to-date, factual view of securities activity, with a specific emphasis on agency MBS. Extract raw data from available sources and produce a thorough summary.

Guidelines:
- Do not stop until you have completed a comprehensive, factual report that gives insight into the current state of the company's securities activity.
- Do not fabricate information or make inferences. Report only what is explicitly stated or directly calculable from the source materials.
- If information for a section is not available, explicitly note that it is unavailable rather than omitting the section silently.

Output Format:
Produce a detailed email-style report with the following sections:
1. Overall Summary — Major themes and key takeaways across all reviewed materials
2. Securities Detail — Specific holdings, trades, coupons, yields, duration, and portfolio composition changes
3. Filing Highlights — Notable disclosures, risk factors, or commentary from SEC filings and reports
4. Performance & Activity — Period-over-period comparisons and trend analysis
5. Supplemental Materials — Insights derived from investor presentations or other non-standard disclosures
6. Data Gaps — Sections where source information was unavailable
```

### Phase 6: Scheduler Updates

Update the scheduler to run for all companies:

```python
for ticker, config in COMPANY_REGISTRY.items():
    # Check for new documents
    new_docs = scraper.check_for_updates(ticker)

    for doc in new_docs:
        # Extract
        extraction = universal_extractor.extract(doc)

        # Check if summary should trigger
        if should_generate_summary(ticker, doc):
            summary_agent.generate_summary(ticker, determine_period(doc))
```

Summary trigger logic:
- **ARR:** After monthly update extraction → monthly summary. After Q earnings → quarterly summary.
- **BMNM:** After Q earnings extraction → quarterly summary.
- **CIM:** After ALL quarterly docs (earnings + supplement + presentation) are extracted → quarterly summary. Wait for all three.
- **AGNC:** After Q earnings extraction → quarterly summary. After monthly BV press release → lightweight monthly note (optional).
- **NLY:** After ALL quarterly docs (earnings + supplement + presentation) are extracted → quarterly summary. Wait for all three.
- **DX:** After Q earnings + presentation are extracted → quarterly summary. After monthly dividend with commentary → lightweight monthly note (optional).

### Phase 7: Cross-Company Comparison (Future Enhancement)

Once all companies are running, add a cross-company comparison agent that:
- Compares all 6 companies for the same quarter
- Highlights relative positioning (leverage, portfolio size, returns, coupons)
- Identifies sector-wide trends vs company-specific moves
- This is a separate report from the per-company summaries

---

## Build Order

1. **Create company registry config** — get all 6 companies defined with their sources
2. **Run migration 003** — multi-company tables (documents, universal_extractions, seed companies)
3. **Build UniversalExtraction Pydantic model** in `src/models/schemas.py`
4. **Build document-type extraction prompts** — start with `QUARTERLY_EARNINGS_PROMPT` since all 6 companies have quarterly press releases
5. **Build universal extractor** — test against one quarterly earnings release from each company (use SEC URLs for the most recent Q4 2025 releases, which are all available)
6. **Test extraction quality** — verify the UniversalExtraction output makes sense for each company. Adjust prompts as needed.
7. **Refactor the scraper** to use company registry and handle multiple document types
8. **Update the summary agent** to pull from universal_extractions
9. **Wire up the scheduler** for all 6 companies
10. **Test end-to-end** for one company at a time: ARMOUR first (regression test), then AGNC (most similar to ARMOUR), then DX, BMNM, CIM, NLY (in order of increasing complexity)
11. **Cross-company comparison** — future phase

**Commit after each working step.** Start with Plan Mode and walk me through what you'd change before writing code.

---

## Test URLs for Initial Extraction Testing

Use these SEC-hosted documents for testing extraction (no scraping needed, direct URLs):

**ARR (Q4 2025):**
- Monthly update: via existing backfill URLs in companies.py

**BMNM (Q4 2025):**
- Earnings release: `https://www.globenewswire.com/news-release/2026/03/12/3255123/24159/en/Bimini-Capital-Management-Announces-Fourth-Quarter-and-Full-Year-2025-Results-and-Share-Repurchase-Plan.html`

**CIM (Q4 2025):**
- Earnings release: `https://www.sec.gov/Archives/edgar/data/0001409493/000140949326000007/pressrelease-q42025.htm`

**AGNC (Q4 2025):**
- Earnings release: `https://www.sec.gov/Archives/edgar/data/0001423689/000142368926000024/agnc8kexhibit991123125.htm`

**NLY (Q4 2025):**
- Financial supplement: `https://www.sec.gov/Archives/edgar/data/0001043219/000104321926000008/a2025q4finsupp991.htm`

**DX (Q4 2025):**
- Earnings release: `https://www.sec.gov/Archives/edgar/data/0000826675/000082667526000004/a4q25earningsrelease.htm`
