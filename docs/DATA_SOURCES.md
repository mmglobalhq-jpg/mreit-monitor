# Data Sources — mREIT Monitor

## ARMOUR Residential REIT (ARR)

### Monthly Company Updates
- **URL:** https://www.armourreit.com/news-events/monthly-company-updates
- **Format:** PDF (2 pages)
- **Frequency:** Monthly, posted 12th–17th (non-earnings months) or 22nd–23rd (earnings months)
- **Day of week:** Almost always Friday (non-earnings) or Wednesday (earnings)
- **Content:**
  - Page 1: Portfolio allocation by coupon, key metrics (price, leverage, liquidity), dividend info, CPR chart
  - Page 2: Repo composition, interest rate swap schedule, hedge summary, footnotes
- **PDF URL pattern:** `https://www.armourreit.com/static-files/{uuid}`
- **As-of date:** Portfolio data is as of prior month-end. CPR data as of ~1 week after month-end.

### Quarterly Reports
- **URL:** https://www.armourreit.com/financials/quarterly-reports
- **Content per quarter:**
  - **Earnings Release** — HTML press release on GlobeNewswire, linked from IR page
  - **10-Q** (Q1-Q3) or **10-K** (Q4) — PDF, 100+ pages, full SEC filing
  - **Webcast** — Conference call replay link (not processed)
  - **Investor Presentation** — PDF slide deck (occasional, e.g., Q4 2025)
- **Posting schedule:** Earnings releases post after market close on earnings day. 10-Q/10-K files may post same day or within a few days.

### Annual Reports
- **URL:** https://www.armourreit.com/financials/annual-reports  
- **Content:**
  - **Annual Report** — Glossy shareholder report PDF
  - **Proxy Statement** — Governance and compensation PDF
  - **10-K** — Same as quarterly reports page (overlap)
- **Frequency:** Once per year, typically February/March for prior year

### News / Press Releases
- **URL:** https://www.armourreit.com/news-events/news
- **Content:** Dividend announcements, earnings releases, webcast notices
- **Frequency:** Multiple per month (dividend confirmations, guidance, etc.)

### SEC EDGAR
- **Submissions API:** `https://data.sec.gov/submissions/CIK0001428205.json`
- **CIK:** 0001428205
- **Key form types:**
  - **8-K** — Contains monthly company updates as exhibits
  - **10-Q** — Quarterly reports
  - **10-K** — Annual report
  - **DEF 14A** — Proxy statement
- **XBRL data:** Available via `https://data.sec.gov/api/xbrl/companyfacts/CIK0001428205.json`

## Future Companies

| Ticker | Name | CIK | Monthly Updates? |
|--------|------|-----|-----------------|
| AGNC | AGNC Investment Corp. | 0001423689 | Monthly factor updates (different format) |
| NLY | Annaly Capital Management | 0001043219 | Quarterly supplements only |
| TWO | Two Harbors Investment | 0001576996 | Quarterly supplements |
| DX | Dynex Capital | 0000826675 | Monthly commentary |

## Posting Calendar Reference (ARMOUR)

Based on 15 months of data (Jan 2025 — Mar 2026):

| Type | Typical Day | Day of Week | Notes |
|------|-------------|-------------|-------|
| Monthly update (non-earnings) | 12th–17th | Friday | 10/11 months on Friday |
| Monthly update (earnings month) | 22nd–23rd | Wednesday | Same day as earnings release |
| Quarterly earnings release | 18th–23rd | After market close | Varies by quarter |
| 10-Q/10-K filing | Same week as earnings | Varies | Sometimes same day, sometimes +1-3 days |
| Dividend announcement | ~25th–29th | Varies | Monthly, announces next month's dividend |
| Dividend confirmation | 1st of month | Varies | Confirms previously announced dividend |
