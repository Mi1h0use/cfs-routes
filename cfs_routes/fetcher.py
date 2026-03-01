"""
PDF discovery and download for CFS Preferred IFR Routes.

URL pattern: {PDF_BASE_URL}CFSPREFERREDIFRROUTES_{MM-DD-YYYY}.PDF
"""
from __future__ import annotations

import logging
from datetime import date

import httpx

from cfs_routes.config import settings

logger = logging.getLogger(__name__)


def pdf_url_for_date(effective: date) -> str | None:
    if not settings.pdf_base_url:
        return None
    date_str = effective.strftime("%m-%d-%Y")
    base = settings.pdf_base_url.rstrip("/")
    return f"{base}/CFSPREFERREDIFRROUTES_{date_str}.PDF"


async def fetch_pdf(effective: date, timeout: float = 60.0) -> bytes:
    """
    Download the CFS PDF for the given effective date.
    Raises httpx.HTTPError on network/HTTP failure.
    """
    url = pdf_url_for_date(effective)
    logger.info("Fetching PDF from %s", url)

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()

    logger.info("Fetched %d bytes from %s", len(response.content), url)
    return response.content


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract raw text from PDF bytes using pdfplumber.
    Returns all pages concatenated with form-feed separators.
    """
    import io

    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                pages.append(text)

    return "\f".join(pages)
