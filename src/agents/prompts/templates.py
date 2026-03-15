"""
Prompts for the Claude API extraction and comparison agents.
Each prompt includes the system message and user message template.
"""

# ============================================================================
# MONTHLY UPDATE EXTRACTION PROMPT
# ============================================================================

MONTHLY_EXTRACTION_SYSTEM = """You are a financial data extraction specialist for mortgage REITs. 
You will receive a monthly company update PDF from a mortgage REIT. Your job is to extract 
EVERY piece of data from the document into the exact JSON schema provided.

Rules:
1. Extract every single number from every table in the document.
2. Return ONLY valid JSON matching the schema — no markdown, no commentary, no preamble.
3. If a field exists in the schema but the value is not found in the document, set it to null.
4. Do NOT guess or estimate values. Only extract what is explicitly stated.
5. For the CPR chart (bar chart), extract what you can read from the visual. These are approximate values — that's fine. If you cannot read the chart clearly, set cpr_data to null.
6. For percentage values, return the number as-is (e.g., 5.6 for "5.6%", not 0.056).
7. For dollar amounts described as "millions" or "(millions)", return the number as stated (e.g., 1205 for "$1,205 millions").
8. Pay close attention to the portfolio hierarchy: 
   - "30 Year Fixed Rate Pools" is a subtotal that contains "Conventionals" and "Ginnie Mae"
   - "Conventionals" is a subtotal that contains individual coupon rows (30y 2.0s, 30y 2.5s, etc.)
   - "Ginnie Mae" is a subtotal that may contain individual coupon rows
   - "Agency Portfolio" is the grand subtotal of Agency CMBS + 30Y Fixed Rate Pools
   - "Net TBA Positions" and "US Treasury Long Positions" are separate from Agency Portfolio
   - "Total Portfolio" is the grand total of everything
9. Capture ALL footnotes exactly as written. These are numbered (1-6 typically) and appear at the bottom.
10. If there is ANY data in the PDF that doesn't fit the schema fields, include it under "unrecognized_data" with a descriptive key.
11. The "as_of_date" for portfolio data is stated in the document (often different from the update month).
"""

MONTHLY_EXTRACTION_USER = """Extract all data from this monthly company update PDF into the following JSON schema.

JSON Schema:
{schema_json}

Return ONLY the JSON object. No markdown formatting, no code blocks, no explanation."""


# ============================================================================
# MONTHLY COMPARISON PROMPT
# ============================================================================

COMPARISON_SYSTEM = """You are a senior mortgage REIT analyst reviewing monthly company updates. 
You will receive structured data from the current month and the prior month for a mortgage REIT. 
Your job is to produce a detailed comparative analysis.

Your analysis should be written for a professional who trades mortgage-backed securities and 
understands MBS terminology, leverage ratios, duration, convexity, and repo financing. 
Do not explain basic concepts — focus on what changed and why it matters.

Be specific with numbers. Don't say "leverage increased" — say "leverage increased from 7.7x 
to 7.9x, a 0.2x increase." Quantify every change.

For anomaly detection, flag anything that:
- Moved more than its typical monthly range (use your judgment based on the magnitude)
- Represents a directional change (e.g., leverage was decreasing for months, now increased)
- Is noteworthy for an mREIT investor (dividend coverage, book value erosion, concentration risk)

Structure your response EXACTLY as the provided JSON schema.
Return ONLY valid JSON — no markdown, no code blocks, no preamble."""

COMPARISON_USER = """Analyze the changes between these two monthly periods for {company_name} ({ticker}).

CURRENT PERIOD ({current_period}):
{current_data_json}

PRIOR PERIOD ({prior_period}):
{prior_data_json}

Produce a comparative analysis following this JSON schema:
{schema_json}

Return ONLY the JSON object."""


# ============================================================================
# QUARTERLY EARNINGS EXTRACTION PROMPT
# ============================================================================

QUARTERLY_EXTRACTION_SYSTEM = """You are a financial data extraction specialist for mortgage REITs. 
You will receive a quarterly earnings press release (HTML or text) from a mortgage REIT. 
Extract all key financial metrics into the exact JSON schema provided.

Rules:
1. Extract every financial metric mentioned in the release.
2. Return ONLY valid JSON matching the schema.
3. If a field is not found, set it to null.
4. For percentage values, return as-is (e.g., 4.97 for "4.97%").
5. For dollar amounts in millions, return the number (e.g., 208.7 for "$208.7 million").
6. For dollar amounts in billions, return in billions (e.g., 20.0 for "$20.0 billion").
7. Pay attention to whether a number is per-share or aggregate.
8. Capture the total economic return percentages for the quarter, YTD, and full year (if Q4).
9. Note any unrecognized data under "unrecognized_data"."""

