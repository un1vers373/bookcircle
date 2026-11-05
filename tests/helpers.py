import os
import tempfile

from app import config, db
from app.seed import seed
from app.services import users


def make_conn(with_seed=False):
    """Чистая база во временном файле: миграции (+ демо-данные)."""
    path = os.path.join(tempfile.mkdtemp(), "test.db")
    config.DB_PATH = path
    conn = db.connect(path)
    db.migrate(conn)
    if with_seed:
        seed(conn)
    return conn


def add_user(conn, name, role="user"):
    uid = users.register(conn, f"{name}@t.local", f"User {name}", "password1", "password1", role=role)
    return users.get_user(conn, uid)


def add_book(conn, title="Книга", author="Автор"):
    from app.services import books
    return books.create_book(conn, {"title": title, "author": author, "genre": "Роман"})


def add_copy(conn, owner, book_id):
    from app.services import copies
    return copies.add_copy(conn, owner["id"], book_id, "good", "Вахта")
