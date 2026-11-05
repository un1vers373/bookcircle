import sqlite3
from pathlib import Path

covers = Path("app/static/covers")
conn = sqlite3.connect("bookcircle.db")
for f in covers.iterdir():
    if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and f.stem.isdigit():
        conn.execute("UPDATE books SET cover_url=? WHERE id=?",
                     (f"/static/covers/{f.name}", int(f.stem)))
        print("ок:", f.name)
conn.commit()