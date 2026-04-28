"""FastAPI application factory."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import db
from axocare_api.routes import router
from axocare_api.settings import DEFAULT_CONFIG_PATH, ApiSettings


def create_app(config_path: str | Path | None = None) -> FastAPI:
    """Create and configure the Axocare API application."""
    resolved_config_path = config_path or os.getenv(
        "AXOCARE_CONFIG", DEFAULT_CONFIG_PATH
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings = ApiSettings.from_toml(resolved_config_path)
        db.migrate(settings.db_path)
        app.state.settings = settings
        yield

    app = FastAPI(
        title="Axocare API",
        summary="JSON API for Axocare temperature dashboard data.",
        version="1.0.0",
        lifespan=lifespan,
    )
    _configure_cors(app)
    app.include_router(router)
    return app


def _configure_cors(app: FastAPI) -> None:
    """Enable browser frontend access."""
    origins = [
        origin.strip()
        for origin in os.getenv("AXOCARE_CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )


app = create_app()
