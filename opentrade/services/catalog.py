"""Company catalog loader, search, presets, and 6-company comparison set (T4.1-T4.3)."""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opentrade.config import Provenance
from opentrade.services.errors import CompareLimitError, ValidationError

CATALOG_PATH = Path("data/catalog.csv")
PRESETS_PATH = Path("data/presets.json")
MAX_COMPARE = 6
MAX_SEARCH_RESULTS = 20

VALID_SECTORS = (
    "Tech",
    "Financials",
    "Auto",
    "Energy",
    "Healthcare",
    "Consumer",
    "Industrials",
    "Telecom",
    "Retail",
    "Materials",
)


@dataclass(frozen=True)
class CompanyRecord:
    """Validated company catalog entry with source/date provenance."""

    symbol: str
    name: str
    sector: str
    hq_city: str
    hq_country: str
    lat: float
    lon: float
    market_cap_usd_bn: float | None
    source: str
    source_date: str
    provenance: Provenance = Provenance.REAL


@dataclass(frozen=True)
class PresetBasket:
    """Curated comparison basket of company symbols."""

    id: str
    name: str
    description: str
    symbols: tuple[str, ...]


def load_catalog(csv_path: str | Path = CATALOG_PATH) -> list[CompanyRecord]:
    """Load and validate companies from catalog.csv (T4.1)."""
    path = Path(csv_path)
    if not path.is_file():
        raise ValidationError(f"Catalog file not found: {path}")

    records: list[CompanyRecord] = []
    seen_symbols: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "symbol",
            "name",
            "sector",
            "hq_city",
            "hq_country",
            "lat",
            "lon",
            "market_cap_usd_bn",
            "source",
            "source_date",
        }
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValidationError("Catalog CSV missing required columns")

        for line_no, row in enumerate(reader, start=2):
            symbol = (row.get("symbol") or "").strip().upper()
            name = (row.get("name") or "").strip()
            sector = (row.get("sector") or "").strip()
            hq_city = (row.get("hq_city") or "").strip()
            hq_country = (row.get("hq_country") or "").strip()
            source = (row.get("source") or "").strip()
            source_date = (row.get("source_date") or "").strip()
            if not all([symbol, name, sector, hq_city, hq_country, source, source_date]):
                raise ValidationError(f"Catalog row {line_no} has empty required field")
            if sector not in VALID_SECTORS:
                raise ValidationError(f"Catalog row {line_no} has invalid sector: {sector!r}")
            if symbol in seen_symbols:
                raise ValidationError(f"Duplicate symbol {symbol!r} at row {line_no}")
            seen_symbols.add(symbol)

            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"Invalid lat/lon at row {line_no}") from exc
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                raise ValidationError(f"Out-of-range lat/lon at row {line_no}")

            cap_raw = (row.get("market_cap_usd_bn") or "").strip()
            try:
                market_cap = float(cap_raw) if cap_raw else None
            except ValueError as exc:
                raise ValidationError(f"Invalid market_cap at row {line_no}") from exc

            records.append(
                CompanyRecord(
                    symbol=symbol,
                    name=name,
                    sector=sector,
                    hq_city=hq_city,
                    hq_country=hq_country,
                    lat=lat,
                    lon=lon,
                    market_cap_usd_bn=market_cap,
                    source=source,
                    source_date=source_date,
                )
            )
    return records


def load_presets(
    presets_path: str | Path = PRESETS_PATH,
    catalog_path: str | Path = CATALOG_PATH,
) -> list[PresetBasket]:
    """Load curated preset baskets and verify all symbols exist in catalog (AC-26)."""
    catalog_symbols = {c.symbol for c in load_catalog(catalog_path)}
    raw = json.loads(Path(presets_path).read_text(encoding="utf-8"))
    baskets: list[PresetBasket] = []
    for item in raw.get("presets", []):
        syms = tuple(str(s).strip().upper() for s in item.get("symbols", []))
        unknown = [s for s in syms if s not in catalog_symbols]
        if unknown:
            raise ValidationError(f"Preset {item.get('id')!r} contains unknown symbols: {unknown}")
        baskets.append(
            PresetBasket(
                id=str(item["id"]),
                name=str(item["name"]),
                description=str(item.get("description", "")),
                symbols=syms,
            )
        )
    return baskets


def search_companies(
    query: str = "",
    sector: str | None = None,
    region: str | None = None,
    catalog_path: str | Path = CATALOG_PATH,
) -> list[CompanyRecord]:
    """Search companies case-insensitively across symbol/name/sector/country (AC-23)."""
    q = query.strip().lower()
    sec = sector.strip() if sector and sector.strip() else None
    reg = region.strip().lower() if region and region.strip() else None

    matches: list[CompanyRecord] = []
    for c in load_catalog(catalog_path):
        if sec and c.sector != sec:
            continue
        if reg and reg not in c.hq_country.lower() and reg not in c.hq_city.lower():
            continue
        if q and not (
            q in c.symbol.lower()
            or q in c.name.lower()
            or q in c.sector.lower()
            or q in c.hq_country.lower()
        ):
            continue
        matches.append(c)
        if len(matches) >= MAX_SEARCH_RESULTS:
            break
    return matches


def get_map_pins(
    sector: str | None = None,
    catalog_path: str | Path = CATALOG_PATH,
) -> list[dict[str, Any]]:
    """Return map pin dicts (symbol, name, sector, lat, lon, market_cap) per AC-25."""
    sec = sector.strip() if sector and sector.strip() else None
    pins: list[dict[str, Any]] = []
    for c in load_catalog(catalog_path):
        if sec and c.sector != sec:
            continue
        pins.append(
            {
                "symbol": c.symbol,
                "name": c.name,
                "sector": c.sector,
                "hq_city": c.hq_city,
                "hq_country": c.hq_country,
                "lat": c.lat,
                "lon": c.lon,
                "market_cap": c.market_cap_usd_bn,
                "source": c.source,
                "source_date": c.source_date,
                "provenance": c.provenance.value,
            }
        )
    return pins


@dataclass
class ComparisonSet:
    """Mutable comparison basket enforcing the 6-company limit (AC-24, T4.3)."""

    symbols: list[str] = field(default_factory=list)
    catalog_path: str | Path = CATALOG_PATH
    presets_path: str | Path = PRESETS_PATH

    def add(self, symbol: str) -> None:
        """Add a company symbol to the basket; raises CompareLimitError on 7th."""
        clean = symbol.strip().upper()
        if clean in self.symbols:
            return
        if len(self.symbols) >= MAX_COMPARE:
            raise CompareLimitError()
        valid = {c.symbol for c in load_catalog(self.catalog_path)}
        if clean not in valid:
            raise ValidationError(f"Unknown symbol: {clean!r}")
        self.symbols.append(clean)

    def remove(self, symbol: str) -> None:
        """Remove a symbol from the comparison basket if present."""
        clean = symbol.strip().upper()
        self.symbols = [s for s in self.symbols if s != clean]

    def load_preset(self, preset_id: str) -> None:
        """Replace basket contents with a named preset from presets.json."""
        for preset in load_presets(self.presets_path, self.catalog_path):
            if preset.id == preset_id:
                self.symbols = list(preset.symbols[:MAX_COMPARE])
                return
        raise ValidationError(f"Unknown preset: {preset_id!r}")

    def clear(self) -> None:
        """Empty the comparison basket."""
        self.symbols.clear()
