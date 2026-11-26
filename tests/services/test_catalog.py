"""Tests for company catalog loader, search, presets, and 6-company comparison limit (T4.1-T4.3).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-23 to AC-26) and docs/SRS.md (FR-29 to FR-32).
"""

from pathlib import Path

import pytest

from opentrade.services.catalog import (
    MAX_COMPARE,
    ComparisonSet,
    get_map_pins,
    load_catalog,
    load_presets,
    search_companies,
)
from opentrade.services.errors import CompareLimitError, ValidationError


def test_load_catalog_validates_rows_and_preserves_source_date_t4_1() -> None:
    """T4.1: Catalog loads ~190 rows with source and source_date metadata."""
    companies = load_catalog()
    assert 180 <= len(companies) <= 210
    for company in companies:
        assert company.symbol
        assert company.name
        assert company.sector
        assert company.source
        assert company.source_date
        assert -90.0 <= company.lat <= 90.0
        assert -180.0 <= company.lon <= 180.0


def test_load_catalog_rejects_malformed_row_t4_1(tmp_path: Path) -> None:
    """T4.1: Catalog loader rejects rows with missing required fields or invalid coordinates."""
    bad_csv = tmp_path / "bad_catalog.csv"
    bad_csv.write_text(
        "symbol,name,sector,hq_city,hq_country,lat,lon,market_cap_usd_bn,source,source_date\n"
        "BAD,Broken Corp,Tech,NYC,USA,not_a_float,-74.0,10.0,Src,2026-01-15\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_catalog(bad_csv)


def test_search_companies_case_insensitive_max_20_ac23_t4_2() -> None:
    """T4.2, AC-23: Searching 'micro' matches case-insensitively and caps at 20 results."""
    matches = search_companies(query="micro")
    assert len(matches) >= 3
    assert len(matches) <= 20
    assert all(
        "micro" in c.name.lower() or "micro" in c.symbol.lower() or "micro" in c.sector.lower()
        for c in matches
    )

    tech_matches = search_companies(query="", sector="Tech")
    assert len(tech_matches) == 20
    assert all(c.sector == "Tech" for c in tech_matches)


def test_presets_resolve_to_catalog_symbols_ac26_t4_2() -> None:
    """T4.2, AC-26: Every preset symbol resolves to a valid company in catalog.csv."""
    catalog_symbols = {c.symbol for c in load_catalog()}
    presets = load_presets()
    assert len(presets) >= 4
    for preset in presets:
        assert len(preset.symbols) <= MAX_COMPARE
        for sym in preset.symbols:
            assert sym in catalog_symbols


def test_map_pins_have_required_fields_ac25() -> None:
    """AC-25: Each map pin includes symbol, name, sector, lat, lon, and market_cap."""
    pins = get_map_pins()
    assert len(pins) >= 180
    first = pins[0]
    assert first["symbol"]
    assert first["name"]
    assert first["sector"]
    assert isinstance(first["lat"], float)
    assert isinstance(first["lon"], float)
    assert "market_cap" in first


def test_comparison_set_enforces_six_company_limit_ac24_t4_3() -> None:
    """T4.3, AC-24: Adding a 7th company raises COMPARE_LIMIT and keeps set at 6."""
    basket = ComparisonSet()
    for sym in ("AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META"):
        basket.add(sym)
    assert len(basket.symbols) == MAX_COMPARE == 6

    with pytest.raises(CompareLimitError) as exc_info:
        basket.add("JPM")
    assert exc_info.value.code == "COMPARE_LIMIT"
    assert len(basket.symbols) == 6

    # Remove, preset load, and clear work cleanly
    basket.remove("META")
    assert len(basket.symbols) == 5
    basket.load_preset("global_banks")
    assert len(basket.symbols) == 6
    assert "JPM" in basket.symbols
    basket.clear()
    assert basket.symbols == []
