"""Step 6 — filtering the profile page by date range.

One test per row of the two tables in .claude/specs/06-date-filter.md.

The seeded expenses run 2026-09-01 to 2026-09-16 and sum to 337.54, so the
range used throughout, 2026-09-01 to 2026-09-05, picks up the first three
of them: 12.50 Food + 45.00 Transport + 78.30 Bills = 135.80, with Bills
on top. Preset expectations are computed from date.today() rather than
written down, so they keep meaning something after today.
"""

import re
from datetime import date, timedelta

DEMO = {"email": "demo@spendly.com", "password": "demo123"}

SEED_USER_ID = 1

SEED_TOTAL = 337.54
SEED_COUNT = 8
SEED_TOP = "Shopping"

# The first three seeded expenses.
EARLY = {"start": "2026-09-01", "end": "2026-09-05"}
EARLY_TOTAL = 135.80
EARLY_COUNT = 3
EARLY_TOP = "Bills"
EARLY_CATEGORIES = {"Bills", "Transport", "Food"}

# The last three.
LATE = {"start": "2026-09-10", "end": "2026-09-16"}

# Long before anything was seeded.
EMPTY = {"start": "2026-01-01", "end": "2026-01-31"}


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


def resolve(args, today=None):
    from app import resolve_date_range

    return resolve_date_range(args, today=today)


# ---------------------------------------------------------------- #
# get_summary_stats with a range                                    #
# ---------------------------------------------------------------- #

def test_summary_stats_are_confined_to_the_range(app):
    from database import queries

    stats = queries.get_summary_stats(SEED_USER_ID, **EARLY)

    assert stats["total_spent"] == EARLY_TOTAL
    assert stats["transaction_count"] == EARLY_COUNT
    assert stats["top_category"] == EARLY_TOP


def test_summary_stats_for_a_range_with_no_expenses(app):
    from database import queries

    assert queries.get_summary_stats(SEED_USER_ID, **EMPTY) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_summary_stats_without_a_range_are_unchanged(app):
    """No range must mean no predicate — Step 5's numbers, exactly."""
    from database import queries

    stats = queries.get_summary_stats(SEED_USER_ID, None, None)

    assert stats["total_spent"] == SEED_TOTAL
    assert stats["transaction_count"] == SEED_COUNT
    assert stats["top_category"] == SEED_TOP


# ---------------------------------------------------------------- #
# get_recent_transactions with a range                              #
# ---------------------------------------------------------------- #

def test_transactions_are_confined_to_the_range_and_newest_first(app):
    from database import queries

    rows = queries.get_recent_transactions(SEED_USER_ID, **LATE)
    dates = [row["date"] for row in rows]

    assert len(rows) == 3
    assert dates == sorted(dates, reverse=True)
    assert all(LATE["start"] <= d <= LATE["end"] for d in dates)


def test_both_bounds_of_the_range_are_inclusive(app):
    """A single-day range returns that day's expense, not nothing."""
    from database import queries

    rows = queries.get_recent_transactions(
        SEED_USER_ID, start="2026-09-01", end="2026-09-01")

    assert len(rows) == 1
    assert rows[0]["amount"] == 12.50


def test_transactions_for_a_range_with_no_expenses(app):
    from database import queries

    assert queries.get_recent_transactions(SEED_USER_ID, **EMPTY) == []


def test_a_start_with_no_end_is_an_open_ended_range(app):
    from database import queries

    rows = queries.get_recent_transactions(SEED_USER_ID, start="2026-09-11")

    assert len(rows) == 3
    assert all(row["date"] >= "2026-09-11" for row in rows)


# ---------------------------------------------------------------- #
# get_category_breakdown with a range                               #
# ---------------------------------------------------------------- #

def test_breakdown_is_confined_to_the_range_and_still_sums_to_100(app):
    from database import queries

    rows = queries.get_category_breakdown(SEED_USER_ID, **EARLY)

    assert {row["name"] for row in rows} == EARLY_CATEGORIES
    assert rows[0]["name"] == EARLY_TOP
    assert all(isinstance(row["pct"], int) for row in rows)
    assert sum(row["pct"] for row in rows) == 100


def test_breakdown_percentages_are_shares_of_the_range_not_all_time(app):
    """Bills is 23% of all time but 58% of the first five days."""
    from database import queries

    rows = queries.get_category_breakdown(SEED_USER_ID, **EARLY)
    bills = next(row for row in rows if row["name"] == EARLY_TOP)

    assert bills["pct"] == round(78.30 * 100 / EARLY_TOTAL)


def test_breakdown_for_a_range_with_no_expenses(app):
    from database import queries

    assert queries.get_category_breakdown(SEED_USER_ID, **EMPTY) == []


# ---------------------------------------------------------------- #
# Resolving the query string into a range                           #
# ---------------------------------------------------------------- #

def test_this_month_runs_from_the_first_to_today(app):
    today = date.today()

    resolved = resolve({"range": "month"}, today=today)

    assert resolved["start"] == today.replace(day=1).isoformat()
    assert resolved["end"] == today.isoformat()


def test_last_30_days_counts_today_as_one_of_them(app):
    today = date.today()

    resolved = resolve({"range": "30d"}, today=today)

    assert resolved["start"] == (today - timedelta(days=29)).isoformat()
    assert resolved["end"] == today.isoformat()


