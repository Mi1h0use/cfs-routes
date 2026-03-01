from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"


@router.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_TEMPLATE_PATH.read_text(encoding="utf-8"))
