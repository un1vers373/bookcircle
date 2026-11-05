"""Тесты бизнес-логики (без веб-сервера): python -m unittest discover -s tests -v"""
import sqlite3
import unittest
from datetime import timedelta

from app import util
from app.errors import AppError, ValidationFailed
from app.services import books, copies, loans, reading, reviews, users
from tests.helpers import add_book, add_copy, add_user, make_conn


def future(days=7):
    return (util.today() + timedelta(days=days)).isoformat()


class LoanFlowTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()
        self.owner1 = add_user(self.conn, "owner1")
        self.owner2 = add_user(self.conn, "owner2")
        self.bob = add_user(self.conn, "bob")
        self.carl = add_user(self.conn, "carl")
        self.book = add_book(self.conn)
        self.copy1 = add_copy(self.conn, self.owner1, self.book)
        self.copy2 = add_copy(self.conn, self.owner2, self.book)

    def status(self, loan_id):
        return self.conn.execute("SELECT status FROM loans WHERE id=?", (loan_id,)).fetchone()["status"]

    def available(self):
        return books.get_book(self.conn, self.book)["available_count"]

    def test_two_copies_are_booked_independently(self):
        l1 = loans.request_loan(self.conn, self.bob, self.copy1, future())
        loans.apply_action(self.conn, self.owner1, l1, "accept")
        self.assertEqual(self.available(), 1)             # второй экземпляр свободен
        l2 = loans.request_loan(self.conn, self.bob, self.copy2, future())
        loans.apply_action(self.conn, self.owner2, l2, "accept")
        self.assertEqual(self.available(), 0)

    def test_full_cycle_restores_availability(self):
        lid = loans.request_loan(self.conn, self.bob, self.copy1, future())
        loans.apply_action(self.conn, self.owner1, lid, "accept")
        self.assertEqual(self.available(), 1)
        loans.apply_action(self.conn, self.owner1, lid, "hand-over")
        self.assertEqual(self.status(lid), "handed_over")
        loans.apply_action(self.conn, self.owner1, lid, "return")
        self.assertEqual(self.status(lid), "returned")
        self.assertEqual(self.available(), 2)

    def test_cannot_accept_two_borrowers(self):
        a = loans.request_loan(self.conn, self.bob, self.copy1, future())
        b = loans.request_loan(self.conn, self.carl, self.copy1, future())
        loans.apply_action(self.conn, self.owner1, a, "accept")
        self.assertEqual(self.status(b), "rejected")       # остальные отклонены автоматически
        with self.assertRaises(AppError) as cm:
            loans.apply_action(self.conn, self.owner1, b, "accept")
        self.assertEqual(cm.exception.status, 409)

    def test_database_blocks_second_active_loan(self):
        a = loans.request_loan(self.conn, self.bob, self.copy1, future())
        loans.apply_action(self.conn, self.owner1, a, "accept")
        with self.assertRaises(sqlite3.IntegrityError):    # защита на уровне БД
            self.conn.execute("INSERT INTO loans (copy_id, borrower_id, requested_return_date, status, created_at) "
                              "VALUES (?,?,?,'accepted','x')", (self.copy1, self.carl["id"], future()))

    def test_owner_cannot_borrow_own_copy(self):
        with self.assertRaises(AppError) as cm:
            loans.request_loan(self.conn, self.owner1, self.copy1, future())
        self.assertEqual(cm.exception.status, 403)
        with self.assertRaises(sqlite3.IntegrityError):    # и триггер в БД
            self.conn.execute("INSERT INTO loans (copy_id, borrower_id, requested_return_date, status, created_at) "
                              "VALUES (?,?,?,'pending','x')", (self.copy1, self.owner1["id"], future()))

    def test_forbidden_transitions_give_409(self):
        lid = loans.request_loan(self.conn, self.bob, self.copy1, future())
        for action in ("hand-over", "return"):              # из «ожидает» нельзя
            with self.assertRaises(AppError) as cm:
                loans.apply_action(self.conn, self.owner1, lid, action)
            self.assertEqual(cm.exception.status, 409)
        loans.apply_action(self.conn, self.owner1, lid, "accept")
        with self.assertRaises(AppError) as cm:             # принять дважды
            loans.apply_action(self.conn, self.owner1, lid, "accept")
        self.assertEqual(cm.exception.status, 409)
        loans.apply_action(self.conn, self.owner1, lid, "hand-over")
        with self.assertRaises(AppError) as cm:             # из «передана» отменить нельзя
            loans.apply_action(self.conn, self.bob, lid, "cancel")
        self.assertEqual(cm.exception.status, 409)
        loans.apply_action(self.conn, self.owner1, lid, "return")
        with self.assertRaises(AppError) as cm:             # из «возвращена» дальше нельзя
            loans.apply_action(self.conn, self.owner1, lid, "return")
        self.assertEqual(cm.exception.status, 409)

    def test_permissions_are_checked(self):
        lid = loans.request_loan(self.conn, self.bob, self.copy1, future())
        for who in (self.bob, self.carl, self.owner2):      # принимать может только владелец
            with self.assertRaises(AppError) as cm:
                loans.apply_action(self.conn, who, lid, "accept")
            self.assertEqual(cm.exception.status, 403)
        with self.assertRaises(AppError) as cm:             # чужую заявку отменить нельзя
            loans.apply_action(self.conn, self.carl, lid, "cancel")
        self.assertEqual(cm.exception.status, 403)
        loans.apply_action(self.conn, self.bob, lid, "cancel")
        self.assertEqual(self.status(lid), "cancelled")
        with self.assertRaises(AppError) as cm:
            loans.apply_action(self.conn, self.bob, 9999, "cancel")
        self.assertEqual(cm.exception.status, 404)

    def test_request_validation(self):
        for bad in ("", "вчера", (util.today() - timedelta(days=1)).isoformat(), future(1000)):
            with self.assertRaises(ValidationFailed):
                loans.request_loan(self.conn, self.bob, self.copy1, bad)
        loans.request_loan(self.conn, self.bob, self.copy1, future())
        with self.assertRaises(AppError) as cm:             # дубль запроса
            loans.request_loan(self.conn, self.bob, self.copy1, future())
        self.assertEqual(cm.exception.status, 409)

    def test_cannot_request_busy_copy(self):
        a = loans.request_loan(self.conn, self.bob, self.copy1, future())
        loans.apply_action(self.conn, self.owner1, a, "accept")
        with self.assertRaises(AppError) as cm:
            loans.request_loan(self.conn, self.carl, self.copy1, future())
        self.assertEqual(cm.exception.status, 409)

    def test_cannot_hide_or_delete_lent_copy(self):
        lid = loans.request_loan(self.conn, self.bob, self.copy1, future())
        loans.apply_action(self.conn, self.owner1, lid, "accept")
        loans.apply_action(self.conn, self.owner1, lid, "hand-over")
        with self.assertRaises(AppError) as cm:
            copies.set_active(self.conn, self.copy1, self.owner1, False)
        self.assertEqual(cm.exception.status, 409)
        with self.assertRaises(AppError) as cm:
            copies.delete_copy(self.conn, self.copy1, self.owner1)
        self.assertEqual(cm.exception.status, 409)
        loans.apply_action(self.conn, self.owner1, lid, "return")
        with self.assertRaises(AppError):                   # есть история — удалять нельзя
            copies.delete_copy(self.conn, self.copy1, self.owner1)
        copies.set_active(self.conn, self.copy1, self.owner1, False)   # а скрыть можно
        self.assertEqual(self.available(), 1)

    def test_only_owner_manages_copy(self):
        with self.assertRaises(AppError) as cm:
            copies.set_active(self.conn, self.copy1, self.bob, False)
        self.assertEqual(cm.exception.status, 403)

    def test_overdue_is_computed(self):
        lid = loans.request_loan(self.conn, self.bob, self.copy1, future(1))
        loans.apply_action(self.conn, self.owner1, lid, "accept")
        loans.apply_action(self.conn, self.owner1, lid, "hand-over")
        self.assertFalse(loans.list_loans(self.conn, self.bob["id"], "outgoing").items[0]["overdue"])
        self.conn.execute("UPDATE loans SET requested_return_date = ? WHERE id = ?",
                          ((util.today() - timedelta(days=1)).isoformat(), lid))
        self.assertTrue(loans.list_loans(self.conn, self.bob["id"], "outgoing").items[0]["overdue"])


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()
        self.a, self.b = add_user(self.conn, "a"), add_user(self.conn, "b")
        self.mod = add_user(self.conn, "mod", "moderator")
        self.book = add_book(self.conn)

    def rating(self):
        b = books.get_book(self.conn, self.book)
        return b["avg_rating"], b["reviews_count"]

    def test_edit_changes_rating_without_duplicate(self):
        reviews.upsert_review(self.conn, self.a["id"], self.book, 5, "Отлично")
        reviews.upsert_review(self.conn, self.b["id"], self.book, 3, "Нормально")
        self.assertEqual(self.rating(), (4.0, 2))
        created = reviews.upsert_review(self.conn, self.b["id"], self.book, 1, "Передумал")
        self.assertFalse(created)
        self.assertEqual(self.rating(), (3.0, 2))
        n = self.conn.execute("SELECT COUNT(*) AS n FROM reviews").fetchone()["n"]
        self.assertEqual(n, 2)

    def test_hidden_review_excluded_from_rating(self):
        reviews.upsert_review(self.conn, self.a["id"], self.book, 5, "Отлично")
        reviews.upsert_review(self.conn, self.b["id"], self.book, 1, "Спам")
        rid = reviews.get_user_review(self.conn, self.b["id"], self.book)["id"]
        reviews.set_hidden(self.conn, self.mod, rid, True)
        self.assertEqual(self.rating(), (5.0, 1))
        with self.assertRaises(AppError) as cm:             # обычный участник скрывать не может
            reviews.set_hidden(self.conn, self.a, rid, False)
        self.assertEqual(cm.exception.status, 403)

    def test_score_validation(self):
        for bad in (0, 6, "x", None):
            with self.assertRaises(ValidationFailed) as cm:
                reviews.upsert_review(self.conn, self.a["id"], self.book, bad, "текст")
            self.assertIn("score", cm.exception.fields)


class ReadingAndUsersTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()
        self.u = add_user(self.conn, "reader")
        self.book = add_book(self.conn)

    def test_one_entry_per_user_and_book(self):
        reading.set_entry(self.conn, self.u["id"], self.book, "want")
        reading.set_entry(self.conn, self.u["id"], self.book, "done", "")
        n = self.conn.execute("SELECT COUNT(*) AS n FROM reading_entries").fetchone()["n"]
        self.assertEqual(n, 1)
        e = reading.get_entry(self.conn, self.u["id"], self.book)
        self.assertEqual(e["finished_at"], util.today().isoformat())
        reading.set_entry(self.conn, self.u["id"], self.book, "reading")
        self.assertIsNone(reading.get_entry(self.conn, self.u["id"], self.book)["finished_at"])

    def test_month_statistic_uses_finished_at(self):
        b2 = add_book(self.conn, "Вторая")
        reading.set_entry(self.conn, self.u["id"], self.book, "done", util.today().isoformat())
        reading.set_entry(self.conn, self.u["id"], b2, "done", "2020-01-15")
        self.assertEqual(reading.stats(self.conn, self.u["id"])["month"], 1)
        self.assertEqual(books.get_book(self.conn, self.book)["read_month"], 1)
        self.assertEqual(books.get_book(self.conn, b2)["read_month"], 0)

    def test_reading_validation(self):
        with self.assertRaises(ValidationFailed):
            reading.set_entry(self.conn, self.u["id"], self.book, "wow")
        with self.assertRaises(ValidationFailed):
            reading.set_entry(self.conn, self.u["id"], self.book, "done", "2999-01-01")
        with self.assertRaises(AppError) as cm:
            reading.set_entry(self.conn, self.u["id"], 9999, "want")
        self.assertEqual(cm.exception.status, 404)

    def test_registration_and_login(self):
        with self.assertRaises(ValidationFailed) as cm:
            users.register(self.conn, "reader@t.local", "X", "short", "other")
        self.assertTrue({"email", "display_name", "password"} <= set(cm.exception.fields))
        uid = users.authenticate(self.conn, "READER@t.local", "password1")
        self.assertEqual(uid, self.u["id"])
        with self.assertRaises(ValidationFailed):
            users.authenticate(self.conn, "reader@t.local", "wrong-pass")

    def test_only_admin_assigns_roles(self):
        admin = add_user(self.conn, "boss", "admin")
        with self.assertRaises(AppError) as cm:
            users.set_role(self.conn, self.u, self.u["id"], "admin")
        self.assertEqual(cm.exception.status, 403)
        users.set_role(self.conn, admin, self.u["id"], "moderator")
        self.assertEqual(users.get_user(self.conn, self.u["id"])["role"], "moderator")
        with self.assertRaises(AppError) as cm:
            users.set_role(self.conn, admin, admin["id"], "user")
        self.assertEqual(cm.exception.status, 409)


class CatalogAndSeedTests(unittest.TestCase):
    def test_seed_counts_and_search(self):
        conn = make_conn(with_seed=True)
        count = lambda t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        self.assertEqual((count("books"), count("copies"), count("users"), count("loans"), count("reviews")),
                         (15, 20, 5, 10, 10))
        res = books.list_books(conn, q="БУЛГАКОВ")            # регистр не важен, в т.ч. для кириллицы
        self.assertEqual({b["title"] for b in res.items}, {"Мастер и Маргарита", "Собачье сердце"})
        self.assertEqual(books.list_books(conn, genre="Антиутопия").total, 2)
        self.assertEqual(books.list_books(conn, per_page=4).pages, 4)
        self.assertEqual(books.list_books(conn, q="%").total, 0)   # спецсимволы LIKE экранируются
        b1 = books.get_book(conn, 1)
        self.assertEqual(b1["copies_count"], 2)
        self.assertEqual(b1["available_count"], 1)             # один экземпляр принят, второй свободен
        self.assertEqual(books.get_book(conn, 6)["avg_rating"], 5.0)   # скрытый отзыв не считается


if __name__ == "__main__":
    unittest.main()
