-- A/B test results for comparing extraction models
CREATE TABLE IF NOT EXISTS extraction_comparisons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES company_documents(id),
    model_name TEXT NOT NULL,
    extraction_data JSONB,
    extraction_confidence NUMERIC,
    fields_extracted INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost NUMERIC,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_extraction_comparisons_document ON extraction_comparisons(document_id);
CREATE INDEX idx_extraction_comparisons_model ON extraction_comparisons(model_name);

-- RLS
ALTER TABLE extraction_comparisons ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on extraction_comparisons"
    ON extraction_comparisons FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Authenticated read on extraction_comparisons"
    ON extraction_comparisons FOR SELECT TO authenticated USING (true);
