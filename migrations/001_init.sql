-- BookCircle: начальная схема

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'moderator', 'admin')),
    created_at    TEXT NOT NULL
);

CREATE TABLE books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    author      TEXT NOT NULL,
    genre       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    cover_url   TEXT,
    title_key   TEXT NOT NULL,            -- название в нижнем регистре (сортировка)
    search_key  TEXT NOT NULL UNIQUE,     -- «название автор» в нижнем регистре (поиск + защита от дублей)
    created_at  TEXT NOT NULL
);
CREATE INDEX ix_books_title_key ON books (title_key);
CREATE INDEX ix_books_genre     ON books (genre);

CREATE TABLE copies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id      INTEGER NOT NULL REFERENCES books (id) ON DELETE RESTRICT,
    owner_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    condition    TEXT NOT NULL CHECK (condition IN ('new', 'good', 'fair', 'worn')),
    pickup_place TEXT NOT NULL,
    is_active    INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at   TEXT NOT NULL
);
CREATE INDEX ix_copies_book  ON copies (book_id, is_active);
CREATE INDEX ix_copies_owner ON copies (owner_id);

CREATE TABLE loans (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    copy_id               INTEGER NOT NULL REFERENCES copies (id) ON DELETE RESTRICT,
    borrower_id           INTEGER NOT NULL REFERENCES users (id)  ON DELETE RESTRICT,
    requested_return_date TEXT NOT NULL
        CHECK (requested_return_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    status                TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'handed_over', 'returned', 'rejected', 'cancelled')),
    created_at            TEXT NOT NULL,
    handed_at             TEXT,
    returned_at           TEXT
);
CREATE INDEX ix_loans_copy     ON loans (copy_id, status);
CREATE INDEX ix_loans_borrower ON loans (borrower_id, status);

-- Главная гарантия: на один экземпляр не больше одной принятой/активной передачи.
CREATE UNIQUE INDEX ux_loans_one_active_per_copy
    ON loans (copy_id) WHERE status IN ('accepted', 'handed_over');
-- Один заёмщик не может подать два ожидающих запроса на один экземпляр.
CREATE UNIQUE INDEX ux_loans_one_pending_per_borrower
    ON loans (copy_id, borrower_id) WHERE status = 'pending';

-- Владелец не одалживает книгу себе (на уровне БД).
CREATE TRIGGER trg_loans_no_self_loan
BEFORE INSERT ON loans
WHEN NEW.borrower_id = (SELECT owner_id FROM copies WHERE id = NEW.copy_id)
BEGIN
    SELECT RAISE(ABORT, 'owner cannot borrow own copy');
END;

CREATE TABLE reading_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    book_id     INTEGER NOT NULL REFERENCES books (id) ON DELETE RESTRICT,
    status      TEXT NOT NULL CHECK (status IN ('want', 'reading', 'done')),
    finished_at TEXT,
    UNIQUE (user_id, book_id),
    CHECK (status = 'done' OR finished_at IS NULL)
);
CREATE INDEX ix_reading_user ON reading_entries (user_id, status);
CREATE INDEX ix_reading_book ON reading_entries (book_id, status, finished_at);

CREATE TABLE reviews (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    book_id    INTEGER NOT NULL REFERENCES books (id) ON DELETE RESTRICT,
    score      INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    text       TEXT NOT NULL,
    is_hidden  INTEGER NOT NULL DEFAULT 0 CHECK (is_hidden IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, book_id)
);
CREATE INDEX ix_reviews_book ON reviews (book_id, is_hidden);
