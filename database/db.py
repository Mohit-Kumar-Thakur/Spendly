"""SQLite data layer for Spendly.

get_db()   — returns a connection with row_factory and foreign keys enabled
init_db()  — creates all tables using CREATE TABLE IF NOT EXISTS
seed_db()  — inserts sample data for development, only once
"""

import os
import sqlite3

from werkzeug.security import generate_password_hash

# The database lives next to app.py, at the project root, so this works
# regardless of the directory the app is started from.
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

# The fixed category list. Later steps use this for the add-expense dropdown.
CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount      REAL    NOT NULL,
    category    TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    description TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# category, date (YYYY-MM-DD), amount, description
SAMPLE_EXPENSES = [
    ("Food",           "2026-09-01",  12.50, "Lunch at the canteen"),
    ("Transport",      "2026-09-03",  45.00, "Monthly metro pass"),
    ("Bills",          "2026-09-05",  78.30, "Electricity bill"),
    ("Health",         "2026-09-07",  32.00, "Pharmacy - cold medicine"),
    ("Entertainment",  "2026-09-09",  15.99, "Streaming subscription"),
    ("Shopping",       "2026-09-11", 120.00, "New running shoes"),
    ("Other",          "2026-09-13",  25.00, "Birthday gift"),
    ("Food",           "2026-09-16",   8.75, "Coffee and pastry"),
]


def get_db():
    """Open a connection to the database and return it.

    The caller is responsible for closing the connection.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create both tables. Safe to call multiple times."""
    conn = get_db()
    try:
        with conn:
            conn.executescript(SCHEMA)
    finally:
        conn.close()


def seed_db():
    """Insert demo data for development, only if the database is empty."""
    conn = get_db()
    try:
        # If any user exists the database has already been seeded.
        if conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]:
            return

        with conn:
            cursor = conn.execute(
                """INSERT INTO users (name, email, password_hash)
                   VALUES (?, ?, ?)""",
                ("Demo User", "demo@spendly.com",
                 generate_password_hash("demo123")),
            )
            user_id = cursor.lastrowid

            conn.executemany(
                """INSERT INTO expenses (user_id, amount, category, date, description)
                   VALUES (?, ?, ?, ?, ?)""",
                [(user_id, amount, category, day, description)
                 for category, day, amount, description in SAMPLE_EXPENSES],
            )
    finally:
        conn.close()


def get_user_by_email(email):
    """Return the user row matching this email, or None.

    Includes password_hash so Step 3's login check can reuse this as is.
    """
    conn = get_db()
    try:
        return conn.execute(
            """SELECT id, name, email, password_hash
                 FROM users
                WHERE email = ?""",
            (email,),
        ).fetchone()
    finally:
        conn.close()


def create_user(name, email, password):
    """Hash the password, insert the user, and return the new id.

    Raises sqlite3.IntegrityError if the email is already taken, so the
    caller can turn a lost race on the UNIQUE constraint into an error
    message rather than a 500.
    """
    conn = get_db()
    try:
        with conn:
            cursor = conn.execute(
                """INSERT INTO users (name, email, password_hash)
                   VALUES (?, ?, ?)""",
                (name, email, generate_password_hash(password)),
            )
        return cursor.lastrowid
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Return the user row for this id, or None.

    Runs on every request to resolve the session cookie, so it leaves
    password_hash out — nothing that greets a user by name needs it.
    None means the session points at a user who no longer exists.
    """
    conn = get_db()
    try:
        return conn.execute(
            """SELECT id, name, email
                 FROM users
                WHERE id = ?""",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    seed_db()
    print(f"Initialised and seeded {DB_PATH}")
