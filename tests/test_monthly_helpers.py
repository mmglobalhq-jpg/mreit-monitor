"""
Tests for helper functions in src/parsers/monthly_update.py.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.parsers.monthly_update import (
    _build_metrics_summary,
    _get_nested,
    _parse_cpr_month,
    _parse_date_string,
)
from src.models.schemas import (
    DividendInfo,
    KeyMetrics,
    MonthlyUpdateExtraction,
)


# ============================================================================
# _parse_cpr_month
# ============================================================================


class TestParseCprMonth:
    def test_j_2024(self):
        """Single-letter abbreviation for January."""
        result = _parse_cpr_month("J 2024")
        assert result == "2024-01-01"

    def test_f_2025(self):
        """Single-letter abbreviation for February."""
        result = _parse_cpr_month("F 2025")
        assert result == "2025-02-01"

    def test_mr_2025(self):
        """Two-letter abbreviation for March."""
        result = _parse_cpr_month("Mr 2025")
        assert result == "2025-03-01"

    def test_a_2025(self):
        result = _parse_cpr_month("A 2025")
        assert result == "2025-04-01"

    def test_m_2025(self):
        result = _parse_cpr_month("M 2025")
        assert result == "2025-05-01"

    def test_jn_2025(self):
        result = _parse_cpr_month("Jn 2025")
        assert result == "2025-06-01"

    def test_jl_2025(self):
        result = _parse_cpr_month("Jl 2025")
        assert result == "2025-07-01"

    def test_au_2025(self):
        result = _parse_cpr_month("Au 2025")
        assert result == "2025-08-01"

    def test_s_2025(self):
        result = _parse_cpr_month("S 2025")
        assert result == "2025-09-01"

    def test_o_2025(self):
        result = _parse_cpr_month("O 2025")
        assert result == "2025-10-01"

    def test_n_2025(self):
        result = _parse_cpr_month("N 2025")
        assert result == "2025-11-01"

    def test_d_2025(self):
        result = _parse_cpr_month("D 2025")
        assert result == "2025-12-01"

    def test_full_month_name(self):
        result = _parse_cpr_month("January 2024")
        assert result == "2024-01-01"

    def test_three_letter_abbreviation(self):
        result = _parse_cpr_month("Mar 2025")
        assert result == "2025-03-01"

    def test_none_input(self):
        result = _parse_cpr_month(None)
        assert result is None

    def test_empty_string(self):
        result = _parse_cpr_month("")
        assert result is None

    def test_invalid_abbreviation(self):
        result = _parse_cpr_month("ZZ 2025")
        assert result is None

    def test_single_word_no_year(self):
        # Single part with no space — len(parts) != 2, goes to dateutil fallback
        result = _parse_cpr_month("January")
        # dateutil may or may not parse this; either a valid date or None is acceptable
        # The point is it doesn't crash
        assert result is None or isinstance(result, str)

    def test_whitespace_handling(self):
        result = _parse_cpr_month("  F 2025  ")
        assert result == "2025-02-01"


# ============================================================================
# _parse_date_string
# ============================================================================


class TestParseDateString:
    def test_standard_us_format(self):
        result = _parse_date_string("3/16/2026")
        assert result == "2026-03-16"

    def test_two_digit_month_day(self):
        result = _parse_date_string("12/31/2025")
        assert result == "2025-12-31"

    def test_none_input(self):
        result = _parse_date_string(None)
        assert result is None

    def test_empty_string(self):
        result = _parse_date_string("")
        assert result is None

    def test_invalid_string(self):
        result = _parse_date_string("not-a-date")
        assert result is None

    def test_iso_format(self):
        result = _parse_date_string("2025-06-30")
        assert result == "2025-06-30"

    def test_written_date(self):
        result = _parse_date_string("March 16, 2026")
        assert result == "2026-03-16"


# ============================================================================
# _get_nested
# ============================================================================


class TestGetNested:
    def test_simple_path(self):
        data = {"key_metrics": {"stock_price": 19.50}}
        result = _get_nested(data, "key_metrics.stock_price")
        assert result == 19.50

    def test_single_key(self):
        data = {"value": 42}
        result = _get_nested(data, "value")
        assert result == 42

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": {"d": 99}}}}
        result = _get_nested(data, "a.b.c.d")
        assert result == 99

    def test_missing_intermediate_key(self):
        data = {"key_metrics": {"stock_price": 19.50}}
        result = _get_nested(data, "key_metrics.nonexistent")
        assert result is None

    def test_missing_top_level_key(self):
        data = {"key_metrics": {"stock_price": 19.50}}
        result = _get_nested(data, "nonexistent.stock_price")
        assert result is None

    def test_none_data(self):
        result = _get_nested(None, "key_metrics.stock_price")
        assert result is None

    def test_empty_dict(self):
        result = _get_nested({}, "key_metrics.stock_price")
        assert result is None

    def test_non_dict_intermediate(self):
        data = {"key_metrics": "not_a_dict"}
        result = _get_nested(data, "key_metrics.stock_price")
        assert result is None

    def test_returns_dict(self):
        data = {"a": {"b": {"c": 1}}}
        result = _get_nested(data, "a.b")
        assert result == {"c": 1}


# ============================================================================
# _build_metrics_summary
# ============================================================================


class TestBuildMetricsSummary:
    def _make_extraction(self, stock_price=19.50, debt_equity=6.8, dividend=0.24, dividend_yield=14.8):
        """Create a minimal MonthlyUpdateExtraction for testing."""
        return MonthlyUpdateExtraction(
            company_name="ARMOUR Residential REIT",
            update_month="March 2026",
            data_as_of_date="02/28/2026",
            key_metrics=KeyMetrics(
                as_of_date="02/28/2026",
                stock_price=stock_price,
                debt_equity=debt_equity,
                implied_leverage=7.9,
                liquidity_millions=525.0,
                liquidity_pct_capital=7.5,
            ),
            dividend_info=DividendInfo(
                monthly_dividend=dividend,
                dividend_yield=dividend_yield,
            ),
            portfolio_positions=[],
            repo_positions=[],
            swap_positions=[],
            hedge_summary=[],
            footnotes=[],
        )

    def test_returns_list_of_dicts(self):
        extraction = self._make_extraction()
        result = _build_metrics_summary(extraction, None)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    def test_metric_names_present(self):
        extraction = self._make_extraction()
        result = _build_metrics_summary(extraction, None)
        names = [r["name"] for r in result]
        assert "Stock Price" in names
        assert "Debt/Equity" in names
        assert "Monthly Dividend" in names
        assert "Dividend Yield" in names

    def test_no_prior_data(self):
        extraction = self._make_extraction()
        result = _build_metrics_summary(extraction, None)
        for entry in result:
            assert entry["prior"] == "\u2014"
            assert entry["delta_str"] == "\u2014"
            assert entry["direction"] == "flat"

    def test_with_prior_data(self):
        extraction = self._make_extraction(stock_price=19.50)
        prior_data = {
            "data": {
                "key_metrics": {
                    "stock_price": 18.50,
                    "debt_equity": 6.5,
                    "implied_leverage": 7.5,
                    "liquidity_millions": 500.0,
                    "liquidity_pct_capital": 7.0,
                },
                "dividend_info": {
                    "monthly_dividend": 0.24,
                    "dividend_yield": 15.0,
                },
            }
        }
        result = _build_metrics_summary(extraction, prior_data)

        stock_entry = next(r for r in result if r["name"] == "Stock Price")
        assert stock_entry["direction"] == "up"
        assert "$1.00" in stock_entry["delta_str"]

    def test_flat_direction_when_no_change(self):
        extraction = self._make_extraction(stock_price=19.50)
        prior_data = {
            "data": {
                "key_metrics": {
                    "stock_price": 19.50,
                    "debt_equity": 6.8,
                    "implied_leverage": 7.9,
                    "liquidity_millions": 525.0,
                    "liquidity_pct_capital": 7.5,
                },
                "dividend_info": {
                    "monthly_dividend": 0.24,
                    "dividend_yield": 14.8,
                },
            }
        }
        result = _build_metrics_summary(extraction, prior_data)

        stock_entry = next(r for r in result if r["name"] == "Stock Price")
        assert stock_entry["direction"] == "flat"

    def test_down_direction(self):
        extraction = self._make_extraction(stock_price=17.00)
        prior_data = {
            "data": {
                "key_metrics": {
                    "stock_price": 19.50,
                    "debt_equity": None,
                    "implied_leverage": None,
                    "liquidity_millions": None,
                    "liquidity_pct_capital": None,
                },
                "dividend_info": {
                    "monthly_dividend": None,
                    "dividend_yield": None,
                },
            }
        }
        result = _build_metrics_summary(extraction, prior_data)

        stock_entry = next(r for r in result if r["name"] == "Stock Price")
        assert stock_entry["direction"] == "down"
