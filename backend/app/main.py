from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health, rooms, ws
from app.core.config import get_settings
from app.core.errors import AppError


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.2.0",
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
    application.include_router(ws.router, prefix="/api")

    @application.get("/", tags=["root"])
    def root() -> dict[str, str]:
        return {"message": f"{settings.app_name} is running"}

    return application


app = create_app()
