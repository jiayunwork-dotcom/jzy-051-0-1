"""FastAPI application entry point.

On startup the ORM metadata is created (idempotent ``CREATE TABLE IF NOT
EXISTS``); for real production migrations a tool like Alembic would take
over, but the schema is small enough that metadata creation keeps the demo
deterministic.

The built React bundle (``frontend/dist``) is served as static files when
present so a single backend container can host the whole app behind the
nginx proxy in docker-compose.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .persistence.db import init_models

STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")


app = FastAPI(title="LaTeX 数学公式编辑器", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def _init_db() -> None:
    await init_models()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# Static frontend (production container).  API routes take precedence; the
# catch-all below serves the SPA for any non-/api path.
if os.path.isdir(STATIC_DIR):
    app.mount("/assets",
              StaticFiles(directory=os.path.join(STATIC_DIR, "assets")),
              name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path == "health":
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        index = os.path.join(STATIC_DIR, "index.html")
        return FileResponse(index)
