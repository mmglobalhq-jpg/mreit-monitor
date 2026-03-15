-- Summary Reports and Investor Materials tables
-- Migration 002

CREATE TABLE summary_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    report_type TEXT NOT NULL,  -- 'monthly', 'quarterly', 'annual'
    period_label TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    report_json JSONB NOT NULL,
    email_sent BOOLEAN DEFAULT false,
    email_sent_at TIMESTAMPTZ,
    model_used TEXT,
    tokens_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, report_type, period_start)
);

CREATE TABLE investor_materials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    material_type TEXT NOT NULL,
    material_date DATE,
    material_title TEXT,
    source_url TEXT,
    raw_content TEXT,
    analysis_json JSONB,
    analyzed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_summary_reports_company_id ON summary_reports(company_id);
CREATE INDEX idx_summary_reports_type ON summary_reports(report_type);
CREATE INDEX idx_summary_reports_period ON summary_reports(period_start, period_end);
CREATE INDEX idx_investor_materials_company_id ON investor_materials(company_id);
