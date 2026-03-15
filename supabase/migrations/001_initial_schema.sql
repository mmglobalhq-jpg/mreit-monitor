-- mREIT Monitor Database Schema
-- Migration 001: Initial schema
-- Run against Supabase PostgreSQL

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- COMPANIES
-- Registry of monitored mREIT companies
-- ============================================================================
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker TEXT NOT NULL UNIQUE,           -- e.g., 'ARR'
    name TEXT NOT NULL,                     -- e.g., 'ARMOUR Residential REIT, Inc.'
    cik TEXT NOT NULL UNIQUE,               -- SEC CIK, e.g., '0001428205'
    exchange TEXT DEFAULT 'NYSE',
    is_active BOOLEAN DEFAULT true,
    
    -- URLs for scraping
    monthly_updates_url TEXT,               -- IR page with monthly PDF links
    quarterly_reports_url TEXT,             -- IR page with 10-Q/10-K links
    annual_reports_url TEXT,                -- IR page with annual report links
    news_url TEXT,                          -- IR news/press releases page
    
    -- Scraping configuration (CSS selectors, parsing quirks)
    scrape_config JSONB DEFAULT '{}',
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- FILINGS
-- Every document we've detected, downloaded, and processed
-- ============================================================================
CREATE TYPE filing_type AS ENUM (
    'monthly_update',
    'earnings_release', 
    'quarterly_10q',
    'annual_10k',
    'investor_presentation',
    'annual_report',
    'proxy_statement',
    'other'
);

CREATE TYPE filing_status AS ENUM (
    'detected',        -- Found on IR page / EDGAR, not yet downloaded
    'downloaded',      -- PDF/HTML stored in Supabase Storage
    'extracting',      -- Currently being processed by extraction agent
    'extracted',       -- Structured data stored, awaiting comparison
    'comparing',       -- Comparison agent running
    'completed',       -- Fully processed, email sent
    'extraction_failed',
    'validation_failed',
    'comparison_failed'
);

CREATE TABLE filings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    
    filing_type filing_type NOT NULL,
    status filing_status DEFAULT 'detected',
    
    -- Source info
    source_url TEXT NOT NULL,               -- Original URL where filing was found
    source_page TEXT,                       -- Which IR page it was found on
    edgar_accession_number TEXT,            -- SEC EDGAR accession number if applicable
    
    -- Document info
    filing_date DATE NOT NULL,              -- Date the filing was posted/filed
    period_date DATE,                       -- The as-of date for the data (e.g., 02/28/2026)
    period_label TEXT,                      -- Human-readable period (e.g., "March 2026", "Q4 2025")
    
    -- Storage
    storage_path TEXT,                      -- Path in Supabase Storage
    storage_bucket TEXT DEFAULT 'filings',
    
    -- Extraction metadata
    raw_extraction_json JSONB,              -- Raw Claude response for debugging
    extraction_model TEXT,                  -- Which Claude model was used
    extraction_tokens_used INTEGER,
    extraction_cost_cents INTEGER,
    
    -- Processing timestamps
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    downloaded_at TIMESTAMPTZ,
    extracted_at TIMESTAMPTZ,
    compared_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Error tracking
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Prevent duplicate processing
    UNIQUE(company_id, source_url)
);

CREATE INDEX idx_filings_company_type ON filings(company_id, filing_type);
CREATE INDEX idx_filings_company_date ON filings(company_id, filing_date DESC);
CREATE INDEX idx_filings_status ON filings(status);

-- ============================================================================
-- MONTHLY METRICS
-- Key headline metrics from monthly company updates
-- One row per filing (per month)
-- ============================================================================
CREATE TABLE monthly_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id),
    as_of_date DATE NOT NULL,              -- Date the data is as of
    
    -- Key Data
    stock_price NUMERIC(10,4),
    debt_equity NUMERIC(6,2),
    implied_leverage NUMERIC(6,2),
    liquidity_millions NUMERIC(12,2),
    liquidity_pct_capital NUMERIC(5,2),
    market_cap_millions NUMERIC(12,2),
    
    -- Dividend Info
    monthly_dividend NUMERIC(8,4),
    ex_dividend_date DATE,
    record_date DATE,
    pay_date DATE,
    dividend_yield NUMERIC(6,2),
    
    -- Portfolio Totals
    total_portfolio_value_millions NUMERIC(14,2),
    agency_portfolio_pct NUMERIC(6,2),
    agency_portfolio_value_millions NUMERIC(14,2),
    tba_positions_pct NUMERIC(6,2),
    tba_positions_value_millions NUMERIC(14,2),
    treasury_positions_pct NUMERIC(6,2),
    treasury_positions_value_millions NUMERIC(14,2),
    
    -- Repo Totals
    total_repo_borrowed_millions NUMERIC(14,2),
    buckler_repo_pct NUMERIC(6,2),
    buckler_repo_millions NUMERIC(14,2),
    total_repo_wtd_avg_original_term_days NUMERIC(6,1),
    total_repo_wtd_avg_remaining_term_days NUMERIC(6,1),
    
    -- Swap Totals
    total_swap_notional_millions NUMERIC(14,2),
    total_swap_wtd_avg_term_months NUMERIC(6,1),
    total_swap_wtd_avg_rate NUMERIC(6,4),
    
    -- Hedge Totals
    swap_hedge_notional_millions NUMERIC(14,2),
    treasury_futures_notional_millions NUMERIC(14,2),
    treasury_futures_wtd_avg_duration_years NUMERIC(6,2),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(company_id, as_of_date)
);

