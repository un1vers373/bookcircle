"""Зависимости FastAPI: соединение с БД, текущий пользователь, проверка ролей."""
from fastapi import Depends, Request

from app import db
from app.errors import AppError, NotAuthenticated
from app.services import users


def get_conn():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def require_user(request: Request, conn=Depends(get_conn)):
    """Права всегда проверяются на сервере: нет сессии — 401 (редирект на вход)."""
    uid = request.session.get("uid")
    user = users.get_user(conn, uid) if uid else None
    if user is None:
        request.session.clear()
        raise NotAuthenticated()
    return user


def require_roles(*roles):
    def checker(user=Depends(require_user)):
        if user["role"] not in roles:
            raise AppError(403, "У вас нет доступа к этому разделу.")
        return user
    return checker


require_moderator = require_roles("moderator", "admin")
require_admin = require_roles("admin")
