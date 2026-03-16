"""
Pydantic models for all structured data extracted from mREIT filings.
These schemas are used both for Claude API extraction validation 
and for Supabase insert operations.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class FilingType(str, Enum):
    MONTHLY_UPDATE = "monthly_update"
    EARNINGS_RELEASE = "earnings_release"
    QUARTERLY_10Q = "quarterly_10q"
    ANNUAL_10K = "annual_10k"
    INVESTOR_PRESENTATION = "investor_presentation"
    ANNUAL_REPORT = "annual_report"
    PROXY_STATEMENT = "proxy_statement"
    FINANCIAL_SUPPLEMENT = "financial_supplement"
    MONTHLY_DIVIDEND = "monthly_dividend"
    MONTHLY_BOOK_VALUE = "monthly_book_value"
    PRESS_RELEASE = "press_release"
    OTHER = "other"


@dataclass
class DetectedFiling:
    """A filing detected by scraping or EDGAR but not yet downloaded."""
    source_url: str
    filing_type: FilingType
    filing_date: date
    period_label: str
    source_page: str


class FilingStatus(str, Enum):
    DETECTED = "detected"
    DOWNLOADED = "downloaded"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    COMPARING = "comparing"
    COMPLETED = "completed"
    EXTRACTION_FAILED = "extraction_failed"
    VALIDATION_FAILED = "validation_failed"
    COMPARISON_FAILED = "comparison_failed"


# ============================================================================
# Monthly Update Extraction Schemas
# These match what Claude should return when extracting monthly PDFs
# ============================================================================

class PortfolioPosition(BaseModel):
    """A single row from the portfolio allocation table."""
    security_type: str = Field(description="e.g., 'Agency CMBS', 'Conventionals', 'Ginnie Mae'")
    coupon: Optional[str] = Field(None, description="e.g., '30y 2.0s', '30y 5.5s', 'FN 30y 4.5 TBAs'. Null for aggregate/subtotal rows.")
    is_subtotal: bool = Field(False, description="True for aggregate rows like '30 Year Fixed Rate Pools', 'Conventionals', 'Agency Portfolio', 'Total Portfolio'")
    parent_category: Optional[str] = Field(None, description="Parent grouping. e.g., 'Conventionals' for individual coupon rows, '30 Year Fixed Rate Pools' for Conventionals/Ginnie Mae subtotals")
    pct_portfolio: Optional[float] = Field(None, description="Percentage of total portfolio")
    market_value_millions: Optional[float] = Field(None, description="Market value in millions USD")
    effective_duration: Optional[float] = Field(None, description="Effective duration")


class RepoPosition(BaseModel):
    """A single row from the repo composition table."""
    counterparty: str = Field(description="e.g., 'BUCKLER Securities LLC', 'All Other Counterparties', 'Total'")
    is_affiliate: bool = Field(False, description="True for BUCKLER (ARMOUR affiliate)")
    is_total: bool = Field(False, description="True for the Total row")
    principal_borrowed_millions: Optional[float] = Field(None, description="Principal borrowed in millions")
    pct_of_repo: Optional[float] = Field(None, description="Percentage of total repo positions")
    wtd_avg_original_term_days: Optional[float] = Field(None, description="Weighted average original term in days")
    wtd_avg_remaining_term_days: Optional[float] = Field(None, description="Weighted average remaining term in days")
    longest_maturity_days: Optional[int] = Field(None, description="Longest maturity in days")


class SwapPosition(BaseModel):
    """A single row from the interest rate swaps table."""
    maturity_bucket: str = Field(description="e.g., '0-12', '13-24', '25-36', '>120', 'Total'")
    is_total: bool = Field(False, description="True for the Total row")
    notional_millions: Optional[float] = Field(None, description="Notional amount in millions")
    wtd_avg_remaining_term_months: Optional[float] = Field(None, description="Weighted average remaining term in months")
    wtd_avg_rate: Optional[float] = Field(None, description="Weighted average rate as percentage (e.g., 2.47 for 2.47%)")


class HedgeSummary(BaseModel):
    """Hedge type summary (swaps + treasury futures)."""
    hedge_type: str = Field(description="e.g., 'Interest Rate Swaps', 'Treasury Futures'")
    notional_millions: Optional[float] = Field(None, description="Notional in millions")
    additional_info: Optional[str] = Field(None, description="e.g., 'weighted average duration of 12.3 years' for Treasury Futures")


class DividendInfo(BaseModel):
    """Dividend information from the monthly update."""
    month_label: Optional[str] = Field(None, description="e.g., 'March 2026'")
    monthly_dividend: Optional[float] = Field(None, description="Monthly common dividend per share")
    ex_dividend_date: Optional[str] = Field(None, description="Ex-dividend date as string (e.g., '3/16/2026')")
    record_date: Optional[str] = Field(None, description="Record date as string")
    pay_date: Optional[str] = Field(None, description="Pay date as string")
    dividend_yield: Optional[float] = Field(None, description="Current dividend yield as percentage")


class KeyMetrics(BaseModel):
    """Key data metrics from the monthly update header."""
    as_of_date: str = Field(description="The as-of date for the data, e.g., '02/28/2026'")
    stock_price: Optional[float] = Field(None, description="Common stock price")
    debt_equity: Optional[float] = Field(None, description="Debt-to-equity ratio")
    implied_leverage: Optional[float] = Field(None, description="Implied leverage ratio")
    liquidity_millions: Optional[float] = Field(None, description="Total liquidity in millions")
    liquidity_pct_capital: Optional[float] = Field(None, description="Liquidity as percentage of total capital")
    market_cap_millions: Optional[float] = Field(None, description="Market cap in millions (may not be in every update)")


class CPRDataPoint(BaseModel):
    """A single CPR reading from the CPR bar chart."""
    month: str = Field(description="Month label, e.g., 'J 2024', 'F 2025'")
    cpr_value: Optional[float] = Field(None, description="CPR value (estimated from chart)")


class FootnoteEntry(BaseModel):
    """A footnote from the monthly update."""
    number: int = Field(description="Footnote number (1-6 typically)")
    text: str = Field(description="Full footnote text")


class MonthlyUpdateExtraction(BaseModel):
    """
    Complete extraction schema for an ARMOUR monthly company update PDF.
    This is the JSON structure Claude should return when extracting a monthly PDF.
    """
    # Metadata
    company_name: str = Field(description="Company name from the header")
    update_month: str = Field(description="Month and year of the update, e.g., 'March 2026'")
    data_as_of_date: str = Field(description="The as-of date for portfolio data, e.g., '02/28/2026'")
    cpr_as_of_date: Optional[str] = Field(None, description="The as-of date for CPR data if different, e.g., '03/05/26'")
    
    # Key metrics
    key_metrics: KeyMetrics
    dividend_info: DividendInfo
    
    # Portfolio
    portfolio_positions: list[PortfolioPosition] = Field(description="All rows from the portfolio table, including subtotals and individual coupons")
    
    # Repo
    repo_positions: list[RepoPosition] = Field(description="All rows from the repo composition table")
    
    # Swaps
    swap_positions: list[SwapPosition] = Field(description="All rows from the interest rate swaps table")
    
    # Hedges
    hedge_summary: list[HedgeSummary] = Field(description="Hedge type summary rows")
    
    # CPR (from the bar chart — best effort)
    cpr_data: Optional[list[CPRDataPoint]] = Field(None, description="CPR data points from the bar chart. Extract what you can read from the chart.")
    
    # Footnotes
    footnotes: list[FootnoteEntry] = Field(description="All numbered footnotes from the document")
    
    # Catch-all for new/unrecognized data
    unrecognized_data: Optional[dict] = Field(None, description="Any data in the PDF not captured by the fields above. Include the section name and raw values.")


# ============================================================================
# Quarterly Earnings Release Schemas
# ============================================================================

class QuarterlyEarningsExtraction(BaseModel):
    """
    Extraction schema for quarterly earnings press releases.
    """
    company_name: str
    quarter_label: str = Field(description="e.g., 'Q4 2025'")
    period_end_date: str = Field(description="e.g., '12/31/2025'")
    
    # Income
    gaap_net_income_millions: Optional[float] = None
    gaap_eps: Optional[float] = None
    net_interest_income_millions: Optional[float] = None
    distributable_earnings_millions: Optional[float] = None
    distributable_eps: Optional[float] = None
    
    # Yield & Spread
    avg_interest_income_rate: Optional[float] = None
    avg_interest_expense_rate: Optional[float] = None
    economic_interest_income_rate: Optional[float] = None
    economic_interest_expense_rate: Optional[float] = None
    economic_net_interest_spread: Optional[float] = None
    
    # Balance Sheet
    book_value_per_share: Optional[float] = None
    total_portfolio_billions: Optional[float] = None
    agency_mbs_pct: Optional[float] = None
    
    # Returns
    quarterly_total_economic_return: Optional[float] = None
    ytd_total_economic_return: Optional[float] = None
    annual_total_economic_return: Optional[float] = None
    
    # Capital & Leverage
    liquidity_millions: Optional[float] = None
    repo_agreements_net_millions: Optional[float] = None
    affiliate_repo_pct: Optional[float] = None
    debt_equity_ratio: Optional[float] = None
    implied_leverage: Optional[float] = None
    
    # Equity Issuance
    atm_capital_raised_millions: Optional[float] = None
    atm_shares_issued: Optional[int] = None
    
    # Dividends
    quarterly_dividend_per_share: Optional[float] = None
    
    # Tax Treatment
    ordinary_income_pct: Optional[float] = None
    return_of_capital_pct: Optional[float] = None
    
    # Catch-all
    unrecognized_data: Optional[dict] = None


# ============================================================================
# Comparison Agent Output Schemas
# ============================================================================

class MetricChange(BaseModel):
    """A single metric change between periods."""
    metric_name: str
    current_value: Optional[float] = None
    prior_value: Optional[float] = None
    change_absolute: Optional[float] = None
    change_pct: Optional[float] = None
    direction: str = Field(description="'up', 'down', or 'flat'")
    significance: str = Field(description="'normal', 'notable', 'significant', 'anomalous'")
    commentary: Optional[str] = Field(None, description="Brief context for the change")


class PortfolioShift(BaseModel):
    """A notable shift in portfolio allocation."""
    coupon: str
    prior_pct: Optional[float] = None
    current_pct: Optional[float] = None
    change_pct: Optional[float] = None
    commentary: Optional[str] = None


class AnomalyFlag(BaseModel):
    """An anomaly detected by the comparison agent."""
    metric: str
    description: str
    severity: str = Field(description="'low', 'medium', 'high'")
    current_value: Optional[float] = None
    expected_range: Optional[str] = None


class ComparisonAnalysis(BaseModel):
    """
    Output schema for the comparison agent.
    """
    period_label: str = Field(description="e.g., 'March 2026 vs February 2026'")
    analysis_type: str = Field(description="'monthly_comparison' or 'quarterly_comparison'")
    
    # Executive summary
    summary: str = Field(description="2-3 sentence executive summary of the key changes")
    
    # Structured changes
    key_metric_changes: list[MetricChange] = Field(description="Changes in headline metrics")
    portfolio_shifts: list[PortfolioShift] = Field(description="Notable shifts in portfolio allocation by coupon")
    
    # Detailed analysis sections (markdown)
    portfolio_analysis: str = Field(description="Paragraph analyzing portfolio composition changes")
    leverage_liquidity_analysis: str = Field(description="Paragraph analyzing leverage and liquidity changes")
    hedging_analysis: str = Field(description="Paragraph analyzing hedge position changes")
    repo_analysis: str = Field(description="Paragraph analyzing repo book changes")
    dividend_analysis: str = Field(description="Paragraph analyzing dividend sustainability")
    
    # Anomalies
    anomalies: list[AnomalyFlag] = Field(default_factory=list, description="Any flagged anomalies")
    
    # New/removed items
    new_items: Optional[list[str]] = Field(None, description="Items in current period not in prior")
    removed_items: Optional[list[str]] = Field(None, description="Items in prior period not in current")
    footnote_changes: Optional[list[str]] = Field(None, description="Any changes in footnote wording")
    
    # Full narrative (markdown)
    full_analysis: str = Field(description="Complete comparative analysis narrative in markdown")
