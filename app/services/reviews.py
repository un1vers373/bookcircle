"""Рецензии и их модерация."""
from app.errors import ValidationFailed, forbidden, not_found
from app.util import Page, clamp_page, now_iso


def get_user_review(conn, user_id, book_id):
    return conn.execute("SELECT * FROM reviews WHERE user_id = ? AND book_id = ?",
                        (user_id, book_id)).fetchone()


def upsert_review(conn, user_id: int, book_id: int, score_raw, text) -> bool:
    """Одна рецензия на пару пользователь/книга: повторная отправка редактирует.
    Возвращает True, если рецензия создана, False — если изменена."""
    errors = {}
    try:
        score = int(score_raw)
        if not 1 <= score <= 5:
            raise ValueError
    except (TypeError, ValueError):
        score = None
        errors["score"] = "Поставьте оценку от 1 до 5."
    text = (text or "").strip()
    if not 1 <= len(text) <= 2000:
        errors["text"] = "Напишите отзыв (до 2000 символов)."
    if errors:
        raise ValidationFailed(errors)
    if conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
        raise not_found("Книга не найдена.")
    existed = get_user_review(conn, user_id, book_id) is not None
    now = now_iso()
    conn.execute(
        "INSERT INTO reviews (user_id, book_id, score, text, is_hidden, created_at, updated_at) "
        "VALUES (?,?,?,?,0,?,?) "
        "ON CONFLICT (user_id, book_id) DO UPDATE SET score = excluded.score, text = excluded.text, "
        "updated_at = excluded.updated_at", (user_id, book_id, score, text, now, now))
    return not existed


def list_for_book(conn, book_id: int, page=1, per_page=5) -> Page:
    """Публичные отзывы (скрытые не показываем)."""
    total = conn.execute("SELECT COUNT(*) AS n FROM reviews WHERE book_id = ? AND is_hidden = 0",
                         (book_id,)).fetchone()["n"]
    page = clamp_page(page, total, per_page)
    rows = conn.execute(
        """SELECT r.*, u.display_name AS author_name FROM reviews r JOIN users u ON u.id = r.user_id
           WHERE r.book_id = ? AND r.is_hidden = 0
           ORDER BY r.updated_at DESC, r.id DESC LIMIT ? OFFSET ?""",
        (book_id, per_page, (page - 1) * per_page)).fetchall()
    return Page(rows, total, page, per_page)


def list_for_moderation(conn, only_hidden=False, page=1, per_page=10) -> Page:
    where = "WHERE r.is_hidden = 1" if only_hidden else ""
    total = conn.execute(f"SELECT COUNT(*) AS n FROM reviews r {where}").fetchone()["n"]
    page = clamp_page(page, total, per_page)
    rows = conn.execute(
        f"""SELECT r.*, u.display_name AS author_name, b.title FROM reviews r
            JOIN users u ON u.id = r.user_id JOIN books b ON b.id = r.book_id
            {where} ORDER BY r.updated_at DESC, r.id DESC LIMIT ? OFFSET ?""",
        (per_page, (page - 1) * per_page)).fetchall()
    return Page(rows, total, page, per_page)


def set_hidden(conn, actor, review_id: int, hidden: bool):
    if actor["role"] not in ("moderator", "admin"):
        raise forbidden("Скрывать рецензии может только модератор.")
    cur = conn.execute("UPDATE reviews SET is_hidden = ? WHERE id = ?", (1 if hidden else 0, review_id))
    if cur.rowcount == 0:
        raise not_found("Рецензия не найдена.")
