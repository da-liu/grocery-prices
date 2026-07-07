from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from extract_server.exception_handlers import register_exception_handlers  # noqa: E402
from extract_server.middleware import RequestLoggingMiddleware  # noqa: E402
from extract_server.routes import auth, health, media, photos, products, settings, stores  # noqa: E402
from extract_server.users_db import close_all_connections, init_db  # noqa: E402
from extract_server.grocery_extract.logging_config import configure_logging  # noqa: E402

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
            "https://g.daliu.ca,http://localhost:41873",
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
        settings.router,
        products.router,
        stores.router,
        media.router,
        photos.router,
    ):
        app.include_router(router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8765, reload=False)
