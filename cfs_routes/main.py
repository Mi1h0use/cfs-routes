from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from cfs_routes import airports as airport_store
from cfs_routes.api.routes import router as api_router
from cfs_routes.config import settings
from cfs_routes.database import engine
from cfs_routes.models import Base
from cfs_routes.scheduler import start_scheduler, stop_scheduler
from cfs_routes.web.views import router as web_router

_STATIC_DIR = Path(__file__).parent / "web" / "static"

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    airport_store.load_airports()

    await start_scheduler()

    yield

    # Shutdown
    await stop_scheduler()


app = FastAPI(
    title="CFS Preferred IFR Routes",
    description="CFS Mandatory IFR Routes for VATSIM controllers",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
app.include_router(api_router, prefix="/api")
app.include_router(web_router)
