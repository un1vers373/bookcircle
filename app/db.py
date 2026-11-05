"""Работа с SQLite: соединение, транзакции, миграции."""
import sqlite3
from contextlib import contextmanager

from app import config


def _dict_factory(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def connect(path: str | None = None) -> sqlite3.Connection:
    # isolation_level=None — автокоммит; транзакции открываем явно через tx()
    conn = sqlite3.connect(path or config.DB_PATH, isolation_level=None,
                           check_same_thread=False, timeout=5)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def tx(conn: sqlite3.Connection):
    """BEGIN IMMEDIATE берёт блокировку записи сразу — проверки и изменения атомарны."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Применяет файлы migrations/*.sql по порядку. Возвращает список применённых."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                 "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    done = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
    applied = []
    for path in sorted(config.MIGRATIONS_DIR.glob("*.sql")):
        if path.name in done:
            continue
        sql = path.read_text(encoding="utf-8")
        conn.executescript(
            "BEGIN;\n" + sql + "\n"
            f"INSERT INTO schema_migrations(version, applied_at) VALUES ('{path.name}', datetime('now'));\n"
            "COMMIT;"
        )
        applied.append(path.name)
    return applied
