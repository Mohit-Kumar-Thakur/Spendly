"""Step 7 — adding an expense.

One test per row of the two tables in .claude/specs/07-add-expense.md.

The seeded account starts with 8 expenses totalling 337.54, so "nothing
was written" is asserted as a count that is still 8 rather than as the
absence of an exception. Dates are computed from date.today() rather than
written down, because "in the future" stops meaning anything the moment a
hardcoded date goes past.
"""

import sqlite3
from datetime import date, timedelta

import pytest

DEMO = {"email": "demo@spendly.com", "password": "demo123"}

SEED_USER_ID = 1
SEED_COUNT = 8
SEED_TOTAL = 337.54

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()

VALID = {
    "amount": "250",
    "category": "Food",
    "date": TODAY,
    "description": "Groceries for the week",
}


def login(client, **overrides):
    return client.post("/login", data=dict(DEMO, **overrides))


def register(client, email, password="supersecret", name="Mohit Kumar"):
    return client.post("/register", data={
        "name": name, "email": email, "password": password,
    })


def validate(**overrides):
    from app import validate_expense_form

    return validate_expense_form(dict(VALID, **overrides))


def count_expenses(query, user_id=SEED_USER_ID):
    return query("SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?",
                 (user_id,))[0]["n"]


# ---------------------------------------------------------------- #
# create_expense                                                    #
# ---------------------------------------------------------------- #

def test_create_expense_writes_the_row_it_was_given(app, query):
    from database.db import create_expense

    new_id = create_expense(SEED_USER_ID, 42.50, "Health", "2026-09-18",
                            "Dentist")

    assert new_id
    row = query("SELECT * FROM expenses WHERE id = ?", (new_id,))[0]
    assert row["user_id"] == SEED_USER_ID
    assert row["amount"] == 42.50
    assert row["category"] == "Health"
    assert row["date"] == "2026-09-18"
    assert row["description"] == "Dentist"


def test_create_expense_stores_a_missing_description_as_null(app, query):
    from database.db import create_expense

    new_id = create_expense(SEED_USER_ID, 10.0, "Other", "2026-09-18", None)

    assert query("SELECT description FROM expenses WHERE id = ?",
                 (new_id,))[0]["description"] is None


def test_create_expense_refuses_an_unknown_user(app, query):
    """Foreign keys are on, so an orphan expense cannot be written."""
    from database.db import create_expense

    with pytest.raises(sqlite3.IntegrityError):
        create_expense(999, 10.0, "Other", "2026-09-18", "Nobody's")

    assert count_expenses(query) == SEED_COUNT


# ---------------------------------------------------------------- #
# validate_expense_form                                             #
# ---------------------------------------------------------------- #

def test_a_valid_form_is_accepted_and_normalised(app):
    values, error = validate()

    assert error is None
    assert values["amount"] == 250.0
    assert isinstance(values["amount"], float)
    assert values["category"] == "Food"
    assert values["date"] == TODAY
    assert values["description"] == "Groceries for the week"


@pytest.mark.parametrize("amount", ["", "   "])
def test_a_missing_amount_is_rejected(app, amount):
    values, error = validate(amount=amount)

    assert error
    assert "amount" in error.lower()


def test_a_non_numeric_amount_is_rejected_without_raising(app):
    values, error = validate(amount="abc")

    assert error


@pytest.mark.parametrize("amount", ["0", "-5"])
def test_an_amount_of_zero_or_less_is_rejected(app, amount):
    values, error = validate(amount=amount)

    assert error


def test_an_amount_is_rounded_to_two_decimal_places(app):
    values, error = validate(amount="12.567")

    assert error is None
    assert values["amount"] == 12.57


def test_an_absurd_amount_is_rejected(app):
    values, error = validate(amount="99999999")

    assert error


def test_a_category_outside_the_seven_is_rejected(app):
    values, error = validate(category="Bitcoin")

    assert error


def test_a_missing_category_is_rejected(app):
    values, error = validate(category="")

    assert error


def test_a_date_in_the_wrong_format_is_rejected(app):
    values, error = validate(date="31-09-2026")

    assert error


def test_a_date_in_the_future_is_rejected(app):
    values, error = validate(date=TOMORROW)

    assert error


def test_a_date_of_today_is_accepted(app):
    values, error = validate(date=TODAY)

    assert error is None


def test_an_over_long_description_is_rejected(app):
    values, error = validate(description="x" * 300)

    assert error


def test_a_blank_description_becomes_none(app):
    values, error = validate(description="   ")

    assert error is None
    assert values["description"] is None


