from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from extract_server.api.routes import auth, health, match, media, photos, products, stores  # noqa: E402
from extract_server.core.exception_handlers import register_exception_handlers  # noqa: E402
from extract_server.core.logging import configure_logging  # noqa: E402
from extract_server.core.middleware import RequestLoggingMiddleware  # noqa: E402
from extract_server.db import close_all_connections, init_db  # noqa: E402

configure_logging()
init_db()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    close_all_connections()


def create_app() -> FastAPI:
    app = FastAPI(title="Grocery Price API", version="3.0.0", lifespan=lifespan)

    cors_origins = [
        origin.strip()
        for origin in os.environ.get(
            "GROCERY_CORS_ORIGINS",
            "https://g.daliu.ca,http://localhost:41873,http://localhost:41875",
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)

    for router in (
        health.router,
        auth.router,
        products.router,
        stores.router,
        media.router,
        photos.router,
        match.router,
    ):
        app.include_router(router)

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("extract_server.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()
