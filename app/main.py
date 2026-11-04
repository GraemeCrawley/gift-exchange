import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import web
from app.config import load_settings
from app.security import RedactTokensFilter, security_headers


def create_app(db_path: str | None = None, root_path: str | None = None) -> FastAPI:
    settings = load_settings()
    app = FastAPI(
        root_path=settings.root_path if root_path is None else root_path,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.db_path = db_path or settings.db_path

    app.middleware("http")(security_headers)
    logging.getLogger("uvicorn.access").addFilter(RedactTokensFilter())

    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return web.not_found(request)
        return web.render(request, "error.html", {"message": exc.detail}, status=exc.status_code)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    Instrumentator().instrument(app).expose(app, include_in_schema=False)
    return app


app = create_app()
