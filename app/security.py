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
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith(_PRIVATE_PREFIXES):
        response.headers["Cache-Control"] = "no-store"
    return response
