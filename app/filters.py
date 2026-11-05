"""Фильтры и глобальные значения Jinja (без зависимости от FastAPI — удобно для тестов)."""
from datetime import date

from app.services import copies, loans, reading, users


def date_ru(value):
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return value or "—"


def install(env):
    env.filters["date_ru"] = date_ru
    env.globals.update(
        LOAN_STATUS=loans.STATUSES,
        READING_STATUS=reading.STATUSES,
        CONDITIONS=copies.CONDITIONS,
        ROLES=users.ROLES,
    )
