from fastapi import APIRouter, Depends, Form, HTTPException, Request

from app import repo
from app.web import get_conn, redirect, render

router = APIRouter(prefix="/p/{token}")


def _load(conn, token: str) -> tuple[repo.Participant, repo.Exchange]:
    p = repo.get_participant_by_token(conn, token)
    if p is None:
        raise HTTPException(404)
    return p, repo.get_exchange(conn, p.exchange_id)


def person_page(request: Request, conn, p: repo.Participant, ex: repo.Exchange, error: str | None = None, status: int = 200):
    return render(
        request,
        "person.html",
        {"p": p, "ex": ex, "token": p.personal_token, "error": error},
        status=status,
    )


@router.get("")
def page(request: Request, token: str, conn=Depends(get_conn)):
    p, ex = _load(conn, token)
    repo.claim_by_token(conn, p)
    if not p.link_saved and request.query_params.get("later") != "1":
        return render(request, "person_save.html", {"p": p, "ex": ex, "token": token})
    return person_page(request, conn, p, ex)


@router.post("/saved")
def saved(request: Request, token: str, saved: str = Form(""), conn=Depends(get_conn)):
    p, ex = _load(conn, token)
    if saved != "on":
        return render(
            request, "person_save.html",
            {"p": p, "ex": ex, "token": token, "error": "Tick the box once you've saved your link."},
            status=400,
        )
    repo.mark_link_saved(conn, p.id)
    return redirect(request, f"/p/{token}")
