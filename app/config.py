"""Настройки приложения. Можно переопределить через переменные окружения."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
MIGRATIONS_DIR = BASE_DIR / "migrations"

DB_PATH = os.environ.get("BOOKCIRCLE_DB", str(BASE_DIR / "bookcircle.db"))
SECRET_KEY = os.environ.get("BOOKCIRCLE_SECRET", "dev-secret-change-me-before-production")

PER_PAGE = 8
