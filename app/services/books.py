"""Каталог произведений (справочник книг)."""
import sqlite3

from app import config
from app.errors import ValidationFailed, not_found
from app.util import Page, clamp_page, like_escape, month_bounds, now_iso

# Экземпляр доступен: виден владельцем и нет принятой/активной передачи.
AVAILABLE = ("c.is_active = 1 AND NOT EXISTS (SELECT 1 FROM loans l2 "
             "WHERE l2.copy_id = c.id AND l2.status IN ('accepted', 'handed_over'))")

# Параметры подзапроса read_month: (начало месяца, начало следующего).
_SELECT = f"""
SELECT b.*,
  (SELECT ROUND(AVG(r.score), 2) FROM reviews r
     WHERE r.book_id = b.id AND r.is_hidden = 0) AS avg_rating,
  (SELECT COUNT(*) FROM reviews r
     WHERE r.book_id = b.id AND r.is_hidden = 0) AS reviews_count,
  (SELECT COUNT(*) FROM copies c WHERE c.book_id = b.id AND c.is_active = 1) AS copies_count,
  (SELECT COUNT(*) FROM copies c WHERE c.book_id = b.id AND {AVAILABLE}) AS available_count,
  (SELECT COUNT(*) FROM reading_entries e
     WHERE e.book_id = b.id AND e.status = 'done'
       AND e.finished_at >= ? AND e.finished_at < ?) AS read_month
FROM books b
"""


def _clean(data: dict) -> dict:
    errors = {}
    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()
    genre = (data.get("genre") or "").strip()
    description = (data.get("description") or "").strip()
    cover_url = (data.get("cover_url") or "").strip()
    if not 1 <= len(title) <= 200:
        errors["title"] = "Название обязательно (до 200 символов)."
    if not 1 <= len(author) <= 120:
        errors["author"] = "Укажите автора (до 120 символов)."
    if not 1 <= len(genre) <= 60:
        errors["genre"] = "Укажите жанр (до 60 символов)."
    if len(description) > 2000:
        errors["description"] = "Описание не длиннее 2000 символов."
    if cover_url and not cover_url.startswith(("http://", "https://", "/static/")):
        errors["cover_url"] = "Ссылка на обложку должна начинаться с http://, https:// или /static/."
    if errors:
        raise ValidationFailed(errors)
    return {"title": title, "author": author, "genre": genre, "description": description,
            "cover_url": cover_url or None,
            "title_key": title.casefold(), "search_key": f"{title} {author}".casefold()}


def create_book(conn, data: dict) -> int:
    d = _clean(data)
    try:
        cur = conn.execute(
            "INSERT INTO books (title, author, genre, description, cover_url, title_key, search_key, created_at) "
            "VALUES (:title, :author, :genre, :description, :cover_url, :title_key, :search_key, :created_at)",
            {**d, "created_at": now_iso()})
    except sqlite3.IntegrityError:
        raise ValidationFailed({"title": "Такая книга этого автора уже есть в каталоге."})
    return cur.lastrowid


def update_book(conn, book_id: int, data: dict):
    if conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
        raise not_found("Книга не найдена.")
    d = _clean(data)
    try:
        conn.execute(
            "UPDATE books SET title=:title, author=:author, genre=:genre, description=:description, "
            "cover_url=:cover_url, title_key=:title_key, search_key=:search_key WHERE id=:id",
            {**d, "id": book_id})
    except sqlite3.IntegrityError:
        raise ValidationFailed({"title": "Такая книга этого автора уже есть в каталоге."})


def get_book(conn, book_id: int) -> dict:
    start, end = month_bounds()
    row = conn.execute(_SELECT + " WHERE b.id = ?", (start, end, book_id)).fetchone()
    if row is None:
        raise not_found("Книга не найдена.")
    return row


def list_books(conn, q="", genre="", only_available=False, page=1,
               per_page=config.PER_PAGE) -> Page:
    where, params = ["1 = 1"], []
    q = (q or "").strip().casefold()
    if q:
        where.append("b.search_key LIKE ? ESCAPE '\\'")
        params.append(f"%{like_escape(q)}%")
    if genre:
        where.append("b.genre = ?")
        params.append(genre)
    if only_available:
        where.append(f"EXISTS (SELECT 1 FROM copies c WHERE c.book_id = b.id AND {AVAILABLE})")
    w = " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) AS n FROM books b WHERE {w}", params).fetchone()["n"]
    page = clamp_page(page, total, per_page)
    start, end = month_bounds()
    items = conn.execute(
        _SELECT + f" WHERE {w} ORDER BY b.title_key, b.id LIMIT ? OFFSET ?",
        [start, end, *params, per_page, (page - 1) * per_page]).fetchall()
    return Page(items, total, page, per_page)


def genres(conn) -> list[str]:
    return [r["genre"] for r in conn.execute("SELECT DISTINCT genre FROM books ORDER BY genre")]


def all_books_brief(conn) -> list[dict]:
    return conn.execute("SELECT id, title, author FROM books ORDER BY title_key").fetchall()


def book_copies(conn, book_id: int, viewer_id: int) -> list[dict]:
    """Видимые экземпляры книги + статус и мой запрос по каждому."""
    rows = conn.execute(
        f"""SELECT c.*, u.display_name AS owner_name,
               CASE WHEN {AVAILABLE} THEN 1 ELSE 0 END AS is_free,
               (SELECT l.status FROM loans l WHERE l.copy_id = c.id AND l.borrower_id = ?
                  AND l.status IN ('pending', 'accepted', 'handed_over') LIMIT 1) AS my_loan_status
            FROM copies c JOIN users u ON u.id = c.owner_id
            WHERE c.book_id = ? AND c.is_active = 1
            ORDER BY c.id""", (viewer_id, book_id)).fetchall()
    return rows
