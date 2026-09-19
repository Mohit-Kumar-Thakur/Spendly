"""Step 9 — deleting an expense.

One test per row of the two tables in .claude/specs/09-delete-expense.md.

The assertions that matter here are about what survives. A DELETE with a
broken WHERE clause passes a count-only test whenever the arithmetic
happens to work out, so the remaining ids are checked by value and the
second user's rows are checked explicitly rather than assumed.

Expense 1 is the seeded ₹12.50 canteen lunch; expense 6 is the ₹120.00
pair of running shoes that makes Shopping the top category.
"""

import pytest

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
OTHER = {"email": "mohit@example.com", "password": "supersecret"}

SEED_USER_ID = 1
SEED_COUNT = 8
SEED_TOTAL = 337.54

EXPENSE_ID = 1
EXPENSE_DESCRIPTION = "Lunch at the canteen"
EXPENSE_AMOUNT = 12.50

SHOPPING_ID = 6
SHOPPING_AMOUNT = 120.00


def login(client, credentials=DEMO):
    """Sign in, first signing out of whatever was there."""
    client.get("/logout")
    return client.post("/login", data=credentials)


def make_other_user(app):
    from database.db import get_user_by_email

    app.test_client().post("/register", data={
        "name": "Mohit Kumar", "email": OTHER["email"],
        "password": OTHER["password"],
    })
    return get_user_by_email(OTHER["email"])["id"]


def expense_ids(query, user_id=SEED_USER_ID):
    return [row["id"] for row in
            query("""SELECT id FROM expenses
                      WHERE user_id = ? ORDER BY id""", (user_id,))]


# ---------------------------------------------------------------- #
# delete_expense                                                    #
# ---------------------------------------------------------------- #

def test_delete_expense_removes_exactly_that_row(app, query):
    from database.db import delete_expense

    before = expense_ids(query)

    assert delete_expense(EXPENSE_ID, SEED_USER_ID)
    assert expense_ids(query) == [i for i in before if i != EXPENSE_ID]


def test_delete_expense_refuses_another_users_row(app, query):
    from database.db import delete_expense

    other_id = make_other_user(app)

    assert not delete_expense(EXPENSE_ID, other_id)
    assert len(expense_ids(query)) == SEED_COUNT


def test_delete_expense_reports_an_unknown_id(app, query):
    from database.db import delete_expense

    assert not delete_expense(999, SEED_USER_ID)
    assert len(expense_ids(query)) == SEED_COUNT


def test_deleting_the_same_row_twice_only_works_once(app):
    from database.db import delete_expense

    assert delete_expense(EXPENSE_ID, SEED_USER_ID)
    assert not delete_expense(EXPENSE_ID, SEED_USER_ID)


def test_deleting_does_not_touch_another_users_expenses(app, query):
    from database.db import create_expense, delete_expense

    other_id = make_other_user(app)
    theirs = create_expense(other_id, 99.0, "Other", "2026-09-01", "Theirs")

    delete_expense(EXPENSE_ID, SEED_USER_ID)

    assert expense_ids(query, other_id) == [theirs]


def test_the_summary_follows_a_deletion(app):
    """Deleting the biggest expense changes the top category."""
    from database import queries
    from database.db import delete_expense

    delete_expense(SHOPPING_ID, SEED_USER_ID)
    stats = queries.get_summary_stats(SEED_USER_ID)

    assert stats["total_spent"] == round(SEED_TOTAL - SHOPPING_AMOUNT, 2)
    assert stats["transaction_count"] == SEED_COUNT - 1
    assert stats["top_category"] != "Shopping"


# ---------------------------------------------------------------- #
# GET /expenses/<id>/delete — the confirmation page                 #
# ---------------------------------------------------------------- #

def test_the_confirmation_page_names_the_expense(client):
    login(client)
    body = client.get("/expenses/1/delete").get_data(as_text=True)

    assert EXPENSE_DESCRIPTION in body
    assert "%.2f" % EXPENSE_AMOUNT in body
    assert "Food" in body


def test_the_confirmation_page_posts_back_to_itself(client):
    login(client)
    body = client.get("/expenses/1/delete").get_data(as_text=True)

    assert 'action="/expenses/1/delete"' in body
    assert 'method="POST"' in body


def test_opening_the_confirmation_page_deletes_nothing(client, query):
    login(client)
    client.get("/expenses/1/delete")

    assert len(expense_ids(query)) == SEED_COUNT


def test_the_delete_placeholder_is_gone(client):
    login(client)

    assert b"coming in Step 9" not in client.get("/expenses/1/delete").data


def test_the_profile_links_every_row_to_its_own_delete_page(client, query):
    login(client)
    body = client.get("/profile").get_data(as_text=True)

    for expense_id in expense_ids(query):
        assert "/expenses/%d/delete" % expense_id in body, expense_id


# ---------------------------------------------------------------- #
# POST /expenses/<id>/delete                                        #
# ---------------------------------------------------------------- #

def test_confirming_removes_the_expense_and_redirects(client, query):
    login(client)
    before = expense_ids(query)
    response = client.post("/expenses/1/delete")

    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]
    assert expense_ids(query) == [i for i in before if i != EXPENSE_ID]


def test_the_profile_reflects_the_deletion(client):
    login(client)
    body = client.post("/expenses/1/delete",
                       follow_redirects=True).get_data(as_text=True)

    assert EXPENSE_DESCRIPTION not in body
    assert "%.2f" % (SEED_TOTAL - EXPENSE_AMOUNT) in body
    assert ">%d<" % (SEED_COUNT - 1) in body
    assert "profile-notice" in body


def test_confirming_twice_is_a_404(client, query):
    login(client)
    client.post("/expenses/1/delete")
    response = client.post("/expenses/1/delete")

    assert response.status_code == 404
    assert len(expense_ids(query)) == SEED_COUNT - 1


@pytest.mark.parametrize("method", ["get", "post"])
def test_an_unknown_expense_is_a_404(client, query, method):
    login(client)
    response = getattr(client, method)("/expenses/999/delete")

    assert response.status_code == 404
    assert len(expense_ids(query)) == SEED_COUNT


@pytest.mark.parametrize("method", ["get", "post"])
def test_another_users_expense_is_a_404_and_survives(app, query, method):
    make_other_user(app)
    before = expense_ids(query)

    client = app.test_client()
    login(client, OTHER)
    response = getattr(client, method)("/expenses/1/delete")

    assert response.status_code == 404
    assert expense_ids(query) == before


@pytest.mark.parametrize("method", ["get", "post"])
def test_deleting_is_closed_to_anonymous_visitors(client, query, method):
    response = getattr(client, method)("/expenses/1/delete")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert len(expense_ids(query)) == SEED_COUNT


# ---------------------------------------------------------------- #
# The page after the last expense goes                              #
# ---------------------------------------------------------------- #

def test_deleting_everything_lands_on_the_first_run_empty_state(client,
                                                                query):
    login(client)
    for expense_id in expense_ids(query):
        client.post("/expenses/%d/delete" % expense_id)

    body = client.get("/profile").get_data(as_text=True)

    assert expense_ids(query) == []
    assert "0.00" in body
    assert "Nothing here yet" in body
    assert "No expenses in" not in body
