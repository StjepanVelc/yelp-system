-- Migration: 001_add_fts_search_vector
-- Adds full-text search support to the businesses table.
-- Safe to run multiple times (idempotent).

-- Enable trigram extension for similarity/trigram search
CREATE EXTENSION
IF NOT EXISTS pg_trgm;

-- Add the search_vector column if it doesn't exist
ALTER TABLE businesses ADD COLUMN
IF NOT EXISTS search_vector tsvector;

-- Populate search_vector for all existing rows
UPDATE businesses
SET search_vector = to_tsvector('simple',
    concat_ws(' ',
        coalesce(name, ''),
        coalesce(categories, ''),
        coalesce(city, ''),
        coalesce(state, ''),
        coalesce(address, '')
    )
);

-- GIN index for fast full-text search
CREATE INDEX
IF NOT EXISTS businesses_search_vector_gin
    ON businesses USING GIN
(search_vector);

-- Trigram index on name for ILIKE / similarity queries
CREATE INDEX
IF NOT EXISTS businesses_name_trgm
    ON businesses USING GIN
(name gin_trgm_ops);

-- Trigram index on categories
CREATE INDEX
IF NOT EXISTS businesses_categories_trgm
    ON businesses USING GIN
(categories gin_trgm_ops);

-- Function to auto-update search_vector on insert/update
CREATE OR REPLACE FUNCTION businesses_search_vector_update
()
RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector
('simple',
        concat_ws
(' ',
            coalesce
(NEW.name, ''),
            coalesce
(NEW.categories, ''),
            coalesce
(NEW.city, ''),
            coalesce
(NEW.state, ''),
            coalesce
(NEW.address, '')
        )
    );
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: keep search_vector in sync automatically
DROP TRIGGER IF EXISTS trg_businesses_search_vector_update
ON businesses;
CREATE TRIGGER trg_businesses_search_vector_update
    BEFORE
INSERT OR
UPDATE OF name, categories, city, state, address
    ON businesses
    FOR EACH ROW
EXECUTE FUNCTION businesses_search_vector_update
();
