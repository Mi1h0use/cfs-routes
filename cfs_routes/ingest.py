"""
Ingest pipeline: fetch PDF → parse → store in DB.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cfs_routes.airac import CfsCycle
from cfs_routes.fetcher import extract_text_from_pdf, fetch_pdf, pdf_url_for_date
from cfs_routes.models import AiracCycle, CycleStatus, MandatoryRoute
from cfs_routes.parser import parse_pdf_text

logger = logging.getLogger(__name__)


async def ensure_cycle(db: AsyncSession, cfs: CfsCycle) -> AiracCycle:
    """
    Ensure the given CFS cycle exists in the DB and is ingested.
    Creates the record if absent, then fetches and parses if not yet done.
    """
    result = await db.execute(
        select(AiracCycle).where(AiracCycle.cycle_ident == cfs.ident)
    )
    cycle = result.scalar_one_or_none()

    if cycle is None:
        url = pdf_url_for_date(cfs.effective)
        cycle = AiracCycle(
            cycle_ident=cfs.ident,
            effective_date=cfs.effective,
            expiry_date=cfs.expiry,
            pdf_url=url,
            status=CycleStatus.pending,
        )
        db.add(cycle)
        await db.commit()
        await db.refresh(cycle)

    if cycle.status not in (CycleStatus.parsed,):
        await fetch_and_parse_cycle(db, cycle)

    return cycle


async def fetch_and_parse_cycle(db: AsyncSession, cycle: AiracCycle) -> None:
    """Fetch the PDF and parse it into the DB, updating cycle status."""
    try:
        pdf_bytes = await fetch_pdf(cycle.effective_date)
        cycle.fetched_at = datetime.now(timezone.utc)
        cycle.status = CycleStatus.fetched
        await db.commit()
    except Exception as exc:
        logger.error("Failed to fetch PDF for cycle %s: %s", cycle.cycle_ident, exc)
        cycle.status = CycleStatus.failed
        cycle.error_message = str(exc)
        await db.commit()
        return

    try:
        text = await extract_text_from_pdf(pdf_bytes)
        sections = parse_pdf_text(text)
        await _store_sections(db, cycle, sections)
        cycle.parsed_at = datetime.now(timezone.utc)
        cycle.status = CycleStatus.parsed
        cycle.error_message = None
        await db.commit()
        total_routes = sum(len(s.routes) for s in sections)
        logger.info("Cycle %s: parsed %d routes", cycle.cycle_ident, total_routes)
    except Exception as exc:
        logger.error("Failed to parse PDF for cycle %s: %s", cycle.cycle_ident, exc)
        cycle.status = CycleStatus.failed
        cycle.error_message = str(exc)
        await db.commit()


async def _store_sections(db: AsyncSession, cycle: AiracCycle, sections) -> None:
    """Persist parsed routes, replacing any existing data for this cycle."""
    from sqlalchemy import delete

    await db.execute(
        delete(MandatoryRoute).where(MandatoryRoute.cycle_id == cycle.id)
    )
    await db.commit()

    for sec in sections:
        for r in sec.routes:
            route_rec = MandatoryRoute(
                cycle_id=cycle.id,
                fir_code=r.fir_code,
                airport=r.airport,
                altitude=r.altitude,
                direction_type=r.direction_type,
                direction=r.direction or "",
                destination=r.destination,
                limitations=r.limitations,
                procedure=r.procedure,
                route=r.route,
                raw_line=r.raw_line,
            )
            db.add(route_rec)

    await db.commit()
