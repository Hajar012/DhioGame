from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
    )

    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(health.router, prefix="/api")

    @application.get("/", tags=["root"])
    def root() -> dict[str, str]:
        return {"message": f"{settings.app_name} is running"}

    return application


app = create_app()
