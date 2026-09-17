"""Step 4 — the profile page.

One test per row of the Definition of done in .claude/specs/04-profile-page.md.

The data on the page is hardcoded in app.py for this step, so these tests
assert against those constants. When Step 5 swaps them for real queries the
rendered values should not change, which is what keeps this file useful as a
regression net rather than something to rewrite.
"""

import os
import re

DEMO = {"email": "demo@spendly.com", "password": "demo123"}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "templates", "profile.html")
STYLESHEET = os.path.join(ROOT, "static", "css", "style.css")

# Every category in CATEGORIES — the breakdown shows all seven.
CATEGORIES = ["Food", "Transport", "Bills", "Health",
              "Entertainment", "Shopping", "Other"]


def login(client, **overrides):
    return client.post("/login", data=dict(DEMO, **overrides))


# ---------------------------------------------------------------- #
# Access control                                                    #
# ---------------------------------------------------------------- #

def test_profile_redirects_to_login_when_logged_out(client):
    response = client.get("/profile")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_returns_200_when_logged_in(client):
    login(client)
    response = client.get("/profile")

    assert response.status_code == 200


# ---------------------------------------------------------------- #
# 1. User info card                                                 #
# ---------------------------------------------------------------- #

def test_user_card_shows_name_and_email(client):
    login(client)
    body = client.get("/profile").data

    assert b"Demo User" in body
    assert b"demo@spendly.com" in body


def test_user_card_shows_avatar_initials_and_member_since(client):
    login(client)
    body = client.get("/profile").data

    assert b'class="profile-avatar">DU<' in body
    assert b"Member since" in body


def test_avatar_initials_handle_a_single_word_name(client):
    """A one-word name must not blow up on the second initial."""
    import app as app_module

    assert app_module.avatar_initials("Madonna") == "M"
    assert app_module.avatar_initials("Demo User") == "DU"
    assert app_module.avatar_initials("ada b cooper") == "AB"
    assert app_module.avatar_initials("") == "?"


# ---------------------------------------------------------------- #
# 2. Summary stats                                                  #
# ---------------------------------------------------------------- #

def test_three_summary_stats_render(client):
    login(client)
    body = client.get("/profile").data.decode()

    assert "\u20b9337.54" in body          # total spent
    assert ">8<" in body                   # transaction count
    assert "Shopping" in body              # top category
    assert body.count('class="stat-card"') == 3


def test_summary_total_matches_the_listed_transactions(client):
    """The headline number has to be the sum of the rows below it."""
    import app as app_module

    listed = sum(e["amount"] for e in app_module.PROFILE_EXPENSES)

    assert round(listed, 2) == app_module.PROFILE_STATS["total"]
    assert len(app_module.PROFILE_EXPENSES) == app_module.PROFILE_STATS["count"]


# ---------------------------------------------------------------- #
# 3. Transaction history table                                      #
# ---------------------------------------------------------------- #

def test_transaction_table_renders_every_row(client):
    login(client)
    body = client.get("/profile").data.decode()

    assert body.count("<tr>") == 9            # one header row plus eight
    assert "New running shoes" in body
    assert "Lunch at the canteen" in body
    assert "\u20b9120.00" in body


def test_transaction_categories_use_a_badge_class(client):
    login(client)
    body = client.get("/profile").data.decode()

    assert 'class="badge badge-shopping"' in body
    assert 'class="badge badge-food"' in body


# ---------------------------------------------------------------- #
# 4. Category breakdown                                             #
# ---------------------------------------------------------------- #

def test_breakdown_lists_every_category(client):
    login(client)
    body = client.get("/profile").data.decode()

    for category in CATEGORIES:
        assert 'bar-%s ' % category.lower() in body, category


def test_breakdown_bar_widths_come_from_the_class_ladder(client):
    """Every width class the page emits must actually exist in the CSS."""
    login(client)
    body = client.get("/profile").data.decode()

    css = open(STYLESHEET, encoding="utf-8").read()

    used = set(re.findall(r"bar-w-\d+", body))

    assert used, "no width classes rendered"
    for cls in used:
        assert ".%s {" % cls in css, cls


def test_breakdown_totals_match_the_transaction_rows(client):
    """The per-category totals must reconcile with the table."""
    import app as app_module

    from collections import defaultdict
    totals = defaultdict(float)
    for expense in app_module.PROFILE_EXPENSES:
        totals[expense["category"]] += expense["amount"]

    for row in app_module.PROFILE_BREAKDOWN:
        assert round(totals[row["category"]], 2) == row["total"], row["category"]

    assert len(app_module.PROFILE_BREAKDOWN) == len(CATEGORIES)


# ---------------------------------------------------------------- #
# Navbar and the styling rules the spec is strict about             #
# ---------------------------------------------------------------- #

def test_navbar_shows_the_logged_in_state(client):
    login(client)
    body = client.get("/profile").data

    assert b"Sign out" in body
    assert b"Get started" not in body


def test_profile_template_has_no_hex_colours(client):
    """Colour belongs in CSS variables, never in the template.

    Checked against the template source rather than the response, because
    base.html and ordinary hrefs legitimately contain '#'.
    """
    source = open(TEMPLATE, encoding="utf-8").read()

    assert re.search(r"#[0-9A-Fa-f]{3,8}", source) is None


def test_profile_template_has_no_inline_styles(client):
    source = open(TEMPLATE, encoding="utf-8").read()

    assert "style=" not in source
