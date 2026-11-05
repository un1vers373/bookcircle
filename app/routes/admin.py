"""Модерация (модератор/админ) и управление ролями (админ)."""
from fastapi import APIRouter, Depends, Request

from app.errors import ValidationFailed
from app.routes.deps import get_conn, require_admin, require_moderator
from app.services import books, reviews, users
from app.web import flash, form_dict, page_num, redirect, render

router = APIRouter()


@router.get("/moderation")
async def moderation_index(user=Depends(require_moderator)):
    return redirect("/moderation/books")


@router.get("/moderation/books")
async def mod_books(request: Request, user=Depends(require_moderator), conn=Depends(get_conn)):
    q = request.query_params.get("q", "")
    return render(request, "mod_books.html", {
        "user": user, "tab": "books", "q": q, "values": {}, "errors": {},
        "pg": books.list_books(conn, q, page=page_num(request))})


@router.post("/moderation/books")
async def mod_create_book(request: Request, user=Depends(require_moderator), conn=Depends(get_conn)):
    f = await form_dict(request)
    try:
        books.create_book(conn, f)
    except ValidationFailed as e:
        return render(request, "mod_books.html", {
            "user": user, "tab": "books", "q": "", "values": f, "errors": e.fields,
            "pg": books.list_books(conn, page=page_num(request))}, 400)
    flash(request, "Книга добавлена в каталог.")
    return redirect("/moderation/books")


@router.get("/moderation/books/{book_id}/edit")
async def mod_edit_form(book_id: int, request: Request, user=Depends(require_moderator), conn=Depends(get_conn)):
    book = books.get_book(conn, book_id)
    return render(request, "mod_book_form.html", {"user": user, "tab": "books", "book": book,
                                                  "values": book, "errors": {}})


@router.post("/moderation/books/{book_id}")
async def mod_update_book(book_id: int, request: Request, user=Depends(require_moderator),
                          conn=Depends(get_conn)):
    book = books.get_book(conn, book_id)
    f = await form_dict(request)
    try:
        books.update_book(conn, book_id, f)
    except ValidationFailed as e:
        return render(request, "mod_book_form.html", {"user": user, "tab": "books", "book": book,
                                                      "values": f, "errors": e.fields}, 400)
    flash(request, "Изменения сохранены.")
    return redirect("/moderation/books")


@router.get("/moderation/reviews")
async def mod_reviews(request: Request, user=Depends(require_moderator), conn=Depends(get_conn)):
    only_hidden = request.query_params.get("f") == "hidden"
    return render(request, "mod_reviews.html", {
        "user": user, "tab": "reviews", "only_hidden": only_hidden,
        "pg": reviews.list_for_moderation(conn, only_hidden, page_num(request))})


@router.post("/moderation/reviews/{review_id}/{action}")
async def mod_review_action(review_id: int, action: str, request: Request,
                            user=Depends(require_moderator), conn=Depends(get_conn)):
    if action not in ("hide", "show"):
        from app.errors import not_found
        raise not_found("Неизвестное действие.")
    reviews.set_hidden(conn, user, review_id, action == "hide")
    flash(request, "Рецензия скрыта." if action == "hide" else "Рецензия снова показана.")
    return redirect("/moderation/reviews")


@router.get("/admin/users")
async def admin_users(request: Request, user=Depends(require_admin), conn=Depends(get_conn)):
    return render(request, "admin_users.html", {"user": user, "tab": "users",
                                                "pg": users.list_users(conn, page_num(request))})


@router.post("/admin/users/{user_id}/role")
async def admin_set_role(user_id: int, request: Request, user=Depends(require_admin), conn=Depends(get_conn)):
    f = await form_dict(request)
    users.set_role(conn, user, user_id, f.get("role"))
    flash(request, "Роль изменена.")
    return redirect("/admin/users")
