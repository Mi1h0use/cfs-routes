"""
PDF text → structured route records.

The CFS Preferred IFR Routes PDF uses a tabular layout:
  AD  ALT  DIRECTION  AD  LIMITATIONS  PROC  ROUTE OF FLIGHT

Column meanings:
  AD (col1)    — departure/arrival airport ICAO
  ALT          — H, L, or H&L
  DIRECTION    — "ARR FR" or "DEP TO" or "OVFLT"
  AD (col2)    — cardinal direction (N/S/E/W/NE/NW/SE/SW) OR specific ICAO airport
  LIMITATIONS  — free text: altitude/speed/type constraints
  PROC         — "RNAV" or blank
  ROUTE        — route of flight string (may wrap to next line)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CARDINALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}

# Regex patterns
RE_FIR_HEADER = re.compile(r"^(CZ\w{2})\s+(\w[\w\s]*?)\s+FIR\s*$", re.IGNORECASE)
RE_TABLE_HEADER = re.compile(
    r"AD\s+ALT\s+DIRECTION\s+AD\s+LIMITATIONS\s+PROC\s+ROUTE\s+OF\s+FLIGHT",
    re.IGNORECASE,
)
RE_CONT_HEADER = re.compile(r"\(Cont'?d\)", re.IGNORECASE)
RE_FOOTER = re.compile(r"^CANADA FLIGHT SUPPLEMENT", re.IGNORECASE)
# Page numbers appear as "C119 PLANNING" or "PLANNING C119" optionally followed by "CFS" etc.
RE_PAGE_NUM = re.compile(r"^(C\d+\s+PLANNING|PLANNING\s+C\d+)(\s+.*)?$", re.IGNORECASE)
# Date lines like "07-AUG-2025" that appear in other CFS sections
RE_DATE_LINE = re.compile(r"^\d{2}-[A-Z]{3}-\d{4}\b")
# Section markers like "= FIXED RNAV ROUTES ENGLISH"
RE_SECTION_MARKER = re.compile(r"^=\s+")
# A valid route token: navaid/fix/airway name (2-5 uppercase letters/digits)
RE_ROUTE_TOKEN = re.compile(r"^[A-Z][A-Z0-9]{1,4}$")
# Airport ICAO: 3-4 uppercase chars starting with C or K (Canada/USA), or common patterns
RE_AIRPORT = re.compile(r"^([CK][A-Z]{2,3})\s+")
# Match the start of a data row: ICAO ALT ARR/DEP
RE_ROW_START = re.compile(
    r"^([CK][A-Z]{2,3})\s+(H&L|H|L)\s+(ARR FR|DEP TO|ARR|DEP|OVFLT)\s+(.*)"
)
RE_DIRECTION_LINE = re.compile(
    r"^(H&L|H|L)\s+(ARR FR|DEP TO|ARR|DEP|OVFLT)\s+(.*)"
)
# Overflights section
RE_OVFL_HEADER = re.compile(r"^OVERFLIGHTS?\s*$", re.IGNORECASE)


@dataclass
class RouteRecord:
    fir_code: str
    airport: str
    altitude: str
    direction_type: str    # ARR, DEP, OVFL
    direction: str         # cardinal or ""
    destination: str | None  # ICAO if specific airport
    limitations: str | None
    procedure: str | None
    route: str
    raw_line: str


@dataclass
class FirSection:
    fir_code: str
    fir_name: str
    routes: list[RouteRecord] = field(default_factory=list)


def _normalize_direction_type(raw: str) -> str:
    raw = raw.strip().upper()
    if raw in ("ARR FR", "ARR"):
        return "ARR"
    if raw in ("DEP TO", "DEP"):
        return "DEP"
    return "OVFL"


def _parse_direction_field(raw: str) -> tuple[str, str | None]:
    """
    Return (direction, destination) from the raw direction field.
    If it looks like an ICAO code → (direction="", destination=ICAO)
    Otherwise → (direction=raw.upper(), destination=None)
    """
    val = raw.strip().upper()
    if val in CARDINALS:
        return val, None
    # Looks like an ICAO airport code (4 chars, starts with C or K, or 3 chars)
    if re.match(r"^[CKY][A-Z]{2,3}$", val):
        return "", val
    # Some entries may be partial; try to extract
    m = re.match(r"^([CK][A-Z]{2,3})\b", val)
    if m:
        return "", m.group(1)
    return val, None


def _parse_row_tail(tail: str) -> tuple[str | None, str | None, str]:
    """
    Parse the portion after the direction field:
      [LIMITATIONS]  [PROC]  ROUTE
    Returns (limitations, procedure, route).
    The PROC column is either "RNAV" or empty; route follows.
    """
    # Try to split off RNAV proc token
    # Pattern: optional limitations text, then optional RNAV, then route
    # RNAV can appear as a standalone token between limitations and route
    tail = tail.strip()

    # Check if tail starts with RNAV then route
    m = re.match(r"^(RNAV)\s+(.*)", tail)
    if m:
        return None, "RNAV", m.group(2).strip()

    # Split by "RNAV" as procedure marker - it separates limitations from route
    # but only if followed by what looks like a route (uppercase words/codes)
    parts = re.split(r"\s+(RNAV)\s+", tail, maxsplit=1)
    if len(parts) == 3:
        limitations = parts[0].strip() or None
        procedure = parts[1]
        route = parts[2].strip()
        return limitations, procedure, route

    # No RNAV — split on what looks like the start of a route
    # Routes are space-separated navaid/fix names (uppercase, 2-5 chars)
    # Limitations are things like "JET", "NONJET", "A17000 & ABV", "N0320 & ABV"
    # Heuristic: find the first token that looks like a navaid or waypoint
    # after an optional limitations section
    # Try to split limitations from route by looking for the point where
    # the text stops looking like limitation keywords

    # Simplest reliable approach: limitations end at the first waypoint-looking token
    # that follows after any comma-separated limitation phrases.
    # We'll use a greedy split: limitations are anything before the ROUTE column.
    # Since we don't have column positions here, try common patterns.

    # Check for common limitation patterns at start
    lim_pattern = re.compile(
        r"^((?:JET|NONJET|SINGLE ENGINE|DH8D|"
        r"A\d{4,5}\s*&\s*(?:ABV|BLW)|"
        r"FL\d+\s*&\s*(?:ABV|BLW)|"
        r"F\d+\s*&\s*(?:ABV|BLW)|"
        r"MAX\s+F\d+|"
        r"N\d{4}\s*&\s*(?:ABV|BLW)|"
        r"CY\w+\d+\s+(?:CCW|CW)\s+\w+|"
        r"RNAV"
        r")(?:\s*[,&]\s*(?:JET|NONJET|SINGLE ENGINE|DH8D|"
        r"A\d{4,5}\s*&\s*(?:ABV|BLW)|"
        r"FL\d+\s*&\s*(?:ABV|BLW)|"
        r"F\d+\s*&\s*(?:ABV|BLW)|"
        r"MAX\s+F\d+|"
        r"N\d{4}\s*&\s*(?:ABV|BLW)|"
        r"CY\w+\d+\s+(?:CCW|CW)\s+\w+"
        r"))*)\s+(.*)",
        re.IGNORECASE,
    )
    m = lim_pattern.match(tail)
    if m:
        lim = m.group(1).strip() or None
        rest = m.group(len(m.groups())).strip()
        return lim, None, rest

    # No recognizable limitations prefix → entire tail is the route
    return None, None, tail.strip()


def _looks_like_route_continuation(stripped: str) -> bool:
    """True if every token looks like a navaid/fix/airway name."""
    if not stripped:
        return False
    tokens = stripped.split()
    return bool(tokens) and all(RE_ROUTE_TOKEN.match(t) for t in tokens)


def _is_skip_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if RE_FOOTER.match(stripped):
        return True
    if RE_PAGE_NUM.match(stripped):
        return True
    if RE_TABLE_HEADER.search(stripped):
        return True
    if RE_CONT_HEADER.search(stripped):
        return True
    if RE_DATE_LINE.match(stripped):
        return True
    if RE_SECTION_MARKER.match(stripped):
        return True
    return False


def parse_pdf_text(text: str) -> list[FirSection]:
    """
    Parse raw PDF text (pages joined by \\f) into FirSection objects.
    """
    lines = []
    for page in text.split("\f"):
        lines.extend(page.splitlines())

    sections: list[FirSection] = []
    current_fir: FirSection | None = None
    in_table = False
    current_airport: str | None = None  # last seen airport code (for continuation)
    current_record: dict | None = None  # accumulating a multi-line record

    in_overflights = False

    def flush_record():
        nonlocal current_record
        if current_record and current_fir is not None:
            r = current_record
            route_str = " ".join(r["route_parts"]).strip()
            if route_str:
                current_fir.routes.append(RouteRecord(
                    fir_code=r["fir_code"],
                    airport=r["airport"],
                    altitude=r["altitude"],
                    direction_type=r["direction_type"],
                    direction=r["direction"],
                    destination=r["destination"],
                    limitations=r["limitations"] or None,
                    procedure=r["procedure"] or None,
                    route=route_str,
                    raw_line=r["raw_line"],
                ))
        current_record = None

    for raw_line in lines:
        line = raw_line.rstrip()

        # --- FIR section header ---
        m = RE_FIR_HEADER.match(line.strip())
        if m and not line.startswith(" "):
            flush_record()
            fir_code = m.group(1).upper()
            # Extract FIR name — everything between the FIR code and "FIR"
            name_part = re.sub(r"^" + re.escape(fir_code) + r"\s+", "", line.strip(), flags=re.I)
            name_part = re.sub(r"\s+FIR\s*$", "", name_part, flags=re.I).strip()
            fir_name = f"{name_part} FIR"

            # Avoid duplicating if we see the same FIR code again (Cont'd pages)
            existing = next((s for s in sections if s.fir_code == fir_code), None)
            if existing:
                current_fir = existing
            else:
                current_fir = FirSection(fir_code=fir_code, fir_name=fir_name)
                sections.append(current_fir)
            in_table = False
            in_overflights = False
            current_record = None
            continue

        if current_fir is None:
            continue

        # --- Overflights section ---
        if RE_OVFL_HEADER.match(line.strip()):
            flush_record()
            in_overflights = True
            in_table = True
            continue

        # --- Table header ---
        if RE_TABLE_HEADER.search(line):
            flush_record()
            in_table = True
            continue

        # --- Lines to skip ---
        if _is_skip_line(line):
            continue

        # --- Before table: skip ---
        if not in_table:
            continue

        # --- In table ---
        stripped = line.strip()

        # Try to match a new data row
        m = RE_ROW_START.match(stripped)
        if m:
            flush_record()
            airport = m.group(1).upper()
            altitude = m.group(2).upper()
            dir_raw = m.group(3)
            rest = m.group(4).strip()

            # rest is: direction_field  [LIMITATIONS]  [PROC]  ROUTE
            # Split out the direction/destination field (first token)
            tokens = rest.split(None, 1)
            direction_field = tokens[0] if tokens else ""
            after_dir = tokens[1].strip() if len(tokens) > 1 else ""

            direction, destination = _parse_direction_field(direction_field)
            direction_type = _normalize_direction_type(dir_raw)
            if in_overflights and direction_type not in ("OVFL",):
                direction_type = "OVFL"

            limitations, procedure, route_start = _parse_row_tail(after_dir)
            current_airport = airport
            current_record = {
                "fir_code": current_fir.fir_code,
                "airport": airport,
                "altitude": altitude,
                "direction_type": direction_type,
                "direction": direction,
                "destination": destination,
                "limitations": limitations,
                "procedure": procedure,
                "route_parts": [route_start] if route_start else [],
                "raw_line": line,
            }
            continue

        # Continuation line (route wraps).
        if current_record is not None:
            if stripped and _looks_like_route_continuation(stripped):
                current_record["route_parts"].append(stripped)
                current_record["raw_line"] += "\n" + line
            else:
                # Unrecognised line — we've left the route entry; flush and discard.
                flush_record()
            continue

    flush_record()

    return sections
