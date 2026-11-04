import logging
import re

from fastapi import Request

_TOKEN_PATH = re.compile(r"/(a|p|j)/[A-Za-z0-9_-]+")
_PRIVATE_PREFIXES = ("/a/", "/p/")


def redact(text: str) -> str:
    return _TOKEN_PATH.sub(r"/\1/***", text)


class RedactTokensFilter(logging.Filter):
    """Strip link tokens out of access-log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # same-origin: no referrer leaves the site (tokens stay private), but browsers
    # still send a real Origin on our own form posts. no-referrer makes it "null".
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Robots-Tag"] = "noindex"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith(_PRIVATE_PREFIXES):
        response.headers["Cache-Control"] = "no-store"
    return response


def same_origin_ok(request: Request) -> bool:
    """Block form posts from other websites."""
    from urllib.parse import urlsplit

    # Modern browsers say directly where a request came from.
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        return site in ("same-origin", "none")
    origin = request.headers.get("origin")
    if origin is None:
        return True
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    return urlsplit(origin).netloc == host.split(",")[0].strip()


async def origin_check(request: Request, call_next):
    if request.method == "POST" and not same_origin_ok(request):
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse("Forbidden: this form was sent from another website.", status_code=403)
    return await call_next(request)
