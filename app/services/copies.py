"""Личная полка: конкретные экземпляры книг."""
from app import config
from app.db import tx
from app.errors import ValidationFailed, conflict, forbidden, not_found
from app.util import Page, clamp_page, now_iso, parse_date, today

CONDITIONS = {"new": "Как новая", "good": "Хорошее", "fair": "Среднее", "worn": "Потрёпанная"}
_ACTIVE_LOAN = "l.copy_id = c.id AND l.status IN ('accepted', 'handed_over')"


def _clean(condition, pickup_place) -> tuple[str, str]:
    errors = {}
    condition = (condition or "").strip()
    pickup_place = (pickup_place or "").strip()
    if condition not in CONDITIONS:
        errors["condition"] = "Выберите состояние книги."
    if not 2 <= len(pickup_place) <= 120:
        errors["pickup_place"] = "Укажите место передачи (от 2 до 120 символов)."
    if errors:
        raise ValidationFailed(errors)
    return condition, pickup_place


def add_copy(conn, owner_id, book_id_raw, condition, pickup_place) -> int:
    errors = {}
    try:
        book_id = int(book_id_raw)
    except (TypeError, ValueError):
        book_id = None
    if book_id is None or conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
        errors["book_id"] = "Выберите книгу из каталога."
    try:
        condition, pickup_place = _clean(condition, pickup_place)
    except ValidationFailed as e:
        errors.update(e.fields)
    if errors:
        raise ValidationFailed(errors)
    cur = conn.execute(
        "INSERT INTO copies (book_id, owner_id, condition, pickup_place, is_active, created_at) "
        "VALUES (?,?,?,?,1,?)", (book_id, owner_id, condition, pickup_place, now_iso()))
    return cur.lastrowid


def get_owned(conn, copy_id, user) -> dict:
    """Экземпляр, которым управляет текущий пользователь (404 / 403)."""
    row = conn.execute(
        "SELECT c.*, b.title, b.author FROM copies c JOIN books b ON b.id = c.book_id WHERE c.id = ?",
        (copy_id,)).fetchone()
    if row is None:
        raise not_found("Экземпляр не найден.")
    if row["owner_id"] != user["id"]:
        raise forbidden("Это не ваш экземпляр.")
    return row


def update_copy(conn, copy_id, user, condition, pickup_place):
    get_owned(conn, copy_id, user)
    condition, pickup_place = _clean(condition, pickup_place)
    conn.execute("UPDATE copies SET condition = ?, pickup_place = ? WHERE id = ?",
                 (condition, pickup_place, copy_id))


def _has_active_loan(conn, copy_id) -> bool:
    return conn.execute("SELECT 1 FROM loans l, copies c WHERE c.id = ? AND " + _ACTIVE_LOAN,
                        (copy_id,)).fetchone() is not None


def set_active(conn, copy_id, user, active: bool):
    """Скрыть/вернуть экземпляр. Скрыть нельзя, пока есть принятая или переданная заявка."""
    with tx(conn):
        get_owned(conn, copy_id, user)
        if not active:
            if _has_active_loan(conn, copy_id):
                raise conflict("Экземпляр принят или передан — скрыть его можно только после возврата.")
            conn.execute("UPDATE loans SET status = 'rejected' WHERE copy_id = ? AND status = 'pending'",
                         (copy_id,))
        conn.execute("UPDATE copies SET is_active = ? WHERE id = ?", (1 if active else 0, copy_id))


def delete_copy(conn, copy_id, user):
    """Удалить можно только экземпляр без истории обменов (историю не теряем)."""
    with tx(conn):
        get_owned(conn, copy_id, user)
        if _has_active_loan(conn, copy_id):
            raise conflict("Экземпляр принят или передан — удалить его нельзя до возврата.")
        if conn.execute("SELECT 1 FROM loans WHERE copy_id = ?", (copy_id,)).fetchone():
            raise conflict("У экземпляра есть история обменов, поэтому удалить его нельзя. "
                           "Его можно скрыть с полки.")
        conn.execute("DELETE FROM copies WHERE id = ?", (copy_id,))


def shelf(conn, owner_id, page=1, per_page=config.PER_PAGE) -> Page:
    total = conn.execute("SELECT COUNT(*) AS n FROM copies WHERE owner_id = ?", (owner_id,)).fetchone()["n"]
    page = clamp_page(page, total, per_page)
    rows = conn.execute(
        f"""SELECT c.*, b.title, b.author, b.cover_url,
              (SELECT l.status FROM loans l WHERE {_ACTIVE_LOAN}) AS active_status,
              (SELECT u.display_name FROM loans l JOIN users u ON u.id = l.borrower_id
                 WHERE {_ACTIVE_LOAN}) AS borrower_name,
              (SELECT l.requested_return_date FROM loans l WHERE {_ACTIVE_LOAN}) AS due_date,
              (SELECT COUNT(*) FROM loans l WHERE l.copy_id = c.id AND l.status = 'pending') AS pending_count,
              (SELECT COUNT(*) FROM loans l WHERE l.copy_id = c.id) AS loans_total
            FROM copies c JOIN books b ON b.id = c.book_id
            WHERE c.owner_id = ?
            ORDER BY b.title_key, c.id LIMIT ? OFFSET ?""",
        (owner_id, per_page, (page - 1) * per_page)).fetchall()
    for r in rows:
        r["overdue"] = bool(r["active_status"] == "handed_over" and r["due_date"]
                            and (parse_date(r["due_date"]) or today()) < today())
        if not r["is_active"]:
            r["state"] = "hidden"
        elif r["active_status"] == "handed_over":
            r["state"] = "lent"
        elif r["active_status"] == "accepted":
            r["state"] = "reserved"
        else:
            r["state"] = "free"
    return Page(rows, total, page, per_page)