CREATE INDEX idx_monthly_metrics_company_date ON monthly_metrics(company_id, as_of_date DESC);

-- ============================================================================
-- PORTFOLIO POSITIONS
-- Granular coupon-level portfolio breakdown from monthly updates
-- Multiple rows per filing (one per security/coupon)
-- ============================================================================
CREATE TABLE portfolio_positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id),
    as_of_date DATE NOT NULL,
    
    -- Position detail
    security_type TEXT NOT NULL,            -- e.g., 'Agency CMBS', '30Y Fixed Rate Pools', 'Conventionals', 'Ginnie Mae', 'Net TBA Positions', 'US Treasury Long Positions'
    coupon TEXT,                            -- e.g., '30y 2.0s', '30y 5.5s', 'FN 30y 4.5 TBAs', null for aggregates
    is_subtotal BOOLEAN DEFAULT false,      -- True for aggregate rows like 'Conventionals', '30Y Fixed Rate Pools'
    parent_category TEXT,                   -- Parent grouping (e.g., 'Conventionals' for coupon rows)
    
    pct_portfolio NUMERIC(6,2),
    market_value_millions NUMERIC(14,2),
    effective_duration NUMERIC(8,4),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_portfolio_positions_filing ON portfolio_positions(filing_id);
CREATE INDEX idx_portfolio_positions_company_date ON portfolio_positions(company_id, as_of_date DESC);

-- ============================================================================
-- REPO POSITIONS
-- Repurchase agreement breakdown from monthly updates
-- ============================================================================
CREATE TABLE repo_positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id),
    as_of_date DATE NOT NULL,
    
    counterparty TEXT NOT NULL,             -- e.g., 'BUCKLER Securities LLC', 'All Other Counterparties', 'Total'
    is_affiliate BOOLEAN DEFAULT false,
    is_total BOOLEAN DEFAULT false,
    
    principal_borrowed_millions NUMERIC(14,2),
    pct_of_repo NUMERIC(6,2),
    wtd_avg_original_term_days NUMERIC(6,1),
    wtd_avg_remaining_term_days NUMERIC(6,1),
    longest_maturity_days INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_repo_positions_filing ON repo_positions(filing_id);

-- ============================================================================
-- SWAP POSITIONS
-- Interest rate swap schedule from monthly updates
-- ============================================================================
CREATE TABLE swap_positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id),
    as_of_date DATE NOT NULL,
    
    maturity_bucket TEXT NOT NULL,          -- e.g., '0-12', '13-24', '>120', 'Total'
    is_total BOOLEAN DEFAULT false,
    
    notional_millions NUMERIC(14,2),
    wtd_avg_remaining_term_months NUMERIC(6,1),
    wtd_avg_rate NUMERIC(8,4),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_swap_positions_filing ON swap_positions(filing_id);

-- ============================================================================
-- QUARTERLY METRICS
-- Headline metrics from quarterly earnings releases and 10-Q/10-K
-- ============================================================================
CREATE TABLE quarterly_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id),
    period_end_date DATE NOT NULL,          -- e.g., 2025-12-31
    quarter_label TEXT NOT NULL,            -- e.g., 'Q4 2025'
    
    -- Income Statement
    gaap_net_income_millions NUMERIC(14,2),
    gaap_eps NUMERIC(10,4),
    net_interest_income_millions NUMERIC(14,2),
    distributable_earnings_millions NUMERIC(14,2),
    distributable_eps NUMERIC(10,4),
    
    -- Yield & Spread
    avg_interest_income_rate NUMERIC(6,4),
    avg_interest_expense_rate NUMERIC(6,4),
    economic_interest_income_rate NUMERIC(6,4),
    economic_interest_expense_rate NUMERIC(6,4),
    economic_net_interest_spread NUMERIC(6,4),
    
    -- Balance Sheet / Position
    book_value_per_share NUMERIC(10,4),
    total_portfolio_billions NUMERIC(10,2),
    agency_mbs_pct NUMERIC(6,2),
    
    -- Returns
    quarterly_total_economic_return NUMERIC(8,4),
    ytd_total_economic_return NUMERIC(8,4),
    annual_total_economic_return NUMERIC(8,4),  -- only for Q4/annual
    
    -- Capital
    liquidity_millions NUMERIC(14,2),
    repo_agreements_net_millions NUMERIC(14,2),
    affiliate_repo_pct NUMERIC(6,2),
    debt_equity_ratio NUMERIC(6,2),
    implied_leverage NUMERIC(6,2),
    
    -- Equity Issuance
    atm_capital_raised_millions NUMERIC(14,2),
    atm_shares_issued INTEGER,
    
    -- Dividends
    quarterly_dividend_per_share NUMERIC(8,4),
    dividend_payout_ratio NUMERIC(8,4),     -- dividend / distributable earnings
    
    -- Tax Treatment
    ordinary_income_pct NUMERIC(6,2),
    return_of_capital_pct NUMERIC(6,2),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(company_id, period_end_date)
);

