"""Обмены: запросы на книги и жизненный цикл передачи.

ожидает → принята | отклонена | отменена
принята → передана | отменена
передана → возвращена
"""
import sqlite3
from datetime import timedelta

from app import config
from app.db import tx
from app.errors import ValidationFailed, conflict, forbidden, not_found
from app.util import Page, clamp_page, now_iso, parse_date, today

STATUSES = {
    "pending": "Ожидает ответа",
    "accepted": "Принята",
    "handed_over": "Передана",
    "returned": "Возвращена",
    "rejected": "Отклонена",
    "cancelled": "Отменена",
}
ACTIVE = ("pending", "accepted", "handed_over")
DONE = ("returned", "rejected", "cancelled")

# действие -> (из каких статусов, в какой статус)
ACTIONS = {
    "accept": (("pending",), "accepted"),
    "reject": (("pending",), "rejected"),
    "hand-over": (("accepted",), "handed_over"),
    "return": (("handed_over",), "returned"),
    "cancel": (("pending", "accepted"), "cancelled"),
}
MAX_DAYS_AHEAD = 365


def is_overdue(status: str, due_date: str | None) -> bool:
    """Просрочка вычисляется, а не хранится: передана и срок прошёл."""
    d = parse_date(due_date)
    return status == "handed_over" and d is not None and d < today()


def request_loan(conn, user, copy_id: int, return_date_raw: str) -> int:
    d = parse_date(return_date_raw)
    if d is None:
        raise ValidationFailed({"requested_return_date": "Укажите дату возврата."})
    if d < today():
        raise ValidationFailed({"requested_return_date": "Дата возврата не может быть в прошлом."})
    if d > today() + timedelta(days=MAX_DAYS_AHEAD):
        raise ValidationFailed({"requested_return_date": "Срок не может превышать один год."})

    with tx(conn):
        copy = conn.execute("SELECT * FROM copies WHERE id = ?", (copy_id,)).fetchone()
        if copy is None:
            raise not_found("Экземпляр не найден.")
        if copy["owner_id"] == user["id"]:
            raise forbidden("Нельзя одолжить книгу самому себе.")
        if not copy["is_active"]:
            raise conflict("Владелец скрыл этот экземпляр.")
        busy = conn.execute("SELECT 1 FROM loans WHERE copy_id = ? AND status IN ('accepted', 'handed_over')",
                            (copy_id,)).fetchone()
        if busy:
            raise conflict("Этот экземпляр сейчас занят. Попробуйте другой экземпляр или зайдите позже.")
        try:
            cur = conn.execute(
                "INSERT INTO loans (copy_id, borrower_id, requested_return_date, status, created_at) "
                "VALUES (?, ?, ?, 'pending', ?)", (copy_id, user["id"], d.isoformat(), now_iso()))
        except sqlite3.IntegrityError:
            raise conflict("Вы уже отправили запрос на этот экземпляр.")
        return cur.lastrowid


def apply_action(conn, user, loan_id: int, action: str) -> str:
    """Выполняет переход статуса. Возвращает новый статус."""
    if action not in ACTIONS:
        raise not_found("Неизвестное действие.")
    allowed_from, new_status = ACTIONS[action]
    with tx(conn):
        loan = conn.execute(
            "SELECT l.*, c.owner_id, c.is_active FROM loans l JOIN copies c ON c.id = l.copy_id "
            "WHERE l.id = ?", (loan_id,)).fetchone()
        if loan is None:
            raise not_found("Заявка не найдена.")
        is_owner = loan["owner_id"] == user["id"]
        is_borrower = loan["borrower_id"] == user["id"]

        # права
        if action == "cancel":
            if not (is_borrower or (is_owner and loan["status"] == "accepted")):
                raise forbidden("Отменить заявку может заёмщик, а принятую — ещё и владелец.")
        elif not is_owner:
            raise forbidden("Это действие доступно только владельцу экземпляра.")

        # допустимость перехода
        if loan["status"] not in allowed_from:
            raise conflict(f"Это действие сейчас недоступно: заявка в статусе «{STATUSES[loan['status']]}».")

        if action == "accept":
            if not loan["is_active"]:
                raise conflict("Экземпляр скрыт — сначала верните его на полку.")
            try:
                cur = conn.execute("UPDATE loans SET status = 'accepted' WHERE id = ? AND status = 'pending'",
                                   (loan_id,))
            except sqlite3.IntegrityError:
                raise conflict("На этот экземпляр уже принята другая заявка.")
            if cur.rowcount != 1:
                raise conflict("Заявка уже обработана.")
            # остальные ожидающие запросы на этот экземпляр отклоняются
            conn.execute("UPDATE loans SET status = 'rejected' "
                         "WHERE copy_id = ? AND status = 'pending' AND id <> ?", (loan["copy_id"], loan_id))
        elif action == "hand-over":
            conn.execute("UPDATE loans SET status = 'handed_over', handed_at = ? WHERE id = ?",
                         (now_iso(), loan_id))
        elif action == "return":
            conn.execute("UPDATE loans SET status = 'returned', returned_at = ? WHERE id = ?",
                         (now_iso(), loan_id))
        else:
            conn.execute("UPDATE loans SET status = ? WHERE id = ?", (new_status, loan_id))
    return new_status


def list_loans(conn, user_id: int, direction: str, flt: str = "active", page=1,
               per_page=config.PER_PAGE) -> Page:
    """direction: incoming — запросы к моим книгам; outgoing — мои запросы."""
    if direction == "incoming":
        cond, other = "c.owner_id = ?", "l.borrower_id"
    else:
        cond, other = "l.borrower_id = ?", "c.owner_id"
    params = [user_id]
    if flt == "active":
        cond += " AND l.status IN ('pending', 'accepted', 'handed_over')"
    elif flt == "done":
        cond += " AND l.status IN ('returned', 'rejected', 'cancelled')"
    base = ("FROM loans l JOIN copies c ON c.id = l.copy_id JOIN books b ON b.id = c.book_id "
            f"JOIN users u ON u.id = {other} WHERE {cond}")
    total = conn.execute(f"SELECT COUNT(*) AS n {base}", params).fetchone()["n"]
    page = clamp_page(page, total, per_page)
    rows = conn.execute(
        f"""SELECT l.*, c.pickup_place, c.owner_id, b.id AS book_id, b.title, b.author, b.cover_url,
                   u.display_name AS other_name
            {base}
            ORDER BY CASE WHEN l.status IN ('pending', 'accepted', 'handed_over') THEN 0 ELSE 1 END, l.id DESC
            LIMIT ? OFFSET ?""", [*params, per_page, (page - 1) * per_page]).fetchall()
    for r in rows:
        r["overdue"] = is_overdue(r["status"], r["requested_return_date"])
    return Page(rows, total, page, per_page)
