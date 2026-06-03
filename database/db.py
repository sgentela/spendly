import os
import sqlite3

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'spendly.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );
    """)
    conn.close()


def seed_db():
    conn = get_db()

    row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    if row[0] > 0:
        conn.close()
        return

    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    user_id = cursor.lastrowid

    expenses = [
        (user_id, 12.50,  "Food",          "2026-06-01", "Lunch"),
        (user_id, 35.00,  "Transport",     "2026-06-02", "Monthly bus pass"),
        (user_id, 120.00, "Bills",         "2026-06-03", "Electricity bill"),
        (user_id, 45.00,  "Health",        "2026-06-05", "Pharmacy"),
        (user_id, 15.99,  "Entertainment", "2026-06-08", "Movie ticket"),
        (user_id, 89.99,  "Shopping",      "2026-06-10", "Clothing"),
        (user_id, 20.00,  "Other",         "2026-06-12", "Miscellaneous"),
        (user_id, 8.75,   "Food",          "2026-06-15", "Coffee and snacks"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )

    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row


def create_user(name, email, password_hash):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id
