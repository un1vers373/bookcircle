"""Личный список чтения."""
from datetime import date

from app import config
from app.errors import ValidationFailed, not_found
from app.util import Page, clamp_page, month_bounds, parse_date, today

STATUSES = {"want": "Хочу прочитать", "reading": "Читаю", "done": "Прочитал"}


def set_entry(conn, user_id: int, book_id: int, status: str, finished_at_raw: str = ""):
    """Создаёт или обновляет запись (одна на пару пользователь/книга)."""
    status = (status or "").strip()
    if status not in STATUSES:
        raise ValidationFailed({"status": "Выберите статус из списка."})
    if conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
        raise not_found("Книга не найдена.")
    finished = None
    if status == "done":
        raw = (finished_at_raw or "").strip()
        if raw:
            d = parse_date(raw)
            if d is None:
                raise ValidationFailed({"finished_at": "Введите дату в формате ГГГГ-ММ-ДД."})
            if d > today():
                raise ValidationFailed({"finished_at": "Дата завершения не может быть в будущем."})
        else:
            d = today()
        finished = d.isoformat()
    conn.execute(
        "INSERT INTO reading_entries (user_id, book_id, status, finished_at) VALUES (?,?,?,?) "
        "ON CONFLICT (user_id, book_id) DO UPDATE SET status = excluded.status, "
        "finished_at = excluded.finished_at", (user_id, book_id, status, finished))


def get_entry(conn, user_id: int, book_id: int):
    return conn.execute("SELECT * FROM reading_entries WHERE user_id = ? AND book_id = ?",
                        (user_id, book_id)).fetchone()


def list_entries(conn, user_id: int, status: str = "", page=1, per_page=config.PER_PAGE) -> Page:
    where, params = "e.user_id = ?", [user_id]
    if status in STATUSES:
        where += " AND e.status = ?"
        params.append(status)
    total = conn.execute(f"SELECT COUNT(*) AS n FROM reading_entries e WHERE {where}", params).fetchone()["n"]
    page = clamp_page(page, total, per_page)
    rows = conn.execute(
        f"""SELECT e.*, b.title, b.author, b.cover_url FROM reading_entries e
            JOIN books b ON b.id = e.book_id WHERE {where}
            ORDER BY CASE e.status WHEN 'reading' THEN 0 WHEN 'want' THEN 1 ELSE 2 END,
                     e.finished_at DESC, e.id DESC
            LIMIT ? OFFSET ?""", [*params, per_page, (page - 1) * per_page]).fetchall()
    return Page(rows, total, page, per_page)


def stats(conn, user_id: int) -> dict:
    counts = {s: 0 for s in STATUSES}
    for r in conn.execute("SELECT status, COUNT(*) AS n FROM reading_entries WHERE user_id = ? GROUP BY status",
                          (user_id,)):
        counts[r["status"]] = r["n"]
    start, end = month_bounds()
    month = conn.execute(
        "SELECT COUNT(*) AS n FROM reading_entries WHERE user_id = ? AND status = 'done' "
        "AND finished_at >= ? AND finished_at < ?", (user_id, start, end)).fetchone()["n"]
    t = today()
    year = conn.execute(
        "SELECT COUNT(*) AS n FROM reading_entries WHERE user_id = ? AND status = 'done' "
        "AND finished_at >= ? AND finished_at < ?",
        (user_id, date(t.year, 1, 1).isoformat(), date(t.year + 1, 1, 1).isoformat())).fetchone()["n"]
    return {"counts": counts, "month": month, "year": year}
