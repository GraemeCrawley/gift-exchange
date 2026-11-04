from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def url(request: Request, path: str) -> str:
    """Absolute path including the app's prefix (e.g. /gift-exchange)."""
    return request.scope.get("root_path", "") + path


def full_url(request: Request, path: str) -> str:
    """Full URL a person can copy and text to someone."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{proto}://{host}{url(request, path)}"


def render(request: Request, name: str, ctx: dict | None = None, status: int = 200):
    context = {"url": lambda p: url(request, p), "full_url": lambda p: full_url(request, p)}
    context.update(ctx or {})
    return templates.TemplateResponse(request, name, context, status_code=status)


def not_found(request: Request):
    return render(request, "not_found.html", {}, status=404)


def get_conn(request: Request):
    """FastAPI dependency: one SQLite connection per request."""
    from app import db

    conn = db.connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


def redirect(request: Request, path: str):
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url(request, path), status_code=303)
