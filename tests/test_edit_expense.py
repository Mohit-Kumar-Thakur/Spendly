"""Step 8 — editing an expense.

One test per row of the two tables in .claude/specs/08-edit-expense.md.

Expense 1 is the seeded ₹12.50 canteen lunch on 2026-09-01, filed under
Food. Most of this file is about ownership rather than about the form:
an id in a URL is a number anyone can change, so "another user gets a
404" is asserted alongside "and the row is byte-identical afterwards".
A 404 on its own would also be reported by a route that updated the row
and then fell over.
"""

from datetime import date, timedelta

import pytest

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
OTHER = {"email": "mohit@example.com", "password": "supersecret"}

SEED_USER_ID = 1
SEED_COUNT = 8
SEED_TOTAL = 337.54

EXPENSE_ID = 1
STORED = {"amount": 12.50, "category": "Food", "date": "2026-09-01",
          "description": "Lunch at the canteen"}

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()

EDITED = {"amount": "20.00", "category": "Health", "date": "2026-09-02",
          "description": "Chemist, not the canteen"}


def login(client, credentials=DEMO):
    """Sign in, first signing out of whatever was there.

    /login is anonymous_only, so posting to it while already signed in is
    a redirect to the profile rather than a change of user — switching
    accounts has to go through /logout.
    """
    client.get("/logout")
    return client.post("/login", data=credentials)


def make_other_user(app):
    """Register a second account and return its id."""
    from database.db import get_user_by_email

    app.test_client().post("/register", data={
        "name": "Mohit Kumar", "email": OTHER["email"],
        "password": OTHER["password"],
    })
    return get_user_by_email(OTHER["email"])["id"]


def stored_row(query, expense_id=EXPENSE_ID):
    return dict(query("SELECT * FROM expenses WHERE id = ?",
                      (expense_id,))[0])


def count_expenses(query, user_id=SEED_USER_ID):
    return query("SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?",
                 (user_id,))[0]["n"]


# ---------------------------------------------------------------- #
# get_expense                                                       #
# ---------------------------------------------------------------- #

def test_get_expense_returns_the_owners_row(app):
    from database.db import get_expense

    row = get_expense(EXPENSE_ID, SEED_USER_ID)

    assert row["amount"] == STORED["amount"]
    assert row["category"] == STORED["category"]
    assert row["date"] == STORED["date"]
    assert row["description"] == STORED["description"]


def test_get_expense_hides_another_users_row(app):
    from database.db import get_expense

    assert get_expense(EXPENSE_ID, make_other_user(app)) is None


def test_get_expense_returns_none_for_an_unknown_id(app):
    from database.db import get_expense

    assert get_expense(999, SEED_USER_ID) is None


# ---------------------------------------------------------------- #
# update_expense                                                    #
# ---------------------------------------------------------------- #

def test_update_expense_writes_the_new_values(app, query):
    from database.db import update_expense

    assert update_expense(EXPENSE_ID, SEED_USER_ID, 20.0, "Health",
                          "2026-09-02", "Chemist")

    row = stored_row(query)
    assert row["amount"] == 20.0
    assert row["category"] == "Health"
    assert row["date"] == "2026-09-02"
    assert row["description"] == "Chemist"


def test_update_expense_refuses_another_users_row(app, query):
    from database.db import update_expense

    before = stored_row(query)
    other_id = make_other_user(app)

    assert not update_expense(EXPENSE_ID, other_id, 9999.0, "Other",
                              "2026-01-01", "Stolen")
    assert stored_row(query) == before


def test_update_expense_reports_an_unknown_id(app, query):
    from database.db import update_expense

    before = stored_row(query)

    assert not update_expense(999, SEED_USER_ID, 20.0, "Health",
                              "2026-09-02", "Nowhere")
    assert stored_row(query) == before


def test_update_expense_leaves_created_at_alone(app, query):
    """An edit is a correction, not a new record."""
    from database.db import update_expense

    before = stored_row(query)["created_at"]
    update_expense(EXPENSE_ID, SEED_USER_ID, 20.0, "Health", "2026-09-02",
                   "Chemist")

    assert stored_row(query)["created_at"] == before


def test_update_expense_can_clear_the_description(app, query):
    from database.db import update_expense

    update_expense(EXPENSE_ID, SEED_USER_ID, 12.50, "Food", "2026-09-01",
                   None)

    assert stored_row(query)["description"] is None


def test_every_transaction_row_carries_its_id(app):
    from database import queries

    rows = queries.get_recent_transactions(SEED_USER_ID)

    assert all(row["id"] for row in rows)
    assert sorted(rows[0]) == ["amount", "category", "date", "description",
                               "id"]


# ---------------------------------------------------------------- #
# GET /expenses/<id>/edit                                           #
# ---------------------------------------------------------------- #

def test_the_form_opens_prefilled_with_the_stored_expense(client):
    login(client)
    body = client.get("/expenses/1/edit").get_data(as_text=True)

    assert 'value="12.50"' in body
    assert 'value="2026-09-01"' in body
    assert "Lunch at the canteen" in body
    assert 'id="category-food"' in body and "checked" in body


