import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import game, health, reveal, rooms, ws
from app.core.config import get_settings
from app.core.errors import AppError
from app.services import expiration

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
FRONTEND_INDEX = FRONTEND_DIR / "index.html"


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        cleanup_task = asyncio.create_task(
            expiration.cleanup_loop(settings.room_cleanup_interval_seconds)
        )
        try:
            yield
        finally:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.3.0",
        lifespan=lifespan,
    )

    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @application.exception_handler(AppError)
    async def handle_app_error(
        request: Request, exc: AppError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    application.include_router(health.router, prefix="/api")
    application.include_router(rooms.router, prefix="/api")
    application.include_router(game.router, prefix="/api")
    application.include_router(reveal.router, prefix="/api")
    application.include_router(ws.router, prefix="/api")

    application.mount(
        "/css",
        StaticFiles(directory=FRONTEND_DIR / "css"),
        name="frontend-css",
    )
    application.mount(
        "/js",
        StaticFiles(directory=FRONTEND_DIR / "js"),
        name="frontend-js",
    )

    @application.get("/", include_in_schema=False)
    def root() -> FileResponse:
        return FileResponse(FRONTEND_INDEX)

    return application


app = create_app()
