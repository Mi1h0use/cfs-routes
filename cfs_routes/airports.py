"""
Airport data loader. Reads airports.csv at startup.

CSV columns: icao, city, country, state, name, type, longitude, latitude, elevation
"""
from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass

from cfs_routes.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Airport:
    icao: str
    name: str
    city: str
    country: str
    state: str
    airport_type: str
    longitude: float | None
    latitude: float | None
    elevation: int | None


_airports: dict[str, Airport] = {}


def load_airports() -> None:
    global _airports
    path = settings.airports_csv_path
    if not os.path.exists(path):
        logger.warning("airports.csv not found at %s — airport names unavailable", path)
        return

    loaded = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            icao = (row.get("icao") or "").strip().upper()
            if not icao:
                continue
            try:
                lon = float(row["longitude"]) if row.get("longitude") else None
                lat = float(row["latitude"]) if row.get("latitude") else None
                elev_raw = row.get("elevation", "")
                elev = int(elev_raw) if elev_raw and elev_raw.isdigit() else None
            except (ValueError, KeyError):
                lon = lat = elev = None

            _airports[icao] = Airport(
                icao=icao,
                name=(row.get("name") or "").strip(),
                city=(row.get("city") or "").strip(),
                country=(row.get("country") or "").strip(),
                state=(row.get("state") or "").strip(),
                airport_type=(row.get("type") or "").strip(),
                longitude=lon,
                latitude=lat,
                elevation=elev,
            )
            loaded += 1

    logger.info("Loaded %d airports from %s", loaded, path)
    _airports = _airports


def get_airport(icao: str) -> Airport | None:
    return _airports.get(icao.upper())


def get_airport_name(icao: str) -> str:
    ap = get_airport(icao)
    if ap:
        return ap.name or icao
    return icao


def all_airports() -> dict[str, Airport]:
    return _airports
