"""
Tests for Pydantic schema validation in src/models/schemas.py.
"""

import pytest
from pydantic import ValidationError

from src.models.schemas import (
    AnomalyFlag,
    ComparisonAnalysis,
    DividendInfo,
    FootnoteEntry,
    HedgeSummary,
    KeyMetrics,
    MetricChange,
    MonthlyUpdateExtraction,
    PortfolioPosition,
    PortfolioShift,
    QuarterlyEarningsExtraction,
    RepoPosition,
    SwapPosition,
)


# ============================================================================
# MonthlyUpdateExtraction validation
# ============================================================================


class TestMonthlyUpdateExtraction:
    @pytest.fixture
    def good_payload(self) -> dict:
        """A known-good JSON payload matching MonthlyUpdateExtraction."""
        return {
            "company_name": "ARMOUR Residential REIT, Inc.",
            "update_month": "March 2026",
            "data_as_of_date": "02/28/2026",
            "cpr_as_of_date": "03/05/2026",
            "key_metrics": {
                "as_of_date": "02/28/2026",
                "stock_price": 19.50,
                "debt_equity": 6.8,
                "implied_leverage": 7.9,
                "liquidity_millions": 525.3,
                "liquidity_pct_capital": 7.5,
                "market_cap_millions": 1230.0,
            },
            "dividend_info": {
                "month_label": "March 2026",
                "monthly_dividend": 0.24,
                "ex_dividend_date": "3/16/2026",
                "record_date": "3/17/2026",
                "pay_date": "3/27/2026",
                "dividend_yield": 14.8,
            },
            "portfolio_positions": [
                {
                    "security_type": "Agency CMBS",
                    "coupon": None,
                    "is_subtotal": True,
                    "parent_category": None,
                    "pct_portfolio": 5.2,
                    "market_value_millions": 600.0,
                    "effective_duration": 3.1,
                },
                {
                    "security_type": "Conventionals",
                    "coupon": "30y 5.5s",
                    "is_subtotal": False,
                    "parent_category": "30 Year Fixed Rate Pools",
                    "pct_portfolio": 22.3,
                    "market_value_millions": 2580.0,
                    "effective_duration": 4.2,
                },
            ],
            "repo_positions": [
                {
                    "counterparty": "BUCKLER Securities LLC",
                    "is_affiliate": True,
                    "is_total": False,
                    "principal_borrowed_millions": 2100.0,
                    "pct_of_repo": 22.5,
                    "wtd_avg_original_term_days": 60.0,
                    "wtd_avg_remaining_term_days": 30.0,
                    "longest_maturity_days": 90,
                },
                {
                    "counterparty": "Total",
                    "is_affiliate": False,
                    "is_total": True,
                    "principal_borrowed_millions": 9300.0,
                    "pct_of_repo": 100.0,
                    "wtd_avg_original_term_days": 45.0,
                    "wtd_avg_remaining_term_days": 22.0,
                    "longest_maturity_days": 120,
                },
            ],
            "swap_positions": [
                {
                    "maturity_bucket": "0-12",
                    "is_total": False,
                    "notional_millions": 500.0,
                    "wtd_avg_remaining_term_months": 6.5,
                    "wtd_avg_rate": 2.47,
                },
                {
                    "maturity_bucket": "Total",
                    "is_total": True,
                    "notional_millions": 5000.0,
                    "wtd_avg_remaining_term_months": 48.0,
                    "wtd_avg_rate": 2.85,
                },
            ],
            "hedge_summary": [
                {
                    "hedge_type": "Interest Rate Swaps",
                    "notional_millions": 5000.0,
                    "additional_info": None,
                },
                {
                    "hedge_type": "Treasury Futures",
                    "notional_millions": 1200.0,
                    "additional_info": "weighted average duration of 12.3 years",
                },
            ],
            "cpr_data": [
                {"month": "J 2024", "cpr_value": 5.2},
                {"month": "F 2024", "cpr_value": 4.8},
            ],
            "footnotes": [
                {"number": 1, "text": "Portfolio data as of 02/28/2026."},
                {"number": 2, "text": "Duration estimates are model-based."},
            ],
            "unrecognized_data": None,
        }

    def test_valid_payload(self, good_payload):
        extraction = MonthlyUpdateExtraction(**good_payload)
        assert extraction.company_name == "ARMOUR Residential REIT, Inc."
        assert extraction.update_month == "March 2026"
        assert extraction.key_metrics.stock_price == 19.50
        assert len(extraction.portfolio_positions) == 2
        assert len(extraction.repo_positions) == 2
        assert len(extraction.swap_positions) == 2
        assert len(extraction.hedge_summary) == 2
        assert len(extraction.cpr_data) == 2
        assert len(extraction.footnotes) == 2

    def test_optional_fields_can_be_none(self, good_payload):
        good_payload["cpr_data"] = None
        good_payload["unrecognized_data"] = None
        good_payload["cpr_as_of_date"] = None
        extraction = MonthlyUpdateExtraction(**good_payload)
        assert extraction.cpr_data is None
        assert extraction.unrecognized_data is None
        assert extraction.cpr_as_of_date is None

    def test_missing_required_company_name(self, good_payload):
        del good_payload["company_name"]
        with pytest.raises(ValidationError):
            MonthlyUpdateExtraction(**good_payload)

    def test_missing_required_key_metrics(self, good_payload):
        del good_payload["key_metrics"]
        with pytest.raises(ValidationError):
            MonthlyUpdateExtraction(**good_payload)

    def test_missing_required_portfolio_positions(self, good_payload):
        del good_payload["portfolio_positions"]
        with pytest.raises(ValidationError):
            MonthlyUpdateExtraction(**good_payload)

    def test_invalid_key_metrics_type(self, good_payload):
        good_payload["key_metrics"] = "not a dict"
        with pytest.raises(ValidationError):
            MonthlyUpdateExtraction(**good_payload)

    def test_empty_lists_are_valid(self, good_payload):
        good_payload["portfolio_positions"] = []
        good_payload["repo_positions"] = []
        good_payload["swap_positions"] = []
        good_payload["hedge_summary"] = []
        good_payload["footnotes"] = []
        extraction = MonthlyUpdateExtraction(**good_payload)
        assert extraction.portfolio_positions == []

    def test_portfolio_position_validation(self):
        # Valid
        pos = PortfolioPosition(security_type="Agency CMBS")
        assert pos.security_type == "Agency CMBS"
        assert pos.coupon is None
        assert pos.is_subtotal is False

    def test_portfolio_position_missing_required(self):
        with pytest.raises(ValidationError):
            PortfolioPosition()  # security_type is required

    def test_repo_position_defaults(self):
        repo = RepoPosition(counterparty="Test")
        assert repo.is_affiliate is False
        assert repo.is_total is False
        assert repo.principal_borrowed_millions is None

    def test_swap_position_defaults(self):
        swap = SwapPosition(maturity_bucket="0-12")
        assert swap.is_total is False
        assert swap.notional_millions is None

    def test_model_dump_roundtrip(self, good_payload):
        extraction = MonthlyUpdateExtraction(**good_payload)
        dumped = extraction.model_dump()
        # Should be able to re-create from dumped data
        extraction2 = MonthlyUpdateExtraction(**dumped)
        assert extraction2.company_name == extraction.company_name
        assert extraction2.key_metrics.stock_price == extraction.key_metrics.stock_price


