"""Демо-данные: 15 книг, 20 экземпляров, 5 пользователей, 10 передач, 10 отзывов."""
from datetime import timedelta

from app.security import hash_password
from app.util import now_iso, today

DEMO_PASSWORD = "demo12345"

USERS = [  # id по порядку 1..5
    ("admin@bookcircle.local", "Админ Админов", "admin"),
    ("moder@bookcircle.local", "Мария Модераторова", "moderator"),
    ("anna@bookcircle.local", "Анна Иванова", "user"),
    ("boris@bookcircle.local", "Борис Петров", "user"),
    ("clara@bookcircle.local", "Клара Смирнова", "user"),
]

BOOKS = [  # id по порядку 1..15 (описания авторские, краткие)
    ("Мастер и Маргарита", "Михаил Булгаков", "Роман",
     "Дьявол приезжает в Москву 1930-х, а параллельно разворачивается история Понтия Пилата."),
    ("Преступление и наказание", "Фёдор Достоевский", "Роман",
     "Бедный студент решается на преступление и мучительно переживает его последствия."),
    ("Война и мир", "Лев Толстой", "Роман",
     "Судьбы нескольких семей на фоне наполеоновских войн."),
    ("Евгений Онегин", "Александр Пушкин", "Поэзия",
     "Роман в стихах о столичном дворянине, любви и упущенных возможностях."),
    ("Герой нашего времени", "Михаил Лермонтов", "Роман",
     "Портрет Печорина — умного и скучающего офицера на Кавказе."),
    ("1984", "Джордж Оруэлл", "Антиутопия",
     "Тоталитарное государство контролирует мысли и язык, а герой пытается сохранить собственное мнение."),
    ("Скотный двор", "Джордж Оруэлл", "Антиутопия",
     "Животные поднимают восстание на ферме, но равенство постепенно исчезает."),
    ("451 градус по Фаренгейту", "Рэй Брэдбери", "Фантастика",
     "В обществе, где книги сжигают, пожарный начинает сомневаться в своей работе."),
    ("Солярис", "Станислав Лем", "Фантастика",
     "Учёные изучают мыслящий океан, который отвечает им странным образом."),
    ("Хоббит", "Джон Р. Р. Толкин", "Фэнтези",
     "Скромный хоббит отправляется с гномами за сокровищами дракона."),
    ("Маленький принц", "Антуан де Сент-Экзюпери", "Сказка",
     "Лётчик в пустыне встречает мальчика с далёкой планеты."),
    ("Собачье сердце", "Михаил Булгаков", "Сатира",
     "Профессор превращает бродячего пса в человека — с непредвиденными результатами."),
    ("Три товарища", "Эрих Мария Ремарк", "Роман",
     "Дружба и любовь в Германии между двумя войнами."),
    ("Краткая история времени", "Стивен Хокинг", "Научпоп",
     "Популярный рассказ о Вселенной, чёрных дырах и природе времени."),
    ("Этюд в багровых тонах", "Артур Конан Дойл", "Детектив",
     "Первое дело Шерлока Холмса и доктора Ватсона."),
]

COPIES = [  # (книга, владелец, состояние, место, активен) — id по порядку 1..20
    (1, 3, "good", "Корпус А, вахта", 1),
    (1, 4, "fair", "Общежитие №2, холл", 1),
    (2, 3, "good", "Корпус А, вахта", 1),
    (3, 5, "worn", "Библиотека, у входа", 1),
    (4, 4, "new", "Общежитие №2, холл", 1),
    (5, 5, "good", "Библиотека, у входа", 1),
    (6, 3, "good", "Корпус А, вахта", 1),
    (6, 2, "fair", "Кафедра, каб. 214", 1),
    (7, 4, "good", "Общежитие №2, холл", 1),
    (8, 5, "new", "Библиотека, у входа", 1),
    (9, 3, "fair", "Корпус А, вахта", 1),
    (10, 4, "good", "Общежитие №2, холл", 1),
    (11, 5, "new", "Библиотека, у входа", 1),
    (12, 2, "good", "Кафедра, каб. 214", 1),
    (13, 3, "worn", "Корпус А, вахта", 1),
    (14, 4, "good", "Общежитие №2, холл", 1),
    (15, 5, "fair", "Библиотека, у входа", 1),
    (2, 2, "good", "Кафедра, каб. 214", 1),
    (10, 3, "good", "Корпус А, вахта", 1),
    (3, 4, "fair", "Общежитие №2, холл", 0),  # скрыт владельцем
]

