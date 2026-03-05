"""
REST API endpoints.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cfs_routes import airports as airport_store
from cfs_routes.airac import current_cfs_cycle
from cfs_routes.api.schemas import (
    AirportInfo,
    AirportsByFir,
    CycleInfo,
    CycleRecord,
    RouteItem,
    RoutesResponse,
)
from cfs_routes.database import get_db
from cfs_routes.models import AiracCycle, CycleStatus, MandatoryRoute

router = APIRouter()
logger = logging.getLogger(__name__)

_CARDINAL_DEGREES: dict[str, float] = {
    "N": 0.0, "NE": 45.0, "E": 90.0, "SE": 135.0,
    "S": 180.0, "SW": 225.0, "W": 270.0, "NW": 315.0,
}


def _initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return initial great-circle bearing in degrees [0, 360)."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _nearest_cardinal(bearing: float, available: set[str]) -> str | None:
    """Return the cardinal in *available* whose angle is closest to *bearing*."""
    best: str | None = None
    best_diff = 361.0
    for card, angle in _CARDINAL_DEGREES.items():
        if card not in available:
            continue
        diff = abs((bearing - angle + 180) % 360 - 180)
        if diff < best_diff:
            best_diff = diff
            best = card
    return best


async def _get_cycle(
    db: AsyncSession,
    cycle_ident: str | None,
) -> AiracCycle | None:
    if cycle_ident:
        result = await db.execute(
            select(AiracCycle).where(AiracCycle.cycle_ident == cycle_ident)
        )
        return result.scalar_one_or_none()
    # Use current active cycle (parsed, effective ≤ today ≤ expiry)
    today = date.today()
    result = await db.execute(
        select(AiracCycle)
        .where(
            AiracCycle.status == CycleStatus.parsed,
            AiracCycle.effective_date <= today,
            AiracCycle.expiry_date >= today,
        )
        .order_by(AiracCycle.effective_date.desc())
        .limit(1)
    )
    cycle = result.scalar_one_or_none()
    if cycle is None:
        # Fall back to most recent parsed cycle
        result = await db.execute(
            select(AiracCycle)
            .where(AiracCycle.status == CycleStatus.parsed)
            .order_by(AiracCycle.effective_date.desc())
            .limit(1)
        )
        cycle = result.scalar_one_or_none()
    return cycle


def _route_to_item(r: MandatoryRoute) -> RouteItem:
    return RouteItem(
        id=r.id,
        direction_type=r.direction_type,
        altitude=r.altitude,
        direction=r.direction,
        destination=r.destination,
        limitations=r.limitations,
        procedure=r.procedure,
        route=r.route,
        fir_code=r.fir_code,
    )


def _cycle_info(c: AiracCycle) -> CycleInfo:
    return CycleInfo(ident=c.cycle_ident, effective=c.effective_date, expiry=c.expiry_date)


@router.get("/routes", response_model=RoutesResponse)
async def get_routes(
    from_icao: Optional[str] = Query(None, alias="from"),
    to_icao: Optional[str] = Query(None, alias="to"),
    airport: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    cycle: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    cyc = await _get_cycle(db, cycle)
    if cyc is None:
        raise HTTPException(status_code=503, detail="No parsed cycle available")

    cycle_info = _cycle_info(cyc)

    # Normalise
    from_icao = from_icao.upper() if from_icao else None
    to_icao = to_icao.upper() if to_icao else None
    airport_icao = airport.upper() if airport else None
    direction_upper = direction.upper() if direction else None

    # --- All routes for a single airport ---
    if airport_icao and not from_icao:
        result = await db.execute(
            select(MandatoryRoute).where(
                MandatoryRoute.cycle_id == cyc.id,
                MandatoryRoute.airport == airport_icao,
            )
        )
        routes = result.scalars().all()
        return RoutesResponse(
            cycle=cycle_info,
            from_airport=airport_icao,
            to_airport=None,
            routes=[_route_to_item(r) for r in routes],
        )

    # --- DEP routes from airport in a cardinal direction ---
    if from_icao and direction_upper and not to_icao:
        result = await db.execute(
            select(MandatoryRoute).where(
                MandatoryRoute.cycle_id == cyc.id,
                MandatoryRoute.airport == from_icao,
                MandatoryRoute.direction_type == "DEP",
                MandatoryRoute.direction == direction_upper,
            )
        )
        routes = result.scalars().all()
        return RoutesResponse(
            cycle=cycle_info,
            from_airport=from_icao,
            to_airport=None,
            routes=[_route_to_item(r) for r in routes],
        )

    # --- Routes between two airports ---
    if from_icao and to_icao:
        routes = await _routes_between(db, cyc.id, from_icao, to_icao)
        fallback = False

        preferred_direction: str | None = None

        if not routes:
            # Amendment: fall back to all DEP TO {cardinal} routes from from_icao
            result = await db.execute(
                select(MandatoryRoute).where(
                    MandatoryRoute.cycle_id == cyc.id,
                    MandatoryRoute.airport == from_icao,
                    MandatoryRoute.direction_type == "DEP",
                    MandatoryRoute.destination.is_(None),  # cardinal routes only
                )
            )
            routes = result.scalars().all()
            fallback = True

            from_ap = airport_store.get_airport(from_icao)
            to_ap = airport_store.get_airport(to_icao)
            if (
                from_ap and to_ap
                and from_ap.latitude is not None and from_ap.longitude is not None
                and to_ap.latitude is not None and to_ap.longitude is not None
            ):
                bearing = _initial_bearing(
                    from_ap.latitude, from_ap.longitude,
                    to_ap.latitude, to_ap.longitude,
                )
                available_dirs = {r.direction for r in routes if r.direction}
                preferred_direction = _nearest_cardinal(bearing, available_dirs)

        return RoutesResponse(
            cycle=cycle_info,
            from_airport=from_icao,
            to_airport=to_icao,
            to_airport_name=airport_store.get_airport_name(to_icao),
            routes=[_route_to_item(r) for r in routes],
            fallback=fallback,
            preferred_direction=preferred_direction,
        )

    raise HTTPException(
        status_code=400,
        detail="Provide ?from=ICAO&to=ICAO, ?airport=ICAO, or ?from=ICAO&direction=CARDINAL",
    )


async def _routes_between(
    db: AsyncSession, cycle_id: int, from_icao: str, to_icao: str
) -> list[MandatoryRoute]:
    """Return DEP routes from from_icao to to_icao, plus ARR routes at from_icao from to_icao."""
    result = await db.execute(
        select(MandatoryRoute).where(
            MandatoryRoute.cycle_id == cycle_id,
            MandatoryRoute.airport == from_icao,
            MandatoryRoute.direction_type == "DEP",
            MandatoryRoute.destination == to_icao,
        )
    )
    dep_routes = result.scalars().all()

    result = await db.execute(
        select(MandatoryRoute).where(
            MandatoryRoute.cycle_id == cycle_id,
            MandatoryRoute.airport == from_icao,
            MandatoryRoute.direction_type == "ARR",
            MandatoryRoute.destination == to_icao,
        )
    )
    arr_routes = result.scalars().all()

    return list(dep_routes) + list(arr_routes)


@router.get("/airports", response_model=AirportsByFir)
async def get_airports(
    cycle: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    cyc = await _get_cycle(db, cycle)
    if cyc is None:
        raise HTTPException(status_code=503, detail="No parsed cycle available")

    result = await db.execute(
        select(MandatoryRoute.fir_code, MandatoryRoute.airport)
        .where(MandatoryRoute.cycle_id == cyc.id)
        .distinct()
        .order_by(MandatoryRoute.fir_code, MandatoryRoute.airport)
    )
    rows = result.all()

    firs: dict[str, list[AirportInfo]] = {}
    seen: set[tuple[str, str]] = set()
    for fir_code, icao in rows:
        key = (fir_code, icao)
        if key in seen:
            continue
        seen.add(key)
        name = airport_store.get_airport_name(icao) or icao
        firs.setdefault(fir_code, []).append(AirportInfo(icao=icao, name=name))

    return AirportsByFir(firs=firs)


@router.get("/cycles", response_model=list[CycleRecord])
async def get_cycles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AiracCycle).order_by(AiracCycle.effective_date.desc())
    )
    cycles = result.scalars().all()
    return [
        CycleRecord(
            id=c.id,
            ident=c.cycle_ident,
            effective=c.effective_date,
            expiry=c.expiry_date,
            status=c.status.value,
            fetched_at=c.fetched_at,
            parsed_at=c.parsed_at,
            pdf_url=c.pdf_url,
            error_message=c.error_message,
        )
        for c in cycles
    ]

