"""FastAPI entry point for SANA FORGE."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.product_api import create_product_router
from models.provider import ModelProvider, create_provider
from services.sana_ai import SanaAIService
from storage.database import Database

STATIC_DIR = Path(__file__).parent / "static"
INDEX = STATIC_DIR / "index.html"
DEFAULT_DB = Path(__file__).parent.parent / "data" / "sana_forge.db"


def create_app(
    provider: ModelProvider | None = None,
    database: Database | None = None,
) -> FastAPI:
    app = FastAPI(title="SANA FORGE", version="3.0")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    selected_provider = provider or create_provider()
    product_database = database or Database(os.getenv("SANA_DB_PATH", DEFAULT_DB))
    app.include_router(
        create_product_router(product_database, SanaAIService(selected_provider))
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(INDEX)

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_routes(full_path: str) -> FileResponse:
        """Serve the History API frontend routes without masking missing APIs."""
        if full_path.startswith("api/"):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="API route not found")
        return FileResponse(INDEX)

    return app


app = create_app()
