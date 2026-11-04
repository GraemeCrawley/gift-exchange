"""Small in-memory rate limiter (one app process, so no shared store needed)."""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# name -> (requests allowed, window in seconds)
LIMITS = {
    "create": (10, 3600),
    "claim": (30, 600),
    "wish": (120, 600),
}


class Limiter:
    def __init__(self, limit: int, window_s: int):
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, now: float | None = None) -> bool:
        """Record a request; False if this key is over the limit."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - self.window_s:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


def client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def make_limiters() -> dict[str, Limiter]:
    return {name: Limiter(*cfg) for name, cfg in LIMITS.items()}


def check(request: Request, name: str) -> None:
    """Raise 429 if this client is over the named limit."""
    if not request.app.state.limiters[name].hit(client_ip(request)):
        raise HTTPException(429, "Slow down a little. Too many tries from your network; please try again in a few minutes.")
