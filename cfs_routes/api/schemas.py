from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class CycleInfo(BaseModel):
    ident: str
    effective: date
    expiry: date


class RouteItem(BaseModel):
    id: int
    direction_type: str          # ARR, DEP, OVFL
    altitude: str                # H, L, H&L
    direction: str               # cardinal or ""
    destination: Optional[str]   # specific ICAO or None
    limitations: Optional[str]
    procedure: Optional[str]
    route: str
    fir_code: str


class RoutesResponse(BaseModel):
    cycle: CycleInfo
    from_airport: str
    to_airport: Optional[str]
    routes: list[RouteItem]
    fallback: bool = False       # True when showing all DEP cardinal routes (no exact match)


class AirportInfo(BaseModel):
    icao: str
    name: str


class AirportsByFir(BaseModel):
    firs: dict[str, list[AirportInfo]]


class CycleRecord(BaseModel):
    id: int
    ident: str
    effective: date
    expiry: date
    status: str
    fetched_at: Optional[datetime]
    parsed_at: Optional[datetime]
    pdf_url: str
    error_message: Optional[str]


