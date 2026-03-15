"""
Document-type-specific extraction prompts for the universal extraction pipeline.

Each prompt pair (system + user) targets a specific document type but works
across companies. Company context (ticker, primary_focus, notes) is injected
at runtime via format strings.
"""

# ============================================================================
# COMMON PREAMBLE (injected into all prompts)
# ============================================================================

_PREAMBLE = """You are extracting financial data from a {document_type} published by {company_name} ({ticker}).
This company focuses on: {primary_focus}.
Additional context: {notes}

Extract all available data into the following structured format. If a field is not present
in this document, set it to null — do not infer or calculate values not explicitly stated.
For fields that ARE present, be precise — include exact figures, dates, and percentages.

For percentage values, return the number as-is (e.g., 5.6 for "5.6%", not 0.056).
For dollar amounts described as "millions", return the number as stated (e.g., 1205 for "$1,205 millions").
For dollar amounts described as "billions", return in billions (e.g., 20.0 for "$20.0 billion").

Return ONLY valid JSON matching the schema — no markdown, no code blocks, no preamble."""


# ============================================================================
# 1. QUARTERLY EARNINGS RELEASE — all 6 companies
# ============================================================================

QUARTERLY_EARNINGS_SYSTEM = """You are a financial data extraction specialist for mortgage REITs.
You will receive a quarterly earnings press release (HTML or text). Extract all key financial
metrics into the exact JSON schema provided.

{preamble}

Additional extraction guidance for quarterly earnings:
- Distinguish per-share metrics from aggregate metrics.
- Capture GAAP net income AND any non-GAAP measures (distributable earnings, core earnings, EAD).
- Extract total economic return (quarterly, YTD, annual if Q4).
- Extract book value per share — this is the most important single metric.
- Capture leverage ratio, liquidity, and dividend information.
- For companies with multiple segments (CIM, NLY, BMNM), extract segment-level data into additional_data.
- Note any management commentary about outlook or strategy in management_commentary.
- Set extraction_confidence between 0 and 1 based on how much data you found.
- List extracted field names in fields_extracted and unavailable ones in fields_unavailable."""

QUARTERLY_EARNINGS_USER = """Extract all financial metrics from this quarterly earnings release.

Company: {company_name} ({ticker})
Document type: quarterly_earnings
Primary focus: {primary_focus}

DOCUMENT CONTENT:
{content}

JSON Schema:
{schema_json}

Return ONLY the JSON object."""


# ============================================================================
# 2. FINANCIAL SUPPLEMENT — CIM, NLY
# ============================================================================

FINANCIAL_SUPPLEMENT_SYSTEM = """You are a financial data extraction specialist for mortgage REITs.
You will receive a financial supplement document with detailed tables covering portfolio
composition, net interest income, financing, and hedging data.

{preamble}

Additional extraction guidance for financial supplements:
- These contain the most detailed data — extract everything.
- Portfolio composition tables: extract total portfolio size, asset class breakdown.
- Net interest income tables: extract yields, costs, and spreads.
- Financing tables: extract leverage, repo terms, and counterparty data.
- Hedging tables: extract swap notional, hedge ratios.
- If multi-quarter comparison tables exist, extract ONLY the most recent quarter's data.
- Store granular tabular data (e.g., coupon-level breakdown) in additional_data.
- For NLY: separate Agency, Residential Credit, and MSR segment data.
- For CIM: capture non-agency RMBS, residential loans, MSRs, CMBS, origination volume."""

FINANCIAL_SUPPLEMENT_USER = """Extract all financial metrics from this financial supplement.

Company: {company_name} ({ticker})
Document type: financial_supplement
Primary focus: {primary_focus}

DOCUMENT CONTENT:
{content}

JSON Schema:
{schema_json}

Return ONLY the JSON object."""


# ============================================================================
# 3. INVESTOR PRESENTATION — CIM, AGNC, NLY, DX
# ============================================================================

INVESTOR_PRESENTATION_SYSTEM = """You are a financial data extraction specialist for mortgage REITs.
You will receive an investor presentation (text extracted from PDF slides).

{preamble}

Additional extraction guidance for investor presentations:
- Presentations often contain forward-looking commentary — capture in management_commentary.
- Extract any specific metrics from data slides (portfolio size, returns, leverage).
- Market outlook and positioning commentary goes in key_highlights.
- Strategy changes or portfolio rotation commentary goes in portfolio_changes_notes.
- Risk discussion goes in risk_factors_notes.
- These may duplicate data from the earnings release — that's fine, extract it anyway.
- Slide data may be approximate (charts/graphs) — extract best estimates."""

INVESTOR_PRESENTATION_USER = """Extract all financial metrics and insights from this investor presentation.

Company: {company_name} ({ticker})
Document type: investor_presentation
Primary focus: {primary_focus}

DOCUMENT CONTENT:
{content}

JSON Schema:
{schema_json}

Return ONLY the JSON object."""


# ============================================================================
# 4. MONTHLY UPDATE — ARR (adapted from existing, outputs UniversalExtraction)
# ============================================================================

