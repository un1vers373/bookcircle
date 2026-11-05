"""Регистрация, вход, выход, профиль."""
from fastapi import APIRouter, Depends, Request

from app.errors import ValidationFailed
from app.routes.deps import get_conn, require_user
from app.services import users
from app.web import flash, form_dict, redirect, render, safe_next

router = APIRouter()


def _logged_in(request) -> bool:
    return bool(request.session.get("uid"))


@router.get("/register")
async def register_form(request: Request):
    if _logged_in(request):
        return redirect("/books")
    return render(request, "register.html", {"user": None, "values": {}, "errors": {}})


@router.post("/register")
async def register(request: Request, conn=Depends(get_conn)):
    f = await form_dict(request)
    try:
        uid = users.register(conn, f.get("email"), f.get("display_name"),
                             f.get("password"), f.get("password2"))
    except ValidationFailed as e:
        return render(request, "register.html", {"user": None, "values": f, "errors": e.fields}, 400)
    request.session.clear()
    request.session["uid"] = uid
    flash(request, "Добро пожаловать в BookCircle!")
    return redirect("/books")


@router.get("/login")
async def login_form(request: Request):
    if _logged_in(request):
        return redirect("/books")
    return render(request, "login.html", {"user": None, "values": {}, "errors": {},
                                          "next": request.query_params.get("next", "")})


@router.post("/login")
async def login(request: Request, conn=Depends(get_conn)):
    f = await form_dict(request)
    try:
        uid = users.authenticate(conn, f.get("email"), f.get("password"))
    except ValidationFailed as e:
        values = {"email": f.get("email", "")}
        return render(request, "login.html", {"user": None, "values": values, "errors": e.fields,
                                              "next": f.get("next", "")}, 400)
    request.session.clear()
    request.session["uid"] = uid
    return redirect(safe_next(f.get("next"), "/books"))


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return redirect("/login")


@router.get("/profile")
async def profile_form(request: Request, user=Depends(require_user)):
    return render(request, "profile.html", {"user": user, "values": {"display_name": user["display_name"]},
                                            "errors": {}})


@router.post("/profile")
async def profile(request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    f = await form_dict(request)
    try:
        users.update_profile(conn, user["id"], f.get("display_name"),
                             f.get("current_password"), f.get("new_password"))
    except ValidationFailed as e:
        return render(request, "profile.html", {"user": user, "values": f, "errors": e.fields}, 400)
    flash(request, "Профиль сохранён.")
    return redirect("/profile")
