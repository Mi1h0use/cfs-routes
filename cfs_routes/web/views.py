from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

_TEMPLATE = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")


def _detect_lang(accept_language: str) -> str:
    first = accept_language.split(",")[0].split(";")[0].strip().lower()
    return "fr" if first.startswith("fr") else "en"


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    lang = _detect_lang(request.headers.get("accept-language", ""))
    return HTMLResponse(_TEMPLATE.replace('lang="en"', f'lang="{lang}"', 1))
