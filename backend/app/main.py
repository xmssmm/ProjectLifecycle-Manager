from typing import Any

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="Enterprise Project Management Archive System",
        version="0.1.0",
        description="API skeleton for the project management archive system.",
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, Any]:
        return {
            "code": 0,
            "message": "success",
            "data": {
                "status": "ok",
                "service": "backend",
            },
        }

    return app


app = create_app()
