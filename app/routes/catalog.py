"""Каталог, страница книги, отзывы, чтение."""
from fastapi import APIRouter, Depends, Request

from app.errors import ValidationFailed
from app.routes.deps import get_conn, require_user
from app.services import books, reading, reviews
from app.web import flash, form_dict, page_num, redirect, render, safe_next

router = APIRouter()


@router.get("/")
async def index():
    return redirect("/books")


@router.get("/books")
async def books_list(request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    q = request.query_params.get("q", "")
    genre = request.query_params.get("genre", "")
    only_available = request.query_params.get("available") == "1"
    pg = books.list_books(conn, q, genre, only_available, page_num(request))
    return render(request, "catalog.html", {
        "user": user, "pg": pg, "q": q, "genre": genre, "only_available": only_available,
        "genres": books.genres(conn)})


def render_book(request, conn, user, book_id: int, status: int = 200, **extra):
    """Страница книги. Используется и для показа ошибок форм (400/409) на этой же странице."""
    book = books.get_book(conn, book_id)
    ctx = {
        "user": user, "book": book,
        "copies": books.book_copies(conn, book_id, user["id"]),
        "pg": reviews.list_for_book(conn, book_id, page_num(request)),
        "my_review": reviews.get_user_review(conn, user["id"], book_id),
        "my_reading": reading.get_entry(conn, user["id"], book_id),
        "review_values": None, "review_errors": {}, "loan_error": None,
    }
    ctx.update(extra)
    return render(request, "book.html", ctx, status)


@router.get("/books/{book_id}")
async def book_page(book_id: int, request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    return render_book(request, conn, user, book_id)


@router.api_route("/books/{book_id}/review", methods=["PUT", "POST"])
async def save_review(book_id: int, request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    """PUT /books/{id}/review (формы браузера отправляют тот же маршрут методом POST)."""
    f = await form_dict(request)
    try:
        created = reviews.upsert_review(conn, user["id"], book_id, f.get("score"), f.get("text"))
    except ValidationFailed as e:
        return render_book(request, conn, user, book_id, 400, review_values=f, review_errors=e.fields)
    flash(request, "Отзыв опубликован." if created else "Отзыв обновлён.")
    return redirect(f"/books/{book_id}")


@router.api_route("/reading/{book_id}", methods=["PUT", "POST"])
async def save_reading(book_id: int, request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    """PUT /reading/{book_id} — статус чтения (создание или изменение записи)."""
    f = await form_dict(request)
    reading.set_entry(conn, user["id"], book_id, f.get("status"), f.get("finished_at", ""))
    flash(request, "Список чтения обновлён.")
    return redirect(safe_next(f.get("next"), f"/books/{book_id}"))


@router.get("/reading")
async def reading_page(request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    status = request.query_params.get("status", "")
    return render(request, "reading.html", {
        "user": user, "status": status,
        "pg": reading.list_entries(conn, user["id"], status, page_num(request)),
        "stats": reading.stats(conn, user["id"])})
