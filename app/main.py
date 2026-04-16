from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import agent_mode, auth, detect, guardians, knowledge, media, model_detect, users
from app.config.settings import settings
from app.db.session import Base, engine


def _ensure_guardians_schema_compat() -> None:
    """Patch legacy SQLite guardians table columns to current ORM shape."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(guardians)")).fetchall()
        if not rows:
            return
        cols = {r[1] for r in rows}
        if "monitor_id" not in cols:
            conn.execute(text("ALTER TABLE guardians ADD COLUMN monitor_id INTEGER"))
        if "ward_id" not in cols:
            conn.execute(text("ALTER TABLE guardians ADD COLUMN ward_id INTEGER"))
        if "relationship" not in cols:
            conn.execute(text("ALTER TABLE guardians ADD COLUMN relationship VARCHAR(64)"))
        if "ward_user_id" in cols:
            conn.execute(text("UPDATE guardians SET ward_id = ward_user_id WHERE ward_id IS NULL"))
        if "relation" in cols:
            conn.execute(text("UPDATE guardians SET relationship = relation WHERE relationship IS NULL"))


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    frontend_dir = Path(__file__).resolve().parents[1] / "anti_frontend" / "public"
    frontend_src_dir = Path(__file__).resolve().parents[1] / "anti_frontend" / "src"

    @app.get("/")
    def root():
        return RedirectResponse(url="/ui/Login.html")

    @app.get("/health")
    def health():
        return {"ok": True}

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(guardians.router)
    app.include_router(detect.router)
    app.include_router(agent_mode.router)
    app.include_router(model_detect.router)
    app.include_router(media.router)
    app.include_router(knowledge.router)
    if frontend_src_dir.exists():
        app.mount("/ui/src", StaticFiles(directory=str(frontend_src_dir), html=False), name="ui-src")
    if frontend_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(frontend_dir), html=True), name="ui")
    return app


_ensure_guardians_schema_compat()
Base.metadata.create_all(bind=engine)
app = create_app()
