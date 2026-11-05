"""Проверка, что все шаблоны рендерятся на реальных данных (без веб-сервера)."""
import unittest

import jinja2

from app import config, filters
from app.services import books, copies, loans, reading, reviews, users
from tests.helpers import make_conn


class TemplateRenderTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn(with_seed=True)
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(config.TEMPLATES_DIR)), autoescape=True)
        filters.install(self.env)
        self.base = {"flash": None, "page_url": lambda n: f"?page={n}", "current_path": "/books", "request": None}

    def render(self, name, **ctx):
        return self.env.get_template(name).render({**self.base, **ctx})

    def test_all_pages_render(self):
        c = self.conn
        anna = users.get_user(c, 3)
        admin = users.get_user(c, 1)
        out = {}
        out["login"] = self.render("login.html", user=None, values={}, errors={"password": "Неверный"}, next="")
        out["register"] = self.render("register.html", user=None, values={}, errors={})
        out["profile"] = self.render("profile.html", user=anna, values=anna, errors={})
        out["error"] = self.render("error.html", user=anna, code=409, title="Действие невозможно", message="тест")
        out["catalog"] = self.render("catalog.html", user=anna, pg=books.list_books(c, per_page=5), q="", genre="",
                                     only_available=False, genres=books.genres(c))
        out["catalog_empty"] = self.render("catalog.html", user=anna, pg=books.list_books(c, q="zzz"), q="zzz",
                                           genre="", only_available=False, genres=books.genres(c))
        out["book"] = self.render("book.html", user=anna, book=books.get_book(c, 1),
                                  copies=books.book_copies(c, 1, anna["id"]), pg=reviews.list_for_book(c, 1),
                                  my_review=reviews.get_user_review(c, 3, 6), my_reading=reading.get_entry(c, 3, 6),
                                  review_values=None, review_errors={}, loan_error=None)
        out["book_err"] = self.render("book.html", user=anna, book=books.get_book(c, 1),
                                      copies=books.book_copies(c, 1, anna["id"]), pg=reviews.list_for_book(c, 1),
                                      my_review=None, my_reading=None, review_values={"score": "9", "text": ""},
                                      review_errors={"score": "Поставьте оценку от 1 до 5."},
                                      loan_error={"copy_id": 2, "message": "Дата в прошлом", "value": ""})
        out["shelf"] = self.render("shelf.html", user=anna, pg=copies.shelf(c, 3),
                                   book_options=[(b["id"], b["title"]) for b in books.all_books_brief(c)],
                                   values={}, errors={})
        out["copy_form"] = self.render("copy_form.html", user=anna, copy=copies.get_owned(c, 1, anna),
                                       values=copies.get_owned(c, 1, anna), errors={})
        for direction, uid in (("incoming", 3), ("outgoing", 3), ("incoming", 5)):
            u = users.get_user(c, uid)
            out[f"loans_{direction}_{uid}"] = self.render(
                "loans.html", user=u, direction=direction, flt="all",
                pg=loans.list_loans(c, uid, direction, "all"))
        out["reading"] = self.render("reading.html", user=anna, status="", pg=reading.list_entries(c, 3),
                                     stats=reading.stats(c, 3))
        out["mod_books"] = self.render("mod_books.html", user=admin, tab="books", q="", values={}, errors={},
                                       pg=books.list_books(c, per_page=5))
        out["mod_form"] = self.render("mod_book_form.html", user=admin, tab="books", book=books.get_book(c, 1),
                                      values=books.get_book(c, 1), errors={})
        out["mod_reviews"] = self.render("mod_reviews.html", user=admin, tab="reviews", only_hidden=False,
                                         pg=reviews.list_for_moderation(c))
        out["admin_users"] = self.render("admin_users.html", user=admin, tab="users", pg=users.list_users(c))
        for name, html in out.items():
            self.assertIn("</html>", html, name)

        # содержательные проверки
        self.assertIn("Неверный", out["login"])
        self.assertIn("Ничего не найдено", out["catalog_empty"])
        self.assertIn("Поставьте оценку", out["book_err"])
        self.assertIn("Просрочено", out["loans_outgoing_3"])
        self.assertIn("Принять", out["loans_incoming_5"])
        self.assertIn("Модерация", out["mod_books"])
        self.assertNotIn("Роли", out["catalog"])         # участник не видит пункт «Роли»


if __name__ == "__main__":
    unittest.main()
