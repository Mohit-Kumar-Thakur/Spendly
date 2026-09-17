"""Step 5 — the profile page reads from the database.

One test per row of the two tables in
.claude/specs/05-backend-route-for-profile-page.md.

The spec originally quoted 346.24 / "Bills" as the seed user's totals. The
seeded rows in database/db.py actually sum to 337.54 with Shopping on top,
so these assert the real data and the spec was corrected to match.
"""

import os
import re

DEMO = {"email": "demo@spendly.com", "password": "demo123"}

# seed_db() inserts the demo user first, into an empty temp database.
SEED_USER_ID = 1
MISSING_USER_ID = 999

SEED_TOTAL = 337.54
SEED_COUNT = 8
SEED_TOP = "Shopping"

CATEGORIES = ["Food", "Transport", "Bills", "Health",
              "Entertainment", "Shopping", "Other"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "templates", "profile.html")
QUERIES = os.path.join(ROOT, "database", "queries.py")


def login(client, **overrides):
    return client.post("/login", data=dict(DEMO, **overrides))


def register(client, email, password="supersecret", name="New Person"):
    return client.post("/register", data={
        "name": name, "email": email, "password": password,
    })


def empty_user_id(app):
    """Register someone with no expenses and return their id."""
    from database.db import get_user_by_email

    register(app.test_client(), "fresh@example.com")
    return get_user_by_email("fresh@example.com")["id"]


# ---------------------------------------------------------------- #
# get_user_by_id                                                    #
# ---------------------------------------------------------------- #

def test_get_user_by_id_returns_the_profile_fields(app):
    from database import queries

    user = queries.get_user_by_id(SEED_USER_ID)

    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    # created_at is datetime('now') at seed time, so only the shape is fixed.
    assert re.match(r"^[A-Z][a-z]+ \d{4}$", user["member_since"]), user


def test_get_user_by_id_returns_none_for_a_missing_id(app):
    from database import queries

    assert queries.get_user_by_id(MISSING_USER_ID) is None


def test_get_user_by_id_never_exposes_the_password_hash(app):
    from database import queries

    assert "password_hash" not in queries.get_user_by_id(SEED_USER_ID)


# ---------------------------------------------------------------- #
# get_summary_stats                                                 #
# ---------------------------------------------------------------- #

def test_get_summary_stats_for_a_user_with_expenses(app):
    from database import queries

    stats = queries.get_summary_stats(SEED_USER_ID)

    assert stats["total_spent"] == SEED_TOTAL
    assert stats["transaction_count"] == SEED_COUNT
    assert stats["top_category"] == SEED_TOP


def test_top_category_ranks_by_amount_not_by_row_count(app):
    """Food appears twice but sums to 21.25; Shopping is one row at 120."""
    from database import queries

    assert queries.get_summary_stats(SEED_USER_ID)["top_category"] != "Food"


def test_get_summary_stats_for_a_user_with_no_expenses(app):
    from database import queries

    assert queries.get_summary_stats(empty_user_id(app)) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


# ---------------------------------------------------------------- #
# get_recent_transactions                                           #
# ---------------------------------------------------------------- #

def test_get_recent_transactions_returns_newest_first(app):
    from database import queries

    rows = queries.get_recent_transactions(SEED_USER_ID)

    assert len(rows) == SEED_COUNT
    assert sorted(rows[0]) == ["amount", "category", "date", "description"]
    assert [r["date"] for r in rows] == sorted(
        (r["date"] for r in rows), reverse=True)
    assert rows[0]["description"] == "Coffee and pastry"


def test_get_recent_transactions_honours_the_limit(app):
    from database import queries

    assert len(queries.get_recent_transactions(SEED_USER_ID, limit=3)) == 3


def test_get_recent_transactions_for_a_user_with_no_expenses(app):
    from database import queries

    assert queries.get_recent_transactions(empty_user_id(app)) == []


# ---------------------------------------------------------------- #
# get_category_breakdown                                            #
# ---------------------------------------------------------------- #

