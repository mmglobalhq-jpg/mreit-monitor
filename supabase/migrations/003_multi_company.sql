-- Multi-company expansion
-- Migration 003: company_documents table, universal_extractions table, seed new companies
--
-- Additive migration — does NOT modify existing tables or data.
-- NOTE: Uses "company_documents" instead of "documents" to avoid conflict
-- with pre-existing documents table from another application.

-- ============================================================================
-- COMPANY_DOCUMENTS
-- Tracks all document types across all companies (broader than filings table
-- which is ARMOUR-specific monthly/quarterly pipeline)
-- ============================================================================
CREATE TABLE IF NOT EXISTS company_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    document_type TEXT NOT NULL,  -- 'monthly_update', 'quarterly_earnings', 'financial_supplement', 'investor_presentation', 'sec_filing', 'press_release', 'monthly_dividend', 'monthly_book_value'
    document_date DATE NOT NULL,
    period_end DATE,
    fiscal_quarter INT,
    fiscal_year INT,
    title TEXT,
    source_url TEXT,
    file_path TEXT,              -- Path in Supabase Storage
    raw_content TEXT,            -- Raw text/HTML content
    content_hash TEXT,           -- For dedup / change detection
    status TEXT DEFAULT 'detected',  -- detected, downloaded, extracted, completed, failed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, document_type, source_url)
);

CREATE INDEX IF NOT EXISTS idx_company_documents_company_type ON company_documents(company_id, document_type);
CREATE INDEX IF NOT EXISTS idx_company_documents_company_date ON company_documents(company_id, document_date DESC);
CREATE INDEX IF NOT EXISTS idx_company_documents_status ON company_documents(status);

-- ============================================================================
-- UNIVERSAL EXTRACTIONS
-- Normalized extraction output for any company / document type.
-- Indexed columns for common queries + JSONB for full flexible storage.
-- ============================================================================
CREATE TABLE IF NOT EXISTS universal_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    document_id UUID NOT NULL REFERENCES company_documents(id),
    document_type TEXT NOT NULL,
    period_end DATE NOT NULL,
    fiscal_quarter INT,
    fiscal_year INT NOT NULL,

    -- Universal fields as indexed columns for easy querying
    book_value_per_share NUMERIC,
    earnings_per_share NUMERIC,
    dividends_per_share NUMERIC,
    economic_return_pct NUMERIC,
    net_interest_spread NUMERIC,
    leverage_ratio NUMERIC,
    portfolio_size NUMERIC,
    agency_rmbs_holdings NUMERIC,
    weighted_avg_coupon NUMERIC,
    avg_asset_yield NUMERIC,
    avg_cost_of_funds NUMERIC,

    -- Flexible storage for everything else
    extraction_data JSONB NOT NULL,     -- Full UniversalExtraction serialized
    management_commentary TEXT,
    key_highlights JSONB,               -- list of strings
    extraction_confidence NUMERIC,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id)
);

CREATE INDEX IF NOT EXISTS idx_universal_extractions_company ON universal_extractions(company_id);
CREATE INDEX IF NOT EXISTS idx_universal_extractions_period ON universal_extractions(company_id, period_end DESC);
CREATE INDEX IF NOT EXISTS idx_universal_extractions_type ON universal_extractions(document_type);

-- ============================================================================
-- SEED: New companies (BMNM, CIM, AGNC, NLY, DX)
-- ARR already exists from migration 001.
-- ============================================================================
INSERT INTO companies (ticker, name, cik, exchange, is_active, scrape_config)
VALUES
    ('BMNM', 'Bimini Capital Management', '0001275477', 'OTC',  true, '{
        "document_types": ["quarterly_earnings", "sec_filing"],
        "primary_focus": ["agency_rmbs", "advisory_services"],
        "notes": "Two segments: MBS portfolio + advisory services (Orchid Island Capital)"
    }'::jsonb),
    ('CIM', 'Chimera Investment Corporation', '0001409493', 'NYSE', true, '{
        "document_types": ["quarterly_earnings", "financial_supplement", "investor_presentation", "sec_filing"],
        "primary_focus": ["agency_rmbs", "non_agency_rmbs", "residential_loans", "msr", "cmbs", "origination"],
        "notes": "Hybrid REIT. Separate financial supplement. HomeXpress origination data."
    }'::jsonb),
    ('AGNC', 'AGNC Investment Corp', '0001423689', 'NASDAQ', true, '{
        "document_types": ["quarterly_earnings", "monthly_book_value", "investor_presentation", "sec_filing"],
        "primary_focus": ["agency_rmbs", "tba_securities"],
        "notes": "Earnings press release IS the supplement (20+ pages). Monthly BV estimate press releases. Largest pure Agency REIT."
    }'::jsonb),
    ('NLY', 'Annaly Capital Management', '0001043219', 'NYSE', true, '{
        "document_types": ["quarterly_earnings", "financial_supplement", "investor_presentation", "sec_filing"],
        "primary_focus": ["agency_rmbs", "residential_credit", "msr"],
        "notes": "Three segments: Agency, Residential Credit, MSR. Three docs per quarter. Largest mREIT overall."
    }'::jsonb),
    ('DX', 'Dynex Capital', '0000826675', 'NYSE', true, '{
        "document_types": ["quarterly_earnings", "investor_presentation", "monthly_dividend", "sec_filing"],
        "primary_focus": ["agency_rmbs", "agency_cmbs"],
        "notes": "Monthly dividend press releases may include market commentary. Both RMBS and CMBS."
    }'::jsonb)
ON CONFLICT (ticker) DO NOTHING;
