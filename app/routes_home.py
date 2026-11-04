from fastapi import APIRouter, Depends, Form, Request

from app import repo
from app.web import get_conn, redirect, render

router = APIRouter()


@router.get("/")
def home(request: Request):
    return render(request, "home.html")


@router.post("/create")
def create(request: Request, name: str = Form(""), conn=Depends(get_conn)):
    try:
        _, raw = repo.create_exchange(conn, name)
    except repo.ValidationError as e:
        return render(request, "home.html", {"error": str(e), "name": name}, status=400)
    return redirect(request, f"/a/{raw}")
