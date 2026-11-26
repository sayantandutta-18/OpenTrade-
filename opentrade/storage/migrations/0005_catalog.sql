-- Migration 0005: Company catalog
CREATE TABLE IF NOT EXISTS company_catalog (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT NOT NULL,
    hq_city TEXT NOT NULL,
    hq_country TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    market_cap_usd_bn REAL,
    source TEXT NOT NULL,
    source_date TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_company_catalog_sector ON company_catalog(sector);
