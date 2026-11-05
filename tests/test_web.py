"""Сквозные тесты через HTTP (нужны fastapi, httpx, python-multipart).
Запуск: python -m unittest tests.test_web -v"""
import sqlite3
import unittest
from datetime import timedelta

try:
    from fastapi.testclient import TestClient
    HAVE_WEB = True
except ImportError:          # веб-зависимости не установлены
    HAVE_WEB = False

from app import util
from tests.helpers import make_conn


def login(client, email):
    r = client.post("/login", data={"email": email, "password": "demo12345"}, follow_redirects=False)
    assert r.status_code == 303, r.text
    return client


@unittest.skipUnless(HAVE_WEB, "не установлены веб-зависимости")
class WebTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn(with_seed=True)       # создаёт временную БД и выставляет config.DB_PATH
        from app.main import app
        self.app = app
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.close()

    def client(self, email=None):
        c = TestClient(self.app)
        self.clients.append(c)
        return login(c, email) if email else c

    def test_anonymous_is_redirected_to_login(self):
        r = self.client().get("/books", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/login?next="))

    def test_roles_are_enforced_on_server(self):
        self.assertEqual(self.client("anna@bookcircle.local").get("/moderation/books").status_code, 403)
        self.assertEqual(self.client("anna@bookcircle.local").get("/admin/users").status_code, 403)
        self.assertEqual(self.client("moder@bookcircle.local").get("/moderation/books").status_code, 200)
        self.assertEqual(self.client("moder@bookcircle.local").get("/admin/users").status_code, 403)
        self.assertEqual(self.client("admin@bookcircle.local").get("/admin/users").status_code, 200)
        r = self.client("anna@bookcircle.local").post("/moderation/reviews/1/hide", follow_redirects=False)
        self.assertEqual(r.status_code, 403)

    def test_404_page_and_wrong_owner(self):
        c = self.client("anna@bookcircle.local")
        self.assertEqual(c.get("/books/9999").status_code, 404)
        self.assertEqual(c.get("/nope").status_code, 404)
        self.assertEqual(c.get("/copies/2/edit").status_code, 403)     # чужой экземпляр

    def test_form_errors_are_shown_at_fields(self):
        r = self.client().post("/register", data={"email": "bad", "display_name": "A",
                                                  "password": "1", "password2": "2"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Введите корректный email", r.text)
        self.assertIn("не короче 8 символов", r.text)

    def test_loan_flow_through_interface(self):
        due = (util.today() + timedelta(days=7)).isoformat()
        boris = self.client("boris@bookcircle.local")
        r = boris.post("/copies/1/loans", data={"requested_return_date": due}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        loan_id = self.conn.execute("SELECT MAX(id) AS i FROM loans").fetchone()["i"]
        self.assertEqual(self.client("clara@bookcircle.local").post(f"/loans/{loan_id}/accept").status_code, 403)
        anna = self.client("anna@bookcircle.local")
        for action in ("accept", "hand-over", "return"):
            self.assertEqual(anna.post(f"/loans/{loan_id}/{action}", follow_redirects=False).status_code, 303)
        r = anna.post(f"/loans/{loan_id}/return", follow_redirects=False)
        self.assertEqual(r.status_code, 409)
        self.assertIn("статусе", r.text)

    def test_put_routes_and_review_upsert(self):
        c = self.client("clara@bookcircle.local")
        r = c.put("/reading/3", data={"status": "reading"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        c.put("/books/3/review", data={"score": "5", "text": "Первый"}, follow_redirects=False)
        c.put("/books/3/review", data={"score": "2", "text": "Второй"}, follow_redirects=False)
        n = self.conn.execute("SELECT COUNT(*) AS n FROM reviews WHERE user_id=5 AND book_id=3").fetchone()["n"]
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
