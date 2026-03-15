"""
Universal extraction schema — normalized output for any company / document type.

All non-identifier fields are Optional with default None so that extraction
works regardless of which fields the source document actually contains.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class UniversalExtraction(BaseModel):
    """Normalized extraction output for any company/document type."""

    # ---- Identifiers ----
    company_ticker: str
    document_type: str  # monthly_update, quarterly_earnings, financial_supplement, etc.
    document_date: date
    period_end: date
    fiscal_quarter: Optional[int] = None
    fiscal_year: int
    source_url: str

    # ---- Universal Fields (present for all/most companies) ----
    book_value_per_share: Optional[float] = None
    earnings_per_share: Optional[float] = None
    dividends_per_share: Optional[float] = None
    economic_return_pct: Optional[float] = None
    net_interest_income: Optional[float] = Field(None, description="Net interest income in millions")
    net_interest_spread: Optional[float] = Field(None, description="Net interest spread in bps or pct")
    leverage_ratio: Optional[float] = None
    total_assets: Optional[float] = Field(None, description="Total assets in millions")
    portfolio_size: Optional[float] = Field(None, description="Investment portfolio in millions")

    # ---- Agency MBS Fields (ARR, AGNC, DX, portions of CIM/NLY) ----
    agency_rmbs_holdings: Optional[float] = Field(None, description="Agency RMBS in millions")
    weighted_avg_coupon: Optional[float] = None
    weighted_avg_life: Optional[float] = Field(None, description="Weighted average life in years")
    cpr_experience: Optional[float] = None
    tba_position: Optional[float] = Field(None, description="TBA position in millions")
    avg_asset_yield: Optional[float] = None
    avg_cost_of_funds: Optional[float] = None

    # ---- Hedge Fields ----
    hedge_ratio: Optional[float] = None
    swap_notional: Optional[float] = Field(None, description="Swap notional in millions")
    hedge_composition_notes: Optional[str] = None

    # ---- Non-Agency / Credit Fields (CIM, NLY) ----
    non_agency_rmbs_holdings: Optional[float] = Field(None, description="Non-Agency RMBS in millions")
    residential_loan_portfolio: Optional[float] = Field(None, description="Residential loans in millions")
    msr_portfolio: Optional[float] = Field(None, description="MSR portfolio in millions")
    cmbs_holdings: Optional[float] = Field(None, description="CMBS holdings in millions")
    origination_volume: Optional[float] = Field(None, description="Origination volume in millions")

    # ---- Flexible Fields ----
    management_commentary: Optional[str] = None
    key_highlights: list[str] = Field(default_factory=list)
    portfolio_changes_notes: Optional[str] = None
    risk_factors_notes: Optional[str] = None

    # ---- Catch-all for company-specific data ----
    additional_data: dict = Field(default_factory=dict)

    # ---- Metadata ----
    extraction_confidence: float = 0.0
    fields_extracted: list[str] = Field(default_factory=list)
    fields_unavailable: list[str] = Field(default_factory=list)
