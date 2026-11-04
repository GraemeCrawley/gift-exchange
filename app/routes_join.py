from fastapi import APIRouter, Depends, HTTPException, Request

from app import ratelimit, repo
from app.web import get_conn, redirect, render

router = APIRouter(prefix="/j/{join_token}")


def _load(conn, join_token: str) -> repo.Exchange:
    ex = repo.get_exchange_by_join(conn, join_token)
    if ex is None:
        raise HTTPException(404)
    return ex


def _page(request, conn, ex, join_token, error=None, status=200):
    return render(
        request,
        "join.html",
        {"ex": ex, "join_token": join_token, "people": repo.list_participants(conn, ex.id), "error": error},
        status=status,
    )


@router.get("")
def join(request: Request, join_token: str, conn=Depends(get_conn)):
    return _page(request, conn, _load(conn, join_token), join_token)


@router.post("/claim/{pid}")
def claim(request: Request, join_token: str, pid: int, conn=Depends(get_conn)):
    ratelimit.check(request, "claim")
    ex = _load(conn, join_token)
    if ex.draw_state == "none":
        return _page(request, conn, ex, join_token)
    if repo.get_participant(conn, ex.id, pid) is None:
        raise HTTPException(404)
    p = repo.claim(conn, ex.id, pid)
    if p is None:
        return _page(
            request, conn, ex, join_token,
            error="Already claimed. If that's your name and you didn't pick it, ask the organizer to reset it.",
            status=409,
        )
    return redirect(request, f"/p/{p.personal_token}")
