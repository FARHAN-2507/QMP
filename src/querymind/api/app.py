"""FastAPI application for QueryMind (smoke dashboard + APIs)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from querymind.api.smoke_routes import router as smoke_router

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    """Build the FastAPI app. Isolated from the agent runtime."""
    app = FastAPI(
        title="QueryMind API",
        description="ApiSmokeTesting dashboard and HTTP APIs",
        version="0.1.0",
    )
    app.include_router(smoke_router, prefix="/api/smoke", tags=["smoke"])

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "querymind"}

    dashboard = STATIC_DIR / "smoke-dashboard.html"
    if dashboard.is_file():
        @app.get("/")
        def dashboard_page() -> FileResponse:
            return FileResponse(dashboard)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


app = create_app()
