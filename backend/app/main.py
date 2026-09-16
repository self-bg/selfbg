from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .matting import warmup
from .routes.remove import router as remove_router
from .routes.v1_compat import router as v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    warmup()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="selfbg",
        description="Self-hosted background removal API. A drop-in replacement for remove.bg.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "model": settings.model}

    app.include_router(remove_router)
    app.include_router(v1_router)
    return app


app = create_app()