def test_a_rejected_form_hands_back_what_was_typed(app):
    """Nothing typed is lost to a mistake in one field."""
    values, error = validate(amount="abc", description="Coffee")

    assert error
    assert values["amount"] == "abc"
    assert values["description"] == "Coffee"
    assert values["category"] == "Food"


# ---------------------------------------------------------------- #
# GET /expenses/add                                                 #
# ---------------------------------------------------------------- #

def test_the_form_lists_every_category(client):
    from database.db import CATEGORIES

    login(client)
    body = client.get("/expenses/add").get_data(as_text=True)

    for category in CATEGORIES:
        assert category in body, category


def test_the_form_is_prefilled_with_today(client):
    login(client)
    body = client.get("/expenses/add").get_data(as_text=True)

    assert TODAY in body


def test_the_placeholder_is_gone(client):
    login(client)

    assert b"coming in Step 7" not in client.get("/expenses/add").data


def test_the_form_is_closed_to_anonymous_visitors(client):
    response = client.get("/expenses/add")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------- #
# POST /expenses/add                                                #
# ---------------------------------------------------------------- #

def test_a_valid_expense_is_stored_and_redirects(client, query):
    login(client)
    response = client.post("/expenses/add", data=VALID)

    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]
    assert count_expenses(query) == SEED_COUNT + 1

    row = query("""SELECT * FROM expenses
                    WHERE user_id = ? ORDER BY id DESC LIMIT 1""",
                (SEED_USER_ID,))[0]
    assert row["amount"] == 250.0
    assert row["category"] == "Food"
    assert row["date"] == TODAY
    assert row["description"] == "Groceries for the week"


def test_the_new_expense_shows_up_on_the_profile(client):
    login(client)
    client.post("/expenses/add", data=VALID)
    body = client.get("/profile?added=1").get_data(as_text=True)

    assert "Groceries for the week" in body
    assert "%.2f" % (SEED_TOTAL + 250) in body


def test_adding_shows_a_confirmation_notice(client):
    login(client)
    body = client.post("/expenses/add", data=VALID,
                       follow_redirects=True).get_data(as_text=True)

    assert "profile-notice" in body


def test_the_notice_is_gone_on_the_next_plain_visit(client):
    login(client)
    client.post("/expenses/add", data=VALID, follow_redirects=True)

    assert "profile-notice" not in client.get("/profile").get_data(as_text=True)


def test_an_anonymous_post_stores_nothing(client, query):
    response = client.post("/expenses/add", data=VALID)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert count_expenses(query) == SEED_COUNT


@pytest.mark.parametrize("field,value", [
    ("amount", "abc"),
    ("amount", "-5"),
    ("amount", ""),
    ("category", "Bitcoin"),
    ("date", "31-09-2026"),
    ("date", TOMORROW),
    ("description", "x" * 300),
])
def test_an_invalid_expense_is_refused_and_stores_nothing(client, query,
                                                          field, value):
    login(client)
    response = client.post("/expenses/add", data=dict(VALID, **{field: value}))

    assert response.status_code == 200
    assert count_expenses(query) == SEED_COUNT
    assert "auth-error" in response.get_data(as_text=True)


def test_a_refused_expense_keeps_the_other_fields_filled_in(client):
    login(client)
    body = client.post("/expenses/add",
                       data=dict(VALID, amount="abc")).get_data(as_text=True)

    assert 'value="abc"' in body
    assert "Groceries for the week" in body


def test_a_posted_user_id_is_ignored(client, query):
    """The owner comes from the session, never from the form."""
    login(client)
    other = register(client.application.test_client(), "mohit@example.com")
    assert other.status_code == 302

    client.post("/expenses/add", data=dict(VALID, user_id=2))

    assert count_expenses(query) == SEED_COUNT + 1
    assert count_expenses(query, user_id=2) == 0


def test_the_same_expense_can_be_added_twice(client, query):
    """Two identical coffees are two expenses, not one."""
    login(client)
    client.post("/expenses/add", data=VALID)
    client.post("/expenses/add", data=VALID)

    assert count_expenses(query) == SEED_COUNT + 2


def test_one_users_expense_stays_off_another_users_profile(app, query):
    from database.db import get_user_by_email

    other = app.test_client()
    register(other, "mohit@example.com")
    other.post("/login", data={"email": "mohit@example.com",
                               "password": "supersecret"})
    other.post("/expenses/add", data=dict(VALID, description="Private note"))

    other_id = get_user_by_email("mohit@example.com")["id"]
    assert count_expenses(query, user_id=other_id) == 1
    assert count_expenses(query) == SEED_COUNT

    seed = app.test_client()
    login(seed)

    assert "Private note" not in seed.get("/profile").get_data(as_text=True)
    assert "Private note" in other.get("/profile").get_data(as_text=True)