def test_the_form_posts_back_to_the_same_expense(client):
    login(client)
    body = client.get("/expenses/1/edit").get_data(as_text=True)

    assert 'action="/expenses/1/edit"' in body


def test_the_edit_placeholder_is_gone(client):
    login(client)

    assert b"coming in Step 8" not in client.get("/expenses/1/edit").data


def test_the_profile_links_every_row_to_its_own_edit_page(client, query):
    login(client)
    body = client.get("/profile").get_data(as_text=True)

    ids = [row["id"] for row in
           query("SELECT id FROM expenses WHERE user_id = ?", (SEED_USER_ID,))]
    for expense_id in ids:
        assert "/expenses/%d/edit" % expense_id in body, expense_id


# ---------------------------------------------------------------- #
# POST /expenses/<id>/edit                                          #
# ---------------------------------------------------------------- #

def test_a_valid_edit_is_saved_and_redirects(client, query):
    login(client)
    response = client.post("/expenses/1/edit", data=EDITED)

    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]

    row = stored_row(query)
    assert row["amount"] == 20.0
    assert row["category"] == "Health"
    assert row["date"] == "2026-09-02"
    assert row["description"] == "Chemist, not the canteen"


def test_an_edit_is_not_an_insert(client, query):
    login(client)
    client.post("/expenses/1/edit", data=EDITED)

    assert count_expenses(query) == SEED_COUNT


def test_the_profile_shows_the_edit_and_a_notice(client):
    login(client)
    body = client.post("/expenses/1/edit", data=EDITED,
                       follow_redirects=True).get_data(as_text=True)

    assert "Chemist, not the canteen" in body
    assert "Lunch at the canteen" not in body
    assert "profile-notice" in body


def test_the_total_moves_by_exactly_the_difference(client):
    login(client)
    client.post("/expenses/1/edit", data=EDITED)
    body = client.get("/profile").get_data(as_text=True)

    assert "%.2f" % (SEED_TOTAL - 12.50 + 20.00) in body


def test_changing_only_the_category_leaves_the_rest_alone(client, query):
    login(client)
    client.post("/expenses/1/edit", data={
        "amount": "12.50", "category": "Other", "date": "2026-09-01",
        "description": "Lunch at the canteen",
    })

    row = stored_row(query)
    assert row["category"] == "Other"
    assert row["amount"] == 12.50
    assert row["date"] == "2026-09-01"


def test_saving_an_unchanged_expense_is_a_success(client, query):
    login(client)
    before = stored_row(query)
    response = client.post("/expenses/1/edit", data={
        "amount": "12.50", "category": "Food", "date": "2026-09-01",
        "description": "Lunch at the canteen",
    })

    assert response.status_code == 302
    assert stored_row(query) == before


# ---------------------------------------------------------------- #
# Who is allowed                                                    #
# ---------------------------------------------------------------- #

@pytest.mark.parametrize("method", ["get", "post"])
def test_an_unknown_expense_is_a_404(client, method):
    login(client)
    response = getattr(client, method)("/expenses/999/edit", data=EDITED)

    assert response.status_code == 404


@pytest.mark.parametrize("method", ["get", "post"])
def test_another_users_expense_is_a_404_and_stays_untouched(app, query,
                                                            method):
    make_other_user(app)
    before = stored_row(query)

    client = app.test_client()
    login(client, OTHER)
    response = getattr(client, method)("/expenses/1/edit", data=EDITED)

    assert response.status_code == 404
    assert stored_row(query) == before


@pytest.mark.parametrize("method", ["get", "post"])
def test_editing_is_closed_to_anonymous_visitors(client, query, method):
    before = stored_row(query)
    response = getattr(client, method)("/expenses/1/edit", data=EDITED)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert stored_row(query) == before


# ---------------------------------------------------------------- #
# Rejected edits                                                    #
# ---------------------------------------------------------------- #

@pytest.mark.parametrize("field,value", [
    ("amount", "abc"),
    ("amount", "-5"),
    ("amount", ""),
    ("category", "Bitcoin"),
    ("date", "31-09-2026"),
    ("date", TOMORROW),
    ("description", "x" * 300),
])
def test_an_invalid_edit_changes_nothing(client, query, field, value):
    """Editing must not be able to store what adding would refuse."""
    login(client)
    before = stored_row(query)
    response = client.post("/expenses/1/edit",
                           data=dict(EDITED, **{field: value}))

    assert response.status_code == 200
    assert "auth-error" in response.get_data(as_text=True)
    assert stored_row(query) == before


def test_a_rejected_edit_keeps_the_unsaved_changes_on_screen(client):
    """The user is looking at their edit, not at the database row."""
    login(client)
    body = client.post("/expenses/1/edit",
                       data=dict(EDITED, amount="abc")).get_data(as_text=True)

    assert 'value="abc"' in body
    assert "Chemist, not the canteen" in body
    assert "Lunch at the canteen" not in body
