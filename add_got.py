"""Добавляет в каталог книгу «Игра престолов». Больше ничего не меняет.
 
Запуск из папки проекта (рядом с manage.py), при остановленном сервере:
    python add_got.py
"""
from app import db
from app.services import books
 
conn = db.connect()
db.migrate(conn)
book_id = books.create_book(conn, {
    "title": "Игра престолов",
    "author": "Джордж Р. Р. Мартин",
    "genre": "Фэнтези",
    "description": "Первая книга цикла «Песнь льда и пламени». Знатные дома Вестероса "
                   "борются за Железный трон, пока на севере просыпается древняя угроза.",
    "cover_url": "/static/covers/got.jpg",
})
conn.close()
print("Книга добавлена, id =", book_id)