def test_get_category_breakdown_is_ordered_and_sums_to_100(app):
    from database import queries

    rows = queries.get_category_breakdown(SEED_USER_ID)

    assert len(rows) == len(CATEGORIES)
    assert sorted(rows[0]) == ["amount", "name", "pct"]
    assert rows[0]["name"] == SEED_TOP
    assert [r["amount"] for r in rows] == sorted(
        (r["amount"] for r in rows), reverse=True)
    assert all(isinstance(r["pct"], int) for r in rows)
    assert sum(r["pct"] for r in rows) == 100


def test_category_amounts_sum_to_the_reported_total(app):
    from database import queries

    rows = queries.get_category_breakdown(SEED_USER_ID)

    assert round(sum(r["amount"] for r in rows), 2) == SEED_TOTAL


def test_get_category_breakdown_for_a_user_with_no_expenses(app):
    from database import queries

    assert queries.get_category_breakdown(empty_user_id(app)) == []


# ---------------------------------------------------------------- #
# GET /profile                                                      #
# ---------------------------------------------------------------- #

def test_profile_redirects_when_unauthenticated(client):
    response = client.get("/profile")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_shows_the_seed_users_real_data(client):
    login(client)
    response = client.get("/profile")
    body = response.data.decode()

    assert response.status_code == 200
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹337.54" in body
    assert ">8<" in body
    assert "Shopping" in body


def test_profile_renders_every_amount_with_the_rupee_symbol(client):
    """No pound or dollar sign anywhere, and every amount carries the rupee."""
    login(client)
    body = client.get("/profile").data.decode()

    assert "£" not in body
    assert "$" not in body
    # 8 transaction rows plus 7 breakdown rows plus the total.
    assert body.count("₹") == SEED_COUNT + len(CATEGORIES) + 1


def test_profile_lists_transactions_newest_first(client):
    login(client)
    body = client.get("/profile").data.decode()

    dates = re.findall(r'profile-txn-date">(\d{4}-\d{2}-\d{2})<', body)

    assert len(dates) == SEED_COUNT
    assert dates == sorted(dates, reverse=True)


def test_profile_breakdown_shows_all_seven_categories(client):
    login(client)
    body = client.get("/profile").data.decode()

    pcts = [int(p) for p in re.findall(r'profile-breakdown-pct">(\d+)%<', body)]

    assert len(pcts) == len(CATEGORIES)
    assert sum(pcts) == 100


def test_a_brand_new_user_sees_zeros_and_no_errors(client, app):
    """The eighth Definition-of-done row: register, then visit /profile."""
    register(client, "brandnew@example.com")
    response = client.post("/login", data={
        "email": "brandnew@example.com", "password": "supersecret",
    })
    assert response.status_code == 302

    response = client.get("/profile")
    body = response.data.decode()

    assert response.status_code == 200
    assert "₹0.00" in body
    assert ">0<" in body
    assert "—" in body                      # top category placeholder
    assert "No spending to break down yet." in body
    assert "profile-breakdown-row" not in body


# ---------------------------------------------------------------- #
# The rules the spec is strict about                                #
# ---------------------------------------------------------------- #

def test_queries_module_does_not_import_flask(app):
    """queries.py must be usable without an app context.

    Checked on import statements rather than the word anywhere, since the
    module's own docstring says it does not import Flask.
    """
    source = open(QUERIES, encoding="utf-8").read()

    assert re.search(r"^\s*(import|from)\s+flask", source,
                     re.MULTILINE | re.IGNORECASE) is None


def test_queries_module_never_formats_values_into_sql(app):
    source = open(QUERIES, encoding="utf-8").read()

    for line in source.splitlines():
        if any(kw in line for kw in ("SELECT", "FROM", "WHERE", "GROUP BY")):
            assert "%" not in line, line
            assert ".format(" not in line, line
            assert not line.strip().startswith('f"'), line


def test_template_has_no_hex_colour_or_inline_style(client):
    source = open(TEMPLATE, encoding="utf-8").read()

    assert re.search(r"#[0-9A-Fa-f]{3,8}", source) is None
    assert "style=" not in source
