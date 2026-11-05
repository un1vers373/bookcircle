"""Пользователи: регистрация, вход, профиль, роли."""
import re
import sqlite3

from app import config
from app.errors import ValidationFailed, conflict, forbidden, not_found
from app.security import hash_password, verify_password
from app.util import Page, clamp_page, now_iso

ROLES = {"user": "Участник", "moderator": "Модератор", "admin": "Администратор"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_password(password: str, errors: dict, field: str = "password"):
    if len(password or "") < 8:
        errors[field] = "Пароль должен быть не короче 8 символов."


def _validate_name(name: str, errors: dict):
    if not 2 <= len(name) <= 40:
        errors["display_name"] = "Имя должно быть от 2 до 40 символов."


def get_user(conn, user_id):
    return conn.execute("SELECT id, email, display_name, role, created_at FROM users WHERE id = ?",
                        (user_id,)).fetchone()


def register(conn, email, display_name, password, password2, role="user") -> int:
    errors = {}
    email = (email or "").strip().lower()
    display_name = (display_name or "").strip()
    if not EMAIL_RE.match(email):
        errors["email"] = "Введите корректный email."
    _validate_name(display_name, errors)
    _validate_password(password, errors)
    if "password" not in errors and password != password2:
        errors["password2"] = "Пароли не совпадают."
    if "email" not in errors and conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        errors["email"] = "Этот email уже зарегистрирован."
    if errors:
        raise ValidationFailed(errors)
    try:
        cur = conn.execute(
            "INSERT INTO users (email, display_name, password_hash, role, created_at) VALUES (?,?,?,?,?)",
            (email, display_name, hash_password(password), role, now_iso()))
    except sqlite3.IntegrityError:
        raise ValidationFailed({"email": "Этот email уже зарегистрирован."})
    return cur.lastrowid


def authenticate(conn, email, password) -> int:
    row = conn.execute("SELECT id, password_hash FROM users WHERE email = ?",
                       ((email or "").strip().lower(),)).fetchone()
    # одно и то же сообщение, чтобы не подсказывать, какой email существует
    if row is None or not verify_password(password or "", row["password_hash"]):
        raise ValidationFailed({"password": "Неверный email или пароль."})
    return row["id"]


def update_profile(conn, user_id, display_name, current_password, new_password):
    errors = {}
    display_name = (display_name or "").strip()
    _validate_name(display_name, errors)
    if new_password:
        _validate_password(new_password, errors, "new_password")
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        if not verify_password(current_password or "", row["password_hash"]):
            errors["current_password"] = "Текущий пароль указан неверно."
    if errors:
        raise ValidationFailed(errors)
    if new_password:
        conn.execute("UPDATE users SET display_name = ?, password_hash = ? WHERE id = ?",
                     (display_name, hash_password(new_password), user_id))
    else:
        conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id))


def list_users(conn, page=1, per_page=config.PER_PAGE) -> Page:
    total = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    page = clamp_page(page, total, per_page)
    items = conn.execute(
        "SELECT id, email, display_name, role, created_at FROM users ORDER BY id LIMIT ? OFFSET ?",
        (per_page, (page - 1) * per_page)).fetchall()
    return Page(items, total, page, per_page)


def set_role(conn, actor, user_id, role):
    """Назначение ролей — только администратор."""
    if actor["role"] != "admin":
        raise forbidden("Назначать роли может только администратор.")
    if role not in ROLES:
        raise ValidationFailed({"role": "Неизвестная роль."})
    target = get_user(conn, user_id)
    if target is None:
        raise not_found("Пользователь не найден.")
    if target["id"] == actor["id"]:
        raise conflict("Нельзя изменить собственную роль — так можно случайно остаться без администратора.")
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
