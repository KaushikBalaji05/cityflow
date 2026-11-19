-- Separate cache: never mix provider content with authoritative transit data.
CREATE TABLE IF NOT EXISTS geocoding_cache (
    normalized_query TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (provider = 'geoapify'),
    results JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (normalized_query, provider)
);
CREATE INDEX IF NOT EXISTS idx_geocoding_cache_expiry ON geocoding_cache(expires_at);
-- Geometry index in migration 001 cannot service geography casts.
CREATE INDEX IF NOT EXISTS idx_transit_stops_geography
    ON transit_stops USING GIST ((location::geography));
-- pg_trgm intentionally deferred: fuzzy cache reuse can return the wrong location.