MONTHLY_UPDATE_UNIVERSAL_SYSTEM = """You are a financial data extraction specialist for mortgage REITs.
You will receive a monthly company update document with portfolio data, key metrics,
dividend info, repo composition, swap positions, and hedge summary.

{preamble}

Additional extraction guidance for monthly updates:
- Extract book_value_per_share from stock price or key data section.
- leverage_ratio maps to debt-equity or implied leverage.
- portfolio_size is the total portfolio market value.
- agency_rmbs_holdings is the Agency Portfolio subtotal.
- tba_position is Net TBA Positions market value.
- swap_notional is total swap notional.
- dividends_per_share is the monthly common dividend.
- Store the full granular data (coupon-level positions, repo counterparties,
  swap maturity buckets, hedge types, CPR data) in additional_data with keys:
  portfolio_positions, repo_positions, swap_positions, hedge_summary, cpr_data, footnotes.
- avg_asset_yield and avg_cost_of_funds may not be in monthly updates — set to null if absent."""

MONTHLY_UPDATE_UNIVERSAL_USER = """Extract all financial metrics from this monthly company update.

Company: {company_name} ({ticker})
Document type: monthly_update
Primary focus: {primary_focus}

DOCUMENT CONTENT:
{content}

JSON Schema:
{schema_json}

Return ONLY the JSON object."""


# ============================================================================
# 5. PRESS RELEASE — general, monthly dividends, BV estimates
# ============================================================================

PRESS_RELEASE_SYSTEM = """You are a financial data extraction specialist for mortgage REITs.
You will receive a press release which may be a dividend declaration, book value estimate,
corporate announcement, or other news.

{preamble}

Additional extraction guidance for press releases:
- Monthly dividend declarations: extract dividends_per_share, ex-date, record date, pay date.
- Book value estimates: extract book_value_per_share and the as-of date.
- Any market commentary goes in management_commentary.
- Key numbers mentioned go in key_highlights.
- Many fields will be null for short press releases — that's expected.
- Set extraction_confidence lower for press releases with minimal data."""

PRESS_RELEASE_USER = """Extract all financial metrics from this press release.

Company: {company_name} ({ticker})
Document type: press_release
Primary focus: {primary_focus}

DOCUMENT CONTENT:
{content}

JSON Schema:
{schema_json}

Return ONLY the JSON object."""


# ============================================================================
# 6. SEC FILING (10-Q / 10-K) — any company
# ============================================================================

SEC_FILING_SYSTEM = """You are a financial data extraction specialist for mortgage REITs.
You will receive text extracted from a 10-Q or 10-K SEC filing. This is a long document —
focus on the key financial data sections.

{preamble}

Additional extraction guidance for SEC filings:
- Extract from the Financial Statements: balance sheet (total assets, book value),
  income statement (net interest income, GAAP net income, EPS).
- Extract from the derivatives/hedging note: swap notional, hedge composition.
- Extract from the MBS portfolio tables: portfolio size, agency vs non-agency split.
- Extract from MD&A: management commentary, strategy discussion, risk factors.
- These filings contain the most authoritative data — set extraction_confidence high
  for fields directly from financial statements.
- Store detailed schedule of investments data in additional_data if present."""

SEC_FILING_USER = """Extract all financial metrics from this SEC filing.

Company: {company_name} ({ticker})
Document type: sec_filing
Primary focus: {primary_focus}

DOCUMENT CONTENT (key sections):
{content}

JSON Schema:
{schema_json}

Return ONLY the JSON object."""


# ============================================================================
# Prompt selector
# ============================================================================

PROMPT_MAP = {
    "quarterly_earnings": (QUARTERLY_EARNINGS_SYSTEM, QUARTERLY_EARNINGS_USER),
    "earnings_release": (QUARTERLY_EARNINGS_SYSTEM, QUARTERLY_EARNINGS_USER),
    "financial_supplement": (FINANCIAL_SUPPLEMENT_SYSTEM, FINANCIAL_SUPPLEMENT_USER),
    "investor_presentation": (INVESTOR_PRESENTATION_SYSTEM, INVESTOR_PRESENTATION_USER),
    "monthly_update": (MONTHLY_UPDATE_UNIVERSAL_SYSTEM, MONTHLY_UPDATE_UNIVERSAL_USER),
    "press_release": (PRESS_RELEASE_SYSTEM, PRESS_RELEASE_USER),
    "monthly_dividend": (PRESS_RELEASE_SYSTEM, PRESS_RELEASE_USER),
    "monthly_book_value": (PRESS_RELEASE_SYSTEM, PRESS_RELEASE_USER),
    "sec_filing": (SEC_FILING_SYSTEM, SEC_FILING_USER),
    "quarterly_10q": (SEC_FILING_SYSTEM, SEC_FILING_USER),
    "annual_10k": (SEC_FILING_SYSTEM, SEC_FILING_USER),
}


def get_extraction_prompts(document_type: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for a document type."""
    if document_type not in PROMPT_MAP:
        raise ValueError(f"No extraction prompts for document type: {document_type}")
    return PROMPT_MAP[document_type]
