"""Read-only query helpers for the profile page.

Separate from db.py on purpose: db.py owns the schema, the connection and
writes, while everything here only reads and shapes data for a template.
Nothing in this module imports Flask, so it can be exercised without an
app context — which is also why every function opens its own connection
through get_db() and closes it before returning.

All of these return plain dicts and lists rather than sqlite3.Row, since
a Row outlives its connection badly and the template renders long after
these have returned.
"""

from database.db import get_db

# Spelled out rather than taken from strftime("%B") because that follows
# the machine's locale, and "Member since septembre 2026" on someone
# else's laptop would be a confusing way to find that out.
MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def _format_member_since(created_at):
    """Turn a stored timestamp into "Month YYYY".

    Reads the leading YYYY-MM rather than parsing the whole value, so it
    works whether the column holds a bare date or the full
    datetime('now') timestamp the schema defaults to.
    """
    try:
        year, month = str(created_at)[:7].split("-")
        return "%s %s" % (MONTHS[int(month) - 1], year)
    except (ValueError, IndexError):
        # A malformed timestamp is not worth a 500 on someone's profile.
        return "—"


def get_user_by_id(user_id):
    """Return the profile header fields for one user, or None.

    Deliberately narrower than db.get_user_by_id: that one resolves the
    session on every request, this one shapes the user card and so
    carries member_since. Neither ever selects password_hash.
    """
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT name, email, created_at
                 FROM users
                WHERE id = ?""",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": _format_member_since(row["created_at"]),
    }


def get_summary_stats(user_id):
    """Return the three headline numbers the summary cards show.

    Kept as one call so a page render costs a single trip rather than
    three, and so the "no expenses yet" case is decided in one place: a
    new user must see zeroes and an em dash, never a blank card or a None
    that breaks currency formatting in the template.

    top_category ranks by summed amount, not row count — one large
    purchase should outrank several small ones, which is what "where the
    money went" means to a user. Ties break alphabetically so repeated
    renders of the same data don't shuffle the card.

    total_spent is rounded because SUM over REAL accumulates float error
    (337.54 comes back as 337.54000000000002) and this is shown as money.
    """
    conn = get_db()
    try:
        totals = conn.execute(
            """SELECT COUNT(*)                 AS n,
                      COALESCE(SUM(amount), 0) AS total
                 FROM expenses
                WHERE user_id = ?""",
            (user_id,),
        ).fetchone()

        # No rows at all: there is no category to name, so short-circuit
        # with the placeholders the cards expect.
        if not totals["n"]:
            return {
                "total_spent": 0,
                "transaction_count": 0,
                "top_category": "—",
            }

        top = conn.execute(
            """SELECT category
                 FROM expenses
                WHERE user_id = ?
                GROUP BY category
                ORDER BY SUM(amount) DESC, category ASC
                LIMIT 1""",
            (user_id,),
        ).fetchone()

        return {
            "total_spent": round(totals["total"], 2),
            "transaction_count": totals["n"],
            "top_category": top["category"],
        }
    finally:
        conn.close()


def get_recent_transactions(user_id, limit=10):
    """Return this user's most recent expenses, newest first.

    Ties on date break by id descending: several seeded expenses share a
    date, and SQLite may return equal keys in any order, which would
    reshuffle the table between requests and make the tests flaky.
    Highest id means most recently entered, which is also the order a
    user expects.

    Returns [] for a user with no expenses.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT date, description, category, amount
                 FROM expenses
                WHERE user_id = ?
                ORDER BY date DESC, id DESC
                LIMIT ?""",
            (user_id, int(limit)),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_category_breakdown(user_id):
    """Return spending per category as name/amount/pct dicts, biggest first.

    The percentages have to add up to 100 — a breakdown whose labels read
    99% looks broken. Rounding each share independently loses or gains a
    point, so the drift is pushed onto the largest category, where one
    point is the smallest relative distortion and the row is big enough
    to absorb it without changing the ranking.

    Categories the user has never spent in are absent rather than shown
    as zero. Returns [] for a user with no expenses, which also keeps the
    percentage maths away from a division by zero.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT category, SUM(amount) AS total
                 FROM expenses
                WHERE user_id = ?
                GROUP BY category
                ORDER BY total DESC, category ASC""",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    # Rounded here so the percentages are computed from the same numbers
    # the page prints, and the two can never disagree.
    breakdown = [
        {"name": row["category"], "amount": round(row["total"], 2), "pct": 0}
        for row in rows
    ]

    total = round(sum(item["amount"] for item in breakdown), 2)
    if not breakdown or total <= 0:
        return []

    for item in breakdown:
        item["pct"] = int(round(item["amount"] * 100 / total))

    # Whatever the rounding lost or gained goes to the largest category,
    # which is first because the query ordered by total descending.
    breakdown[0]["pct"] += 100 - sum(item["pct"] for item in breakdown)

    return breakdown
