from typing import Any

from fastapi import FastAPI

from app.core.exceptions import BusinessException, business_exception_handler
from app.core.middleware import RequestIdMiddleware, configure_logging
from app.core.responses import success_response


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Enterprise Project Management Archive System",
        version="0.1.0",
        description="API skeleton for the project management archive system.",
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(BusinessException, business_exception_handler)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, Any]:
        return success_response(
            {
                "status": "ok",
                "service": "backend",
            }
        )

    return app


app = create_app()
