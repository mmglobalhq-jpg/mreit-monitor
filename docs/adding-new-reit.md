# Adding a New mREIT to the Monitor

Step-by-step process for adding a company and loading historical data.

## 1. Register the company

**File:** `src/config/company_registry.py`

Add a new entry to `COMPANY_CONFIGS`:

```python
"TICKER": CompanyConfig(
    name="Company Name",
    cik="CIK_NUMBER",  # Pad with zeros to 10 digits
    document_types=["quarterly_earnings", "sec_filing"],
    scrape_sources=[
        ScrapeSource(type="website", url="https://company.com/financial-results", doc_type="quarterly_earnings"),
        ScrapeSource(type="edgar", filing_types=["10-Q", "10-K", "8-K"]),
    ],
    primary_focus=["agency_rmbs"],  # or ["agency_rmbs", "agency_cmbs"], etc.
    has_monthly_update=False,  # True only for ARR-style monthly PDFs
    has_financial_supplement=False,
    has_investor_presentation=True,
    notes="Any relevant context for extraction prompts.",
)
```

Then add the company to the Supabase `companies` table (via API or directly).

## 2. Find SEC filing URLs

```bash
# Get filing index from EDGAR
curl -sA "mREIT-Monitor user@email.com" \
  "https://data.sec.gov/submissions/CIK{padded_cik}.json" \
  | python3 -c "
import json,sys
data = json.load(sys.stdin)
recent = data['filings']['recent']
for i in range(len(recent['form'])):
    if recent['form'][i] in ('10-K','10-Q'):
        acc = recent['accessionNumber'][i].replace('-','')
        doc = recent['primaryDocument'][i]
        print(f\"{recent['form'][i]:6s} {recent['filingDate'][i]}  https://www.sec.gov/Archives/edgar/data/{data['cik']}/{acc}/{doc}\")
"
```

## 3. Add presets to the processor script

**File:** `scripts/process_sec_filing.py`

Add to the `PRESETS` dict:

```python
"TICKER": {
    "10k-fy2025": {
        "url": "https://www.sec.gov/Archives/...",
        "doc_type": "sec_filing",
        "period_end": "2025-12-31",
        "fiscal_year": 2025,
        "fiscal_quarter": 4,
        "title": "TICKER FY 2025 10-K",
        "filing_date": "2026-02-XX",
    },
    "10q-q3-2025": { ... },
},
```

## 4. Process earnings releases

If the company has an earnings press release (8-K exhibit), process it first — it has headline metrics:

```bash
python -m scripts.test_universal_extraction --ticker TICKER
```

Or manually add to `TEST_DOCUMENTS` in `scripts/test_universal_extraction.py`.

## 5. Process SEC filings

```bash
# Process all presets (10-K + 10-Q):
python -m scripts.process_sec_filing --ticker TICKER --all-presets

# Or one at a time:
python -m scripts.process_sec_filing --ticker TICKER --preset 10k-fy2025
```

## 6. Verify extracted data

Check Supabase for accuracy:

```bash
# Check universal_extractions
curl -s "SUPABASE_URL/rest/v1/universal_extractions?company_id=eq.COMPANY_ID&select=period_end,book_value_per_share,portfolio_size,leverage_ratio" \
  -H "apikey: KEY" -H "Authorization: Bearer KEY"
```

Cross-reference key metrics against the source document:
- book_value_per_share
- earnings_per_share
- portfolio_size (total FV including CMBS and TBA)
- agency_rmbs_holdings (RMBS fair value only)
- leverage_ratio
- dividends_per_share

## 7. Generate the quarterly report

```bash
# Via API:
curl -X POST "REIT_MONITOR_URL/api/reports/generate" \
  -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"TICKER","report_type":"quarterly","year":2025,"quarter":4}'

# Or via the review page on mmglobal.us/reit-monitor/review
```

## 8. Verify the report

Check for:
- QoQ comparisons are accurate (current vs prior quarter)
- Dollar amounts match source documents
- Anti-AI-writing rules applied (no banned vocabulary)
- Verification pass ran (metadata.verified = true)
- Data gaps section flags anything missing

## 9. Send to subscribers

On the review page, click "Send to Subscribers" for the new report.

## Checklist for each company

- [ ] Company registered in `company_registry.py`
- [ ] Company exists in Supabase `companies` table
- [ ] Earnings releases extracted (Q3 + Q4 minimum)
- [ ] 10-K and/or 10-Q extracted
- [ ] Key metrics verified against source docs
- [ ] Quarterly report generated with QoQ comparison
- [ ] Report reviewed for accuracy
- [ ] Email sent to subscribers