# (экземпляр, заёмщик, статус, дней до срока от сегодня, дней назад выдано, дней назад возвращено)
LOANS = [
    (1, 4, "returned", -28, 40, 26),
    (3, 5, "returned", -21, 35, 20),
    (4, 3, "returned", -14, 30, 12),
    (5, 2, "returned", -7, 20, 6),
    (7, 5, "handed_over", 4, 10, None),
    (9, 3, "handed_over", -5, 25, None),   # просрочена
    (2, 3, "accepted", 10, None, None),
    (6, 4, "pending", 14, None, None),
    (6, 2, "pending", 7, None, None),
    (10, 4, "rejected", 5, None, None),
]

REVIEWS = [  # (пользователь, книга, оценка, текст, скрыт)
    (4, 1, 5, "Перечитываю каждый год. Москва и Воланд — незабываемо.", 0),
    (5, 1, 4, "Сильная книга, но линия Пилата мне понравилась больше сатирической.", 0),
    (3, 2, 5, "Тяжело, но очень точно про совесть и ответственность.", 0),
    (5, 2, 4, "Читается медленно, зато остаётся надолго.", 0),
    (4, 6, 5, "Пугающе актуально. Лучше читать не на ночь.", 0),
    (3, 6, 1, "Реклама, переходите по ссылке и покупайте дёшево!", 1),
    (2, 9, 4, "Больше философия, чем фантастика. Мне понравилось.", 0),
    (3, 10, 5, "Уютное приключение, хорошо подходит для отдыха.", 0),
    (5, 11, 5, "Короткая книга, которую хочется цитировать.", 0),
    (4, 14, 4, "Сложные вещи объяснены понятно, местами нужно перечитывать.", 0),
]

READING = [  # (пользователь, книга, статус, дней назад завершено)
    (3, 3, "done", 40), (3, 6, "done", 0), (3, 10, "reading", None),
    (4, 1, "done", 1), (4, 6, "done", 0), (4, 14, "want", None),
    (5, 1, "done", 45), (5, 11, "done", 0), (5, 2, "reading", None),
    (2, 9, "done", 2), (2, 8, "want", None), (3, 2, "done", 60),
]


def seed(conn):
    if conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]:
        raise RuntimeError("База уже содержит данные. Используйте `python manage.py reset`.")
    now, t = now_iso(), today()
    pw = hash_password(DEMO_PASSWORD)
    conn.execute("BEGIN IMMEDIATE")
    try:
        for email, name, role in USERS:
            conn.execute("INSERT INTO users (email, display_name, password_hash, role, created_at) "
                         "VALUES (?,?,?,?,?)", (email, name, pw, role, now))
        for title, author, genre, desc in BOOKS:
            conn.execute(
                "INSERT INTO books (title, author, genre, description, cover_url, title_key, search_key, created_at) "
                "VALUES (?,?,?,?,NULL,?,?,?)",
                (title, author, genre, desc, title.casefold(), f"{title} {author}".casefold(), now))
        for book, owner, cond, place, active in COPIES:
            conn.execute("INSERT INTO copies (book_id, owner_id, condition, pickup_place, is_active, created_at) "
                         "VALUES (?,?,?,?,?,?)", (book, owner, cond, place, active, now))
        for copy, borrower, status, due, handed, returned in LOANS:
            conn.execute(
                "INSERT INTO loans (copy_id, borrower_id, requested_return_date, status, created_at, handed_at, returned_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (copy, borrower, (t + timedelta(days=due)).isoformat(), status, now,
                 (t - timedelta(days=handed)).isoformat() if handed else None,
                 (t - timedelta(days=returned)).isoformat() if returned else None))
        for user, book, score, text, hidden in REVIEWS:
            conn.execute("INSERT INTO reviews (user_id, book_id, score, text, is_hidden, created_at, updated_at) "
                         "VALUES (?,?,?,?,?,?,?)", (user, book, score, text, hidden, now, now))
        for user, book, status, ago in READING:
            finished = (t - timedelta(days=ago)).isoformat() if status == "done" else None
            conn.execute("INSERT INTO reading_entries (user_id, book_id, status, finished_at) VALUES (?,?,?,?)",
                         (user, book, status, finished))
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
