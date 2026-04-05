from __future__ import annotations

from fastapi import FastAPI

from app.api import auth, detect, guardians, knowledge, media, users
from app.config.settings import settings
from app.db.session import Base, engine


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    @app.get("/")
    def root():
        return {"ok": True, "docs": "/docs", "health": "/health"}

    @app.get("/health")
    def health():
        return {"ok": True}

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(guardians.router)
    app.include_router(detect.router)
    app.include_router(media.router)
    app.include_router(knowledge.router)
    return app


Base.metadata.create_all(bind=engine)
app = create_app()
