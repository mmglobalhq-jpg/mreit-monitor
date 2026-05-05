"""
Pydantic models for summary reports and investor material analysis.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SummaryReportSection(BaseModel):
    """A single section of a summary report."""
    title: str
    content: str = Field(description="Markdown content for this section")
    data_available: bool = Field(True, description="False if insufficient data to populate this section")
    source_documents: list[str] = Field(default_factory=list, description="Filing IDs or labels that sourced this section")


class SummaryReport(BaseModel):
    """
    Consolidated summary report produced by the summary agent.
    report_content holds the full formatted markdown desk note.
    Section fields are retained for backward compatibility.
    """
    # Metadata
    ticker: str
    company_name: str
    report_type: str = Field(description="'monthly', 'quarterly', or 'annual'")
    period_label: str = Field(description="e.g., 'March 2026', 'Q4 2025', 'FY 2025'")
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    # Full formatted desk note (primary output)
    report_content: str = Field(
        default="",
        description="Full formatted markdown desk note following the required output structure",
    )

    # Legacy section fields — optional, preserved for backward compatibility
    overall_summary: Optional[SummaryReportSection] = Field(
        default=None,
        description="Executive summary: key takeaways, headline metrics, notable changes"
    )
    securities_detail: Optional[SummaryReportSection] = Field(
        default=None,
        description="Portfolio composition, duration, coupon allocation, MBS positioning"
    )
    filing_highlights: Optional[SummaryReportSection] = Field(
        default=None,
        description="Highlights from 10-Q/10-K, earnings releases processed in this period"
    )
    performance_activity: Optional[SummaryReportSection] = Field(
        default=None,
        description="Leverage, liquidity, repo, hedging, dividend coverage, book value"
    )
    supplemental_materials: Optional[SummaryReportSection] = Field(
        default=None,
        description="Investor presentations, conference call notes, ad-hoc materials"
    )
    data_gaps: Optional[SummaryReportSection] = Field(
        default=None,
        description="What data was unavailable, expected but missing filings, quality notes"
    )


class InvestorMaterialAnalysis(BaseModel):
    """Analysis of an ad-hoc investor material (presentation, conference call, etc.)."""
    securities_insights: str = Field(description="Key insights about MBS/agency securities positioning")
    portfolio_implications: str = Field(description="What the material implies for portfolio strategy")
    key_data_points: list[str] = Field(description="Specific data points extracted from the material")
    source_url: Optional[str] = None
