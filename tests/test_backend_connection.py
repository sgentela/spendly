import sqlite3
import unittest.mock as mock
from werkzeug.security import generate_password_hash

from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

# ---------------------------------------------------------------------------
# In-memory DB helpers
# ---------------------------------------------------------------------------

_SCHEMA = """
    CREATE TABLE users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT    NOT NULL,
        email         TEXT    UNIQUE NOT NULL,
        password_hash TEXT    NOT NULL,
        created_at    TEXT    DEFAULT (datetime('now'))
    );
    CREATE TABLE expenses (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL REFERENCES users(id),
        amount      REAL    NOT NULL,
        category    TEXT    NOT NULL,
        date        TEXT    NOT NULL,
        description TEXT,
        created_at  TEXT    DEFAULT (datetime('now'))
    );
"""

_SEED_EXPENSES = [
    (12.50,  "Food",          "2026-06-01", "Lunch"),
    (35.00,  "Transport",     "2026-06-02", "Monthly bus pass"),
    (120.00, "Bills",         "2026-06-03", "Electricity bill"),
    (45.00,  "Health",        "2026-06-05", "Pharmacy"),
    (15.99,  "Entertainment", "2026-06-08", "Movie ticket"),
    (89.99,  "Shopping",      "2026-06-10", "Clothing"),
    (20.00,  "Other",         "2026-06-12", "Miscellaneous"),
    (8.75,   "Food",          "2026-06-15", "Coffee and snacks"),
]


class _PersistentConn:
    """Wraps sqlite3.Connection so close() is a no-op, keeping :memory: alive."""
    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _make_db():
    raw = sqlite3.connect(":memory:")
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    raw.executescript(_SCHEMA)
    return _PersistentConn(raw)


def _seed(conn, created_at="2026-01-15 10:00:00"):
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Test User", "test@example.com", generate_password_hash("pass"), created_at),
    )
    uid = cursor.lastrowid
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [(uid, amt, cat, dt, desc) for amt, cat, dt, desc in _SEED_EXPENSES],
    )
    conn.commit()
    return uid


# ---------------------------------------------------------------------------
# Unit tests — get_user_by_id
# ---------------------------------------------------------------------------

def test_get_user_by_id_valid():
    conn = _make_db()
    uid = _seed(conn)
    with mock.patch("database.queries.get_db", return_value=conn):
        result = get_user_by_id(uid)
    assert result is not None
    assert result["name"] == "Test User"
    assert result["email"] == "test@example.com"
    assert result["member_since"] == "January 2026"
    assert result["initials"] == "TU"


def test_get_user_by_id_not_found():
    conn = _make_db()
    _seed(conn)
    with mock.patch("database.queries.get_db", return_value=conn):
        result = get_user_by_id(99999)
    assert result is None


# ---------------------------------------------------------------------------
# Unit tests — get_summary_stats
# ---------------------------------------------------------------------------

def test_get_summary_stats_with_expenses():
    conn = _make_db()
    uid = _seed(conn)
    with mock.patch("database.queries.get_db", return_value=conn):
        result = get_summary_stats(uid)
    assert result["total_spent"] == "₹347.23"
    assert result["transaction_count"] == 8
    assert result["top_category"] == "Bills"


def test_get_summary_stats_no_expenses():
    conn = _make_db()
    # Insert user with no expenses
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Empty", "empty@example.com", generate_password_hash("x")),
    )
    conn.commit()
    uid = cursor.lastrowid
    with mock.patch("database.queries.get_db", return_value=conn):
        result = get_summary_stats(uid)
    assert result["total_spent"] == "₹0.00"
    assert result["transaction_count"] == 0
    assert result["top_category"] == "—"


# ---------------------------------------------------------------------------
# Unit tests — get_recent_transactions
# ---------------------------------------------------------------------------

def test_get_recent_transactions_with_expenses():
    conn = _make_db()
    uid = _seed(conn)
    with mock.patch("database.queries.get_db", return_value=conn):
        result = get_recent_transactions(uid)
    assert len(result) == 8
    # newest date first
    assert result[0]["date"] == "15 Jun 2026"
    for tx in result:
        assert set(tx.keys()) == {"date", "description", "category", "label", "amount"}


def test_get_recent_transactions_limit():
    conn = _make_db()
    uid = _seed(conn)
    with mock.patch("database.queries.get_db", return_value=conn):
        result = get_recent_transactions(uid, limit=3)
    assert len(result) == 3


def test_get_recent_transactions_no_expenses():
    conn = _make_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Empty", "empty2@example.com", generate_password_hash("x")),
    )
    conn.commit()
    uid = cursor.lastrowid
    with mock.patch("database.queries.get_db", return_value=conn):
        result = get_recent_transactions(uid)
    assert result == []


# ---------------------------------------------------------------------------
# Unit tests — get_category_breakdown
# ---------------------------------------------------------------------------

def test_get_category_breakdown_with_expenses():
    conn = _make_db()
    uid = _seed(conn)
    with mock.patch("database.queries.get_db", return_value=conn):
        result = get_category_breakdown(uid)
    assert len(result) == 7
    assert result[0]["name"] == "Bills"   # highest spend first
    for cat in result:
        assert set(cat.keys()) == {"name", "slug", "amount", "pct"}


def test_get_category_breakdown_pct_sums_to_100():
    conn = _make_db()
    uid = _seed(conn)
    with mock.patch("database.queries.get_db", return_value=conn):
        result = get_category_breakdown(uid)
    assert sum(c["pct"] for c in result) == 100


def test_get_category_breakdown_no_expenses():
    conn = _make_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Empty", "empty3@example.com", generate_password_hash("x")),
    )
    conn.commit()
    uid = cursor.lastrowid
    with mock.patch("database.queries.get_db", return_value=conn):
        result = get_category_breakdown(uid)
    assert result == []


# ---------------------------------------------------------------------------
# Route tests — use real spendly.db via Flask test client
# ---------------------------------------------------------------------------

def test_profile_unauthenticated_redirects(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_authenticated_returns_200(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.get("/profile")
    assert response.status_code == 200


def test_profile_shows_real_user_name(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.get("/profile")
    assert b"Demo User" in response.data


def test_profile_shows_real_email(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.get("/profile")
    assert b"demo@spendly.com" in response.data


def test_profile_shows_rupee_symbol(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.get("/profile")
    assert "₹".encode() in response.data


def test_profile_shows_correct_total(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.get("/profile")
    assert "₹347.23".encode() in response.data


def test_profile_transaction_count(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.get("/profile")
    assert b">8<" in response.data


def test_profile_top_category_is_bills(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.get("/profile")
    assert b"Bills" in response.data