def test_this_year_runs_from_january_to_today(app):
    today = date.today()

    resolved = resolve({"range": "year"}, today=today)

    assert resolved["start"] == date(today.year, 1, 1).isoformat()
    assert resolved["end"] == today.isoformat()


def test_all_time_and_a_missing_range_both_mean_no_bounds(app):
    for args in ({}, {"range": "all"}):
        resolved = resolve(args)

        assert (resolved["start"], resolved["end"]) == (None, None)
        assert resolved["error"] is None
        assert resolved["label"] == "All time"


def test_a_malformed_date_falls_back_to_all_time_and_explains(app):
    resolved = resolve({"range": "custom",
                        "start": "not-a-date", "end": "2026-09-05"})

    assert (resolved["start"], resolved["end"]) == (None, None)
    assert resolved["error"]


def test_a_reversed_range_falls_back_to_all_time_and_explains(app):
    resolved = resolve({"range": "custom",
                        "start": "2026-09-30", "end": "2026-09-01"})

    assert (resolved["start"], resolved["end"]) == (None, None)
    assert resolved["error"]


def test_an_unknown_preset_falls_back_to_all_time(app):
    resolved = resolve({"range": "banana"})

    assert (resolved["start"], resolved["end"]) == (None, None)
    assert resolved["range"] == "all"


def test_a_valid_custom_range_survives_resolution(app):
    resolved = resolve({"range": "custom", **EARLY})

    assert resolved["start"] == EARLY["start"]
    assert resolved["end"] == EARLY["end"]
    assert resolved["error"] is None


# ---------------------------------------------------------------- #
# GET /profile with a filter                                        #
# ---------------------------------------------------------------- #

def filtered(client, **params):
    query = "&".join("%s=%s" % item for item in params.items())
    return client.get("/profile?" + query).data.decode()


def test_the_filtered_page_shows_only_the_range(client):
    login(client)
    body = filtered(client, range="custom", **EARLY)

    assert "₹135.80" in body
    assert ">3<" in body
    assert EARLY_TOP in body
    assert "Electricity bill" in body
    assert "New running shoes" not in body


def test_the_filtered_breakdown_lists_only_the_ranges_categories(client):
    login(client)
    body = filtered(client, range="custom", **EARLY)

    pcts = [int(p) for p in re.findall(r'profile-breakdown-pct">(\d+)%<', body)]

    assert len(pcts) == len(EARLY_CATEGORIES)
    assert sum(pcts) == 100
    assert "Entertainment" not in body


def test_an_empty_range_says_so_without_the_first_run_copy(client):
    login(client)
    body = filtered(client, range="custom", **EMPTY)

    assert "₹0.00" in body
    assert ">0<" in body
    assert "No expenses in" in body
    assert "Nothing here yet" not in body
    assert "profile-breakdown-row" not in body


def test_a_malformed_date_renders_the_whole_page_with_an_explanation(client):
    login(client)
    response = client.get(
        "/profile?range=custom&start=not-a-date&end=2026-09-05")
    body = response.data.decode()

    assert response.status_code == 200
    assert "₹337.54" in body
    assert ">8<" in body
    assert "profile-filter-error" in body


def test_a_reversed_range_renders_the_whole_page_with_an_explanation(client):
    login(client)
    response = client.get(
        "/profile?range=custom&start=2026-09-30&end=2026-09-01")
    body = response.data.decode()

    assert response.status_code == 200
    assert "₹337.54" in body
    assert "profile-filter-error" in body


def test_an_unknown_preset_still_renders_the_unfiltered_page(client):
    login(client)
    response = client.get("/profile?range=banana")

    assert response.status_code == 200
    assert "₹337.54" in response.data.decode()


def test_the_active_preset_is_marked_as_current(client):
    login(client)
    body = client.get("/profile?range=month").data.decode()

    assert body.count('aria-current="page"') == 1
    assert "profile-chip-on" in body


def test_the_custom_inputs_keep_the_range_in_effect(client):
    login(client)
    body = filtered(client, range="custom", **EARLY)

    assert 'name="start" value="2026-09-01"' in body
    assert 'name="end" value="2026-09-05"' in body


def test_filtering_still_requires_a_session(client):
    response = client.get("/profile?range=month")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_the_unfiltered_page_is_unchanged(client):
    """The last line of the Definition of done: Step 5 still holds."""
    login(client)
    body = client.get("/profile").data.decode()

    dates = re.findall(r'profile-txn-date">(\d{4}-\d{2}-\d{2})<', body)

    assert "₹337.54" in body
    assert len(dates) == SEED_COUNT
    assert "across all time" in body


def test_a_brand_new_user_sees_the_first_run_copy_under_every_preset(client):
    """No expenses at all is not the same as none in this range."""
    register(client, "brandnew@example.com")
    client.post("/login", data={
        "email": "brandnew@example.com", "password": "supersecret",
    })

    for preset in ("all", "30d", "month", "year"):
        body = client.get("/profile?range=" + preset).data.decode()

        assert "₹0.00" in body, preset
        assert "Nothing here yet" in body, preset
        assert "No expenses in" not in body, preset


def test_the_filter_adds_no_currency_symbol_of_its_own(client):
    """The rupee count from Step 5 must survive the new markup."""
    login(client)
    body = filtered(client, range="custom", **EARLY)

    assert "£" not in body
    assert "$" not in body
    # 3 transaction rows plus 3 breakdown rows plus the total.
    assert body.count("₹") == EARLY_COUNT + len(EARLY_CATEGORIES) + 1