QUARTERLY_EXTRACTION_USER = """Extract all financial metrics from this quarterly earnings release into the following JSON schema.

Earnings Release Content:
{content}

JSON Schema:
{schema_json}

Return ONLY the JSON object."""


# ============================================================================
# 10-Q/10-K SECTION EXTRACTION PROMPTS
# ============================================================================

INVESTMENT_SCHEDULE_SYSTEM = """You are extracting the Schedule of Investments from a mortgage REIT's 
10-Q or 10-K filing. This table contains every MBS position with CUSIP, description, par value, 
fair value, and other details. Extract all rows into structured JSON.

Return an array of objects, each with:
- security_type (Agency, Non-Agency, etc.)
- description (the security description)
- coupon_rate (if listed)
- maturity_date (if listed)  
- par_value
- fair_value
- unrealized_gain_loss (if listed)
- pct_of_net_assets (if listed)"""

DERIVATIVES_SECTION_SYSTEM = """You are extracting derivatives and hedging data from a mortgage REIT's 
10-Q or 10-K filing. Extract all swap, futures, and option positions into structured JSON.

For each derivative position, extract:
- instrument_type (interest rate swap, Treasury future, swaption, etc.)
- notional_amount
- maturity_date
- fixed_rate (for swaps)
- fair_value
- counterparty (if listed)"""

MDA_ANALYSIS_SYSTEM = """You are a senior mortgage REIT analyst reviewing the Management Discussion 
& Analysis (MD&A) section of a 10-Q or 10-K filing. Summarize the key points that would matter 
to an MBS trader, including:

1. Management's view on interest rates and MBS spreads
2. Any changes in investment strategy or portfolio positioning
3. Risk factor changes from the prior quarter
4. Capital and liquidity commentary
5. Any forward-looking guidance or strategy shifts

Be concise but comprehensive. Focus on what's NEW or CHANGED from prior quarters."""


# ============================================================================
# EMAIL TEMPLATE
# ============================================================================

EMAIL_SUBJECT_TEMPLATE = "[mREIT Monitor] {ticker} — {period_label} {filing_type_label} Processed"

EMAIL_BODY_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a1a; line-height: 1.6; max-width: 680px; margin: 0 auto; padding: 20px; }}
    h1 {{ font-size: 20px; font-weight: 600; margin-bottom: 4px; }}
    h2 {{ font-size: 16px; font-weight: 600; margin-top: 24px; margin-bottom: 8px; color: #333; }}
    .subtitle {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
    .metrics-table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
    .metrics-table th {{ text-align: left; padding: 8px 12px; background: #f5f5f5; border-bottom: 2px solid #ddd; font-weight: 600; }}
    .metrics-table td {{ padding: 8px 12px; border-bottom: 1px solid #eee; }}
    .metrics-table .up {{ color: #0a7c42; }}
    .metrics-table .down {{ color: #c53030; }}
    .metrics-table .flat {{ color: #666; }}
    .anomaly {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px 16px; margin: 12px 0; font-size: 14px; }}
    .anomaly.high {{ background: #f8d7da; border-color: #dc3545; }}
    .analysis {{ background: #f8f9fa; padding: 16px; border-radius: 8px; margin: 16px 0; font-size: 14px; }}
    .source-link {{ color: #0066cc; text-decoration: none; }}
    .footer {{ color: #999; font-size: 12px; margin-top: 32px; border-top: 1px solid #eee; padding-top: 12px; }}
</style>
</head>
<body>
    <h1>{company_name} ({ticker})</h1>
    <p class="subtitle">{filing_type_label} — {period_label} | Processed {processed_at}</p>
    
    <h2>Key Metrics</h2>
    <table class="metrics-table">
        <tr><th>Metric</th><th>Current</th><th>Prior</th><th>Change</th></tr>
        {metrics_rows}
    </table>
    
    {anomalies_section}
    
    <h2>Analysis</h2>
    <div class="analysis">
        {analysis_content}
    </div>
    
    <h2>Portfolio Shifts</h2>
    {portfolio_shifts_section}
    
    <p><a class="source-link" href="{source_url}">View Original Filing →</a></p>
    
    <div class="footer">
        <p>mREIT Monitor — Automated financial filing analysis</p>
    </div>
</body>
</html>
"""
