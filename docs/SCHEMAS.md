# Data Model — mREIT Monitor

## Database Tables

### companies
Company registry. One row per monitored mREIT.

### filings
Every document detected, downloaded, and processed. Tracks the full lifecycle from detection through extraction, comparison, and email alert. Status progression: `detected` → `downloaded` → `extracting` → `extracted` → `comparing` → `completed`.

### monthly_metrics
One row per company per month. Contains the headline numbers from monthly company updates: stock price, leverage, liquidity, dividend info, and portfolio/repo/swap totals.

### portfolio_positions
Granular coupon-level portfolio breakdown. Multiple rows per filing — one for each security type and coupon (e.g., "30y 5.5s Conventionals"). Includes subtotal rows for aggregation levels.

### repo_positions
Repurchase agreement breakdown by counterparty. Typically 3 rows per filing: BUCKLER (affiliate), All Other, and Total.

### swap_positions
Interest rate swap schedule by maturity bucket. ~12 rows per filing covering 0-12 months through >120 months, plus Total.

### quarterly_metrics
Headline metrics from quarterly earnings releases. One row per company per quarter. Contains GAAP income, distributable earnings, spreads, book value, returns, leverage, and capital issuance data.

### cpr_data
Monthly CPR values extracted from the CPR chart in monthly updates. One row per company per month.

### agent_analyses
AI-generated comparison briefs. Stores the full analysis narrative, structured list of changes, and anomaly flags. Linked to the filing that triggered the analysis.

### filing_footnotes
Tracked footnotes from monthly updates, with change detection against prior month.

### poll_log
Audit log of every polling run for debugging and monitoring.

## Pydantic Schemas (src/models/schemas.py)

### MonthlyUpdateExtraction
Complete extraction schema for monthly PDFs. This is the JSON shape Claude returns. Contains nested models for key metrics, dividend info, portfolio positions, repo positions, swap positions, hedge summary, CPR data, and footnotes.

### QuarterlyEarningsExtraction
Extraction schema for quarterly earnings press releases.

### ComparisonAnalysis
Output schema for the comparison agent. Contains executive summary, structured metric changes, portfolio shifts, detailed analysis sections, anomaly flags, and new/removed items.

## Key Relationships

```
companies (1) ──── (*) filings
filings   (1) ──── (*) monthly_metrics (usually 1:1)
filings   (1) ──── (*) portfolio_positions
filings   (1) ──── (*) repo_positions
filings   (1) ──── (*) swap_positions
filings   (1) ──── (*) quarterly_metrics (usually 1:1)
filings   (1) ──── (*) agent_analyses
filings   (1) ──── (*) filing_footnotes
filings   (1) ──── (*) cpr_data
companies (1) ──── (*) poll_log
```
