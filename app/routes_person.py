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
    recipient = repo.get_recipient(conn, p.id)
    return render(
        request,
        "person.html",
        {
            "p": p,
            "ex": ex,
            "token": p.personal_token,
            "recipient": recipient,
            "recipient_items": repo.list_items(conn, recipient.id) if recipient else [],
            "my_items": repo.list_items(conn, p.id),
            "error": error,
        },
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


def _item_action(request: Request, conn, token: str, action):
    p, ex = _load(conn, token)
    try:
        action(p)
    except repo.ValidationError as e:
        return person_page(request, conn, p, ex, error=str(e), status=400)
    except LookupError:
        raise HTTPException(404) from None
    return redirect(request, f"/p/{token}#my-list")


@router.post("/items")
def add_item(request: Request, token: str, text: str = Form(""), url: str = Form(""), conn=Depends(get_conn)):
    return _item_action(request, conn, token, lambda p: repo.add_item(conn, p.id, text, url))


@router.post("/items/{item_id}/edit")
def edit_item(request: Request, token: str, item_id: int, text: str = Form(""), url: str = Form(""), conn=Depends(get_conn)):
    return _item_action(request, conn, token, lambda p: repo.update_item(conn, p.id, item_id, text, url))


@router.post("/items/{item_id}/delete")
def delete_item(request: Request, token: str, item_id: int, conn=Depends(get_conn)):
    return _item_action(request, conn, token, lambda p: repo.delete_item(conn, p.id, item_id))
