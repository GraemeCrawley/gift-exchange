import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import db, routes_admin, routes_home, routes_join, routes_person, web
from app.config import load_settings
from app.security import RedactTokensFilter, security_headers


def create_app(db_path: str | None = None, root_path: str | None = None) -> FastAPI:
    settings = load_settings()
    # Traefik strips the prefix before requests arrive, so the app only uses it to
    # build links. (Passing it to FastAPI's root_path breaks static file paths.)
    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.db_path = db_path or settings.db_path
    app.state.prefix = (settings.root_path if root_path is None else root_path).rstrip("/")
    conn = db.connect(app.state.db_path)
    db.init_schema(conn)
    conn.close()

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

    app.include_router(routes_home.router)
    app.include_router(routes_admin.router)
    app.include_router(routes_join.router)
    app.include_router(routes_person.router)

    Instrumentator().instrument(app).expose(app, include_in_schema=False)
    return app


app = create_app()
