-- Add filing type values that exist in Python but were missing from the DB enum
ALTER TYPE filing_type ADD VALUE IF NOT EXISTS 'financial_supplement';
ALTER TYPE filing_type ADD VALUE IF NOT EXISTS 'monthly_dividend';
ALTER TYPE filing_type ADD VALUE IF NOT EXISTS 'monthly_book_value';
ALTER TYPE filing_type ADD VALUE IF NOT EXISTS 'press_release';