# ============================================================================
# QuarterlyEarningsExtraction validation
# ============================================================================


class TestQuarterlyEarningsExtraction:
    @pytest.fixture
    def good_quarterly_payload(self) -> dict:
        return {
            "company_name": "ARMOUR Residential REIT, Inc.",
            "quarter_label": "Q4 2025",
            "period_end_date": "12/31/2025",
            "gaap_net_income_millions": 45.2,
            "gaap_eps": 0.68,
            "net_interest_income_millions": 32.1,
            "distributable_earnings_millions": 28.5,
            "distributable_eps": 0.43,
            "book_value_per_share": 20.15,
            "total_portfolio_billions": 12.3,
            "debt_equity_ratio": 6.8,
            "implied_leverage": 7.9,
            "quarterly_total_economic_return": 3.2,
        }

    def test_valid_quarterly_payload(self, good_quarterly_payload):
        extraction = QuarterlyEarningsExtraction(**good_quarterly_payload)
        assert extraction.quarter_label == "Q4 2025"
        assert extraction.gaap_net_income_millions == 45.2

    def test_all_optional_fields_none(self):
        extraction = QuarterlyEarningsExtraction(
            company_name="ARMOUR",
            quarter_label="Q1 2025",
            period_end_date="03/31/2025",
        )
        assert extraction.gaap_net_income_millions is None
        assert extraction.book_value_per_share is None
        assert extraction.unrecognized_data is None

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            QuarterlyEarningsExtraction(company_name="ARMOUR")  # missing quarter_label, period_end_date

    def test_invalid_types(self, good_quarterly_payload):
        good_quarterly_payload["gaap_net_income_millions"] = "not a number"
        with pytest.raises(ValidationError):
            QuarterlyEarningsExtraction(**good_quarterly_payload)


