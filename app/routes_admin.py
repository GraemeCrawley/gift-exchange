from fastapi import APIRouter, Depends, Form, HTTPException, Request

from app import repo
from app.web import get_conn, manifest, redirect, render, url

router = APIRouter(prefix="/a/{token}")

# Success messages shown after a redirect. Only these keys are accepted from the URL.
MESSAGES = {
    "added": "Added.",
    "saved": "Saved.",
    "renamed": "Renamed.",
    "household": "Household updated.",
    "removed": "Removed.",
    "reset": "Claim reset. Their old link no longer works. Send them the new one below.",
    "drawn": "Names drawn! Now share the group link.",
}


def _load(conn, token: str) -> repo.Exchange:
    ex = repo.get_exchange_by_admin(conn, token)
    if ex is None:
        raise HTTPException(404)
    return ex


def _panel(request: Request, conn, token: str, ex: repo.Exchange, error: str | None = None, status: int = 200):
    msg = MESSAGES.get(request.query_params.get("msg", ""))
    return render(
        request,
        "admin.html",
        {
            "ex": ex,
            "token": token,
            "people": repo.list_participants(conn, ex.id),
            "message": None if error else msg,
            "error": error,
            "manifest_url": url(request, f"/a/{token}/manifest.webmanifest"),
        },
        status=status,
    )


@router.get("")
def panel(request: Request, token: str, conn=Depends(get_conn)):
    ex = _load(conn, token)
    if not ex.admin_link_saved:
        return render(request, "admin_saved.html", {"ex": ex, "token": token, "manifest_url": url(request, f"/a/{token}/manifest.webmanifest")})
    return _panel(request, conn, token, ex)


@router.post("/saved")
def saved(request: Request, token: str, saved: str = Form(""), conn=Depends(get_conn)):
    ex = _load(conn, token)
    if saved != "on":
        return render(request, "admin_saved.html", {"ex": ex, "token": token, "error": "Tick the box once you've saved your organizer link."}, status=400)
    repo.mark_admin_link_saved(conn, ex.id)
    return redirect(request, f"/a/{token}")


def _act(request, conn, token, action, msg_key):
    """Run an organizer action; re-render with the error, or redirect with a message."""
    ex = _load(conn, token)
    try:
        action(ex)
    except repo.ValidationError as e:
        return _panel(request, conn, token, repo.get_exchange(conn, ex.id), error=str(e), status=400)
    except LookupError:
        raise HTTPException(404) from None
    return redirect(request, f"/a/{token}?msg={msg_key}")


@router.post("/settings")
def settings(
    request: Request,
    token: str,
    name: str = Form(""),
    exchange_date: str = Form(""),
    price_limit: str = Form(""),
    conn=Depends(get_conn),
):
    return _act(request, conn, token, lambda ex: repo.update_settings(conn, ex.id, name, exchange_date, price_limit), "saved")


@router.post("/people")
def add_person(request: Request, token: str, name: str = Form(""), conn=Depends(get_conn)):
    return _act(request, conn, token, lambda ex: repo.add_participant(conn, ex.id, name), "added")


@router.post("/people/{pid}/rename")
def rename(request: Request, token: str, pid: int, name: str = Form(""), conn=Depends(get_conn)):
    return _act(request, conn, token, lambda ex: repo.rename_participant(conn, ex.id, pid, name), "renamed")


@router.post("/people/{pid}/household")
def household(request: Request, token: str, pid: int, household: str = Form(""), conn=Depends(get_conn)):
    return _act(request, conn, token, lambda ex: repo.set_household(conn, ex.id, pid, household), "household")


@router.post("/people/{pid}/remove")
def remove(request: Request, token: str, pid: int, confirm: str = Form(""), conn=Depends(get_conn)):
    def action(ex):
        if confirm != "on":
            raise repo.ValidationError("Tick the box to confirm removing this person.")
        repo.remove_participant(conn, ex.id, pid)

    return _act(request, conn, token, action, "removed")


@router.post("/people/{pid}/reset")
def reset(request: Request, token: str, pid: int, conn=Depends(get_conn)):
    return _act(request, conn, token, lambda ex: repo.reset_claim(conn, ex.id, pid), "reset")


@router.post("/draw")
def draw(request: Request, token: str, conn=Depends(get_conn)):
    return _act(request, conn, token, lambda ex: repo.run_draw(conn, ex.id), "drawn")


@router.get("/manifest.webmanifest")
def web_manifest(request: Request, token: str, conn=Depends(get_conn)):
    ex = _load(conn, token)
    return manifest(request, ex.name, f"/a/{token}")
