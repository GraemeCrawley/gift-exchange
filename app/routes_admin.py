from fastapi import APIRouter, Depends, Form, HTTPException, Request

from app import repo
from app.web import get_conn, manifest, redirect, render, url

router = APIRouter(prefix="/a/{token}")

# Success messages shown after a redirect. Only these keys are accepted from the URL.
MESSAGES = {
    "added": "Added.",
    "saved": "Saved.",
    "renamed": "Renamed.",
    "household": "Households saved.",
    "removed": "Removed.",
    "reset": "Claim reset. Their old link no longer works. Send them the new one below.",
    "drawn": "Names drawn! Now share the group link.",
}

# Where on the page each action lands, so a phone doesn't jump back to the top.
SPOTS = {"added": "add", "renamed": "people", "household": "people", "removed": "people", "reset": "people"}


def _load(conn, token: str) -> repo.Exchange:
    ex = repo.get_exchange_by_admin(conn, token)
    if ex is None:
        raise HTTPException(404)
    return ex


def _panel(request: Request, conn, token: str, ex: repo.Exchange, error: str | None = None, status: int = 200, spot: str | None = None):
    key = request.query_params.get("msg", "")
    msg = MESSAGES.get(key)
    if spot is None and not error:
        spot = SPOTS.get(key)
    return render(
        request,
        "admin.html",
        {
            "ex": ex,
            "token": token,
            "people": (people := repo.list_participants(conn, ex.id)),
            "labels": repo.household_labels(people),
            "message": None if error else msg,
            "error": error,
            "spot": spot,
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
        return _panel(request, conn, token, repo.get_exchange(conn, ex.id), error=str(e), status=400, spot=SPOTS.get(msg_key))
    except LookupError:
        raise HTTPException(404) from None
    spot = SPOTS.get(msg_key)
    return redirect(request, f"/a/{token}?msg={msg_key}" + (f"#{spot}" if spot else ""))


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
def draw(request: Request, token: str, confirm: str = Form(""), conn=Depends(get_conn)):
    def action(ex):
        if ex.draw_state != "none" and confirm != "on":
            raise repo.ValidationError("Names are already drawn. Tick the box to confirm re-drawing.")
        repo.run_draw(conn, ex.id)

    return _act(request, conn, token, action, "drawn")


@router.get("/households")
def households_page(request: Request, token: str, conn=Depends(get_conn)):
    ex = _load(conn, token)
    people = repo.list_participants(conn, ex.id)
    # Number the existing households 1, 2, 3... in the order they first appear.
    keys: dict[str, str] = {}
    for p in people:
        if p.household and p.household not in keys:
            keys[p.household] = str(len(keys) + 1)
    groups = [
        {"key": k, "people": [p for p in people if keys.get(p.household or "") == k]} for k in keys.values()
    ]
    return render(
        request,
        "households.html",
        {
            "ex": ex,
            "token": token,
            "loose": [p for p in people if not p.household],
            "groups": groups,
            "labels": repo.household_labels(people),
            "keys": {p.id: keys.get(p.household or "", "") for p in people},
            "people": people,
            "manifest_url": url(request, f"/a/{token}/manifest.webmanifest"),
        },
    )


@router.post("/households")
async def save_households(request: Request, token: str, conn=Depends(get_conn)):
    form = await request.form()
    choice: dict[int, str] = {}
    for name, value in form.multi_items():
        if not name.startswith("hh_"):
            continue
        try:
            pid = int(name[3:])
        except ValueError:
            raise HTTPException(404) from None
        choice[pid] = str(value).strip()
    return _act(request, conn, token, lambda ex: repo.set_households(conn, ex.id, choice), "household")


@router.get("/manifest.webmanifest")
def web_manifest(request: Request, token: str, conn=Depends(get_conn)):
    ex = _load(conn, token)
    return manifest(request, ex.name, f"/a/{token}")
