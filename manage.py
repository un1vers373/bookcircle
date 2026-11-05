"""Команды управления: python manage.py <команда>

  migrate       применить миграции
  seed          наполнить демо-данными (на пустой базе)
  setup         migrate + seed
  reset         удалить базу и выполнить setup заново
  createadmin   создать администратора: createadmin EMAIL ИМЯ ПАРОЛЬ
  run           запустить сервер (http://127.0.0.1:8000)
"""
import os
import sys

from app import config, db


def _cmd_migrate():
    conn = db.connect()
    applied = db.migrate(conn)
    print("Применено миграций:", ", ".join(applied) if applied else "нет новых")


def _cmd_seed():
    from app.seed import DEMO_PASSWORD, seed
    conn = db.connect()
    db.migrate(conn)
    seed(conn)
    print("Демо-данные добавлены. Пароль у всех демо-аккаунтов:", DEMO_PASSWORD)


def _cmd_reset():
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(config.DB_PATH + suffix)
        except FileNotFoundError:
            pass
    _cmd_seed()


def _cmd_createadmin(args):
    from app.services import users
    if len(args) != 3:
        sys.exit("Использование: python manage.py createadmin EMAIL ИМЯ ПАРОЛЬ")
    conn = db.connect()
    db.migrate(conn)
    users.register(conn, args[0], args[1], args[2], args[2], role="admin")
    print("Администратор создан:", args[0])


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "migrate":
        _cmd_migrate()
    elif cmd == "seed":
        _cmd_seed()
    elif cmd == "setup":
        _cmd_migrate()
        _cmd_seed()
    elif cmd == "reset":
        _cmd_reset()
    elif cmd == "createadmin":
        _cmd_createadmin(args)
    elif cmd == "run":
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