# ============================================================================
# ComparisonAnalysis validation
# ============================================================================


class TestComparisonAnalysis:
    @pytest.fixture
    def good_comparison_payload(self) -> dict:
        return {
            "period_label": "March 2026 vs February 2026",
            "analysis_type": "monthly_comparison",
            "summary": "Portfolio shifted toward higher coupons with modest leverage increase.",
            "key_metric_changes": [
                {
                    "metric_name": "Stock Price",
                    "current_value": 19.50,
                    "prior_value": 18.50,
                    "change_absolute": 1.0,
                    "change_pct": 5.4,
                    "direction": "up",
                    "significance": "normal",
                    "commentary": "Stock price increased by $1.00",
                },
            ],
            "portfolio_shifts": [
                {
                    "coupon": "30y 5.5s",
                    "prior_pct": 20.0,
                    "current_pct": 22.3,
                    "change_pct": 2.3,
                    "commentary": "Increased allocation to 5.5 coupon",
                },
            ],
            "portfolio_analysis": "The portfolio shifted toward higher coupons.",
            "leverage_liquidity_analysis": "Leverage increased modestly.",
            "hedging_analysis": "Swap notional increased to offset duration.",
            "repo_analysis": "Repo book remained stable.",
            "dividend_analysis": "Dividend appears well-covered.",
            "anomalies": [
                {
                    "metric": "implied_leverage",
                    "description": "Leverage above recent range",
                    "severity": "medium",
                    "current_value": 7.9,
                    "expected_range": "6.5-7.5",
                },
            ],
            "new_items": ["New coupon 6.5s added to portfolio"],
            "removed_items": None,
            "footnote_changes": ["Footnote 3 wording changed regarding duration methodology"],
            "full_analysis": "# Monthly Comparison\n\nDetailed analysis here.",
        }

    def test_valid_comparison_payload(self, good_comparison_payload):
        analysis = ComparisonAnalysis(**good_comparison_payload)
        assert analysis.period_label == "March 2026 vs February 2026"
        assert len(analysis.key_metric_changes) == 1
        assert len(analysis.anomalies) == 1
        assert analysis.anomalies[0].severity == "medium"

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            ComparisonAnalysis(period_label="test")  # missing many required fields

    def test_empty_lists_valid(self, good_comparison_payload):
        good_comparison_payload["key_metric_changes"] = []
        good_comparison_payload["portfolio_shifts"] = []
        good_comparison_payload["anomalies"] = []
        analysis = ComparisonAnalysis(**good_comparison_payload)
        assert analysis.key_metric_changes == []
        assert analysis.anomalies == []

    def test_anomaly_flag_validation(self):
        anomaly = AnomalyFlag(
            metric="debt_equity",
            description="Above historical range",
            severity="high",
            current_value=8.5,
            expected_range="5.5-7.0",
        )
        assert anomaly.severity == "high"

    def test_anomaly_flag_missing_required(self):
        with pytest.raises(ValidationError):
            AnomalyFlag(metric="test")  # missing description and severity

    def test_metric_change_validation(self):
        change = MetricChange(
            metric_name="Stock Price",
            direction="up",
            significance="normal",
        )
        assert change.current_value is None
        assert change.direction == "up"

    def test_metric_change_missing_required(self):
        with pytest.raises(ValidationError):
            MetricChange(metric_name="test")  # missing direction and significance

    def test_portfolio_shift_validation(self):
        shift = PortfolioShift(coupon="30y 5.5s")
        assert shift.prior_pct is None
        assert shift.current_pct is None

    def test_model_dump_roundtrip(self, good_comparison_payload):
        analysis = ComparisonAnalysis(**good_comparison_payload)
        dumped = analysis.model_dump()
        analysis2 = ComparisonAnalysis(**dumped)
        assert analysis2.summary == analysis.summary
        assert len(analysis2.key_metric_changes) == len(analysis.key_metric_changes)
