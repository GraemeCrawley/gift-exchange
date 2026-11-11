from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def nice_date(iso: str | None) -> str:
    """2026-12-24 -> Thu, Dec 24, 2026"""
    from datetime import date

    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return f"{d:%a, %b} {d.day}, {d.year}"


templates.env.filters["nice_date"] = nice_date


def countdown(iso: str | None, today=None) -> str:
    """'54 days to go', 'Tomorrow!', 'Today!', or '' once it's past. Uses the server's local date (TZ)."""
    from datetime import date

    if not iso:
        return ""
    days = (date.fromisoformat(iso) - (today or date.today())).days
    if days < 0:
        return ""
    return {0: "Today!", 1: "Tomorrow!"}.get(days, f"{days} days to go")


templates.env.filters["countdown"] = countdown


from app.repo import money  # noqa: E402  (shared with saving)

templates.env.filters["money"] = money


def _static_version() -> str:
    """Short hash of the CSS, JS and icons, added to their links so phones fetch new copies after a deploy."""
    import hashlib

    static = Path(__file__).parent / "static"
    h = hashlib.sha256()
    for f in [static / "app.css", static / "app.js", *sorted((static / "icons").glob("*.png"))]:
        h.update(f.read_bytes())
    return h.hexdigest()[:10]


templates.env.globals["static_version"] = _static_version()


def url(request: Request, path: str) -> str:
    """Absolute path including the app's prefix (e.g. /gift-exchange)."""
    return request.app.state.prefix + path


def full_url(request: Request, path: str) -> str:
    """Full URL a person can copy and text to someone."""
    base = getattr(request.app.state, "public_base_url", "")
    if base:
        return base + path
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{proto}://{host}{url(request, path)}"


def render(request: Request, name: str, ctx: dict | None = None, status: int = 200):
    from app.themes import THEMES, icon_path, theme

    context = {"url": lambda p: url(request, p), "full_url": lambda p: full_url(request, p)}
    context.update(ctx or {})
    # Each exchange has its own colour; the organizer's Home Screen icon has a star badge.
    ex = context.get("ex")
    color = getattr(ex, "color", None) or "green"
    role = "organizer" if request.scope["path"].startswith("/a/") else "member"
    context.update(color=color, themes=THEMES, theme_primary=theme(color)["primary"],
                   touch_icon=icon_path(color, role, 180), fav_icon=icon_path(color, role, 192))
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


def manifest(request: Request, name: str, path: str, color: str = "green", role: str = "member"):
    """Web app manifest so 'Add to Home Screen' reopens this exact page."""
    from fastapi.responses import JSONResponse

    from app.themes import icon_path, theme

    start = url(request, path)
    return JSONResponse(
        {
            "name": name,
            "short_name": name[:12],
            "start_url": start,
            "scope": start,
            "display": "standalone",
            "background_color": "#F7F4EE",
            "theme_color": theme(color)["primary"],
            "icons": [
                {"src": url(request, icon_path(color, role, n)) + "?v=" + templates.env.globals["static_version"], "sizes": f"{n}x{n}", "type": "image/png"}
                for n in (192, 512)
            ],
        },
        media_type="application/manifest+json",
    )
