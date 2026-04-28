"""FastAPI entrypoint for Axocare dashboard data."""

from axocare_api.app import app, create_app

__all__ = ["app", "create_app"]
