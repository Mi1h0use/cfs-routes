"""
AIRAC cycle calculator for CFS (Canada Flight Supplement) 56-day cycles.

CFS publishes on odd-numbered 28-day AIRAC cycles from the ICAO epoch.
Known 2026 effective dates: 2026-01-22, 2026-03-19, 2026-05-14, 2026-07-09,
                              2026-09-03, 2026-10-29
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# ICAO AIRAC epoch
EPOCH = date(1901, 1, 10)
CYCLE_DAYS = 28


@dataclass(frozen=True)
class CfsCycle:
    ident: str          # e.g. "2601"
    effective: date
    expiry: date        # effective + 55 days


def _cycle_number_for_date(d: date) -> int:
    """Return the 28-day cycle number (0-based from epoch) containing date d."""
    return (d - EPOCH).days // CYCLE_DAYS


def _effective_for_cycle(n: int) -> date:
    return EPOCH + timedelta(days=n * CYCLE_DAYS)


def _is_cfs_cycle(n: int) -> bool:
    """CFS cycles are the odd-numbered 28-day cycles (0-based: 1, 3, 5, ...)."""
    return n % 2 == 1


def _cycle_ident(effective: date) -> str:
    """
    Return cycle ident string YYNN where:
      YY = last 2 digits of the year the cycle starts
      NN = ordinal of that 28-day AIRAC cycle within the year (1-based, up to 13)

    The first AIRAC cycle of a year is the one whose effective date falls on or after
    Jan 1 of that year.  We compute NN by counting how many 28-day cycles have
    started in that calendar year before (and including) this one.
    """
    year = effective.year
    jan1 = date(year, 1, 1)
    n_this = _cycle_number_for_date(effective)

    # Find the first 28-day cycle that starts on/after Jan 1 of effective's year.
    n_jan1 = _cycle_number_for_date(jan1)
    if _effective_for_cycle(n_jan1) < jan1:
        n_jan1 += 1

    ordinal = n_this - n_jan1 + 1  # 1-based
    yy = year % 100
    return f"{yy:02d}{ordinal:02d}"


def _build_cycle(n: int) -> CfsCycle:
    eff = _effective_for_cycle(n)
    exp = eff + timedelta(days=55)
    return CfsCycle(ident=_cycle_ident(eff), effective=eff, expiry=exp)


def current_cfs_cycle(today: date | None = None) -> CfsCycle:
    """Return the CFS cycle currently in effect."""
    if today is None:
        today = date.today()
    n = _cycle_number_for_date(today)
    # Round down to nearest odd cycle number
    if not _is_cfs_cycle(n):
        n -= 1
    return _build_cycle(n)


def next_cfs_cycle(today: date | None = None) -> CfsCycle:
    """Return the next upcoming CFS cycle."""
    cur = current_cfs_cycle(today)
    n = _cycle_number_for_date(cur.effective)
    return _build_cycle(n + 2)


def cfs_cycle_for_date(d: date) -> CfsCycle:
    """Return the CFS cycle in effect on date d."""
    return current_cfs_cycle(d)


def all_cfs_cycles(start_year: int, end_year: int) -> list[CfsCycle]:
    """Return all CFS cycles whose effective date falls within [start_year, end_year]."""
    results: list[CfsCycle] = []
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)

    n = _cycle_number_for_date(start)
    # Align to first odd cycle at or after start
    if not _is_cfs_cycle(n):
        n += 1

    while True:
        eff = _effective_for_cycle(n)
        if eff > end:
            break
        if eff >= start:
            results.append(_build_cycle(n))
        n += 2

    return results
