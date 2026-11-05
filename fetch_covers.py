import json
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

BOOKS = {
    1: "The Master and Margarita Bulgakov",
    2: "Crime and Punishment Dostoevsky",
    3: "War and Peace Tolstoy",
    4: "Eugene Onegin Pushkin",
    5: "A Hero of Our Time Lermontov",
    6: "Nineteen Eighty-Four Orwell",
    7: "Animal Farm Orwell",
    8: "Fahrenheit 451 Bradbury",
    9: "Solaris Lem",
    10: "The Hobbit Tolkien",
    11: "The Little Prince Saint-Exupery",
    12: "Heart of a Dog Bulgakov",
    13: "Three Comrades Remarque",
    14: "A Brief History of Time Hawking",
    15: "A Study in Scarlet Conan Doyle",
}

HEADERS = {"User-Agent": "bookcircle-student-project"}
out = Path("app/static/covers")
out.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect("bookcircle.db")


def get(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers=HEADERS)
    with opener.open(req, timeout=30) as r:
        return r.read()


for book_id, query in BOOKS.items():
    target = out / f"{book_id}.jpg"
    try:
        if not target.exists():
            url = "https://openlibrary.org/search.json?limit=10&fields=title,cover_i&q=" + urllib.parse.quote(query)
            docs = json.loads(get(url))["docs"]
            cover_id = next((d["cover_i"] for d in docs if d.get("cover_i")), None)
            if not cover_id:
                print("не найдено:", book_id, query)
                continue
            data = get(f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg")
            target.write_bytes(data)
        conn.execute("UPDATE books SET cover_url=? WHERE id=?",
                     (f"/static/covers/{book_id}.jpg", book_id))
        print("ок:", book_id, query)
    except Exception as e:
        print("ошибка:", book_id, query, e)

conn.commit()