CREATE INDEX idx_quarterly_metrics_company_date ON quarterly_metrics(company_id, period_end_date DESC);

-- ============================================================================
-- CPR DATA
-- Monthly CPR values extracted from the CPR chart in monthly updates
-- ============================================================================
CREATE TABLE cpr_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id),
    
    month DATE NOT NULL,                    -- First of the month for the CPR reading
    cpr_value NUMERIC(6,2),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(company_id, month)
);

CREATE INDEX idx_cpr_data_company_month ON cpr_data(company_id, month DESC);

-- ============================================================================
-- AGENT ANALYSES
-- AI-generated analysis briefs from the comparison agent
-- ============================================================================
CREATE TABLE agent_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id),
    
    analysis_type TEXT NOT NULL,            -- 'monthly_comparison', 'quarterly_comparison', 'annual_review', 'anomaly_alert'
    period_label TEXT,                      -- e.g., 'March 2026 vs February 2026'
    
    -- The analysis content
    summary TEXT,                           -- Short 2-3 sentence executive summary
    full_analysis TEXT,                     -- Full comparative brief (markdown)
    key_changes JSONB,                      -- Structured list of notable changes
    anomalies JSONB,                        -- Flagged anomalies with severity
    
    -- What data was compared
    current_period_date DATE,
    prior_period_date DATE,
    
    -- Agent metadata
    model_used TEXT,
    tokens_used INTEGER,
    cost_cents INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_analyses_filing ON agent_analyses(filing_id);
CREATE INDEX idx_agent_analyses_company_type ON agent_analyses(company_id, analysis_type);

-- ============================================================================
-- FILING FOOTNOTES
-- Tracked footnotes from monthly updates (for change detection)
-- ============================================================================
CREATE TABLE filing_footnotes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id),
    as_of_date DATE NOT NULL,
    
    footnote_number INTEGER NOT NULL,
    footnote_text TEXT NOT NULL,
    
    -- Change detection
    changed_from_prior BOOLEAN DEFAULT false,
    prior_text TEXT,                        -- Previous version if changed
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_filing_footnotes_filing ON filing_footnotes(filing_id);

-- ============================================================================
-- POLL LOG
-- Track polling runs for debugging and rate limiting
-- ============================================================================
CREATE TABLE poll_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id),
    
    poll_type TEXT NOT NULL,                -- 'ir_page', 'edgar_api'
    poll_url TEXT,
    
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    
    new_filings_found INTEGER DEFAULT 0,
    error_message TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_poll_log_company_date ON poll_log(company_id, created_at DESC);

-- ============================================================================
-- UPDATED_AT TRIGGER
-- Auto-update the updated_at column on row changes
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER filings_updated_at
    BEFORE UPDATE ON filings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- SEED: ARMOUR company record
-- ============================================================================
INSERT INTO companies (ticker, name, cik, exchange, monthly_updates_url, quarterly_reports_url, annual_reports_url, news_url, scrape_config)
VALUES (
    'ARR',
    'ARMOUR Residential REIT, Inc.',
    '0001428205',
    'NYSE',
    'https://www.armourreit.com/news-events/monthly-company-updates',
    'https://www.armourreit.com/financials/quarterly-reports',
    'https://www.armourreit.com/financials/annual-reports',
    'https://www.armourreit.com/news-events/news',
    '{
        "monthly_updates": {
            "link_selector": "a[href*=\"/static-files/\"]",
            "date_pattern": "MM/DD/YYYY preceding the link",
            "pdf_title_attr": "title"
        },
        "quarterly_reports": {
            "year_selector": "h2",
            "quarter_selector": "h3",
            "link_types": {
                "earnings_release": "Earnings Release",
                "10q": "10-Q",
                "10k": "10-K",
                "webcast": "Webcast",
                "investor_presentation": "Investor Presentation"
            }
        }
    }'::jsonb
);
