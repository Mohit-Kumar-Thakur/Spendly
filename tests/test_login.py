"""Step 3 — login and logout.

One test per row of the Definition of done in
.claude/specs/03-login-logout.md. The seeded demo account from Step 1 is
the fixture data.
"""

DEMO = {"email": "demo@spendly.com", "password": "demo123"}

GUARDED = ["/profile", "/expenses/add", "/expenses/1/edit", "/expenses/1/delete"]


def login(client, **overrides):
    return client.post("/login", data=dict(DEMO, **overrides))


# ------------------------------------------------------------------ #
# Signing in                                                          #
# ------------------------------------------------------------------ #

def test_valid_login_redirects_to_profile(client):
    response = login(client)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_valid_login_sets_a_session_cookie(client):
    response = login(client)

    assert "session=" in response.headers.get("Set-Cookie", "")


def test_profile_greets_the_user_by_name(client):
    login(client)
    response = client.get("/profile")

    assert response.status_code == 200
    assert b"Demo User" in response.data


def test_email_casing_does_not_matter(client):
    response = login(client, email="DEMO@Spendly.com")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_get_login_while_logged_in_redirects_to_profile(client):
    login(client)
    response = client.get("/login")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


# ------------------------------------------------------------------ #
# Failed sign-in                                                      #
# ------------------------------------------------------------------ #

def test_wrong_password_is_rejected(client):
    response = login(client, password="wrongpassword")

    assert response.status_code == 200
    assert b"Incorrect email or password." in response.data


def test_unknown_email_and_wrong_password_are_indistinguishable(client):
    wrong_password = login(client, password="wrongpassword")
    unknown_email = login(client, email="nobody@nowhere.com",
                          password="wrongpassword")

    # The only thing that may differ is the email echoed back into the
    # form, which is the submitter's own input. Normalise that away and
    # the two responses must be byte-identical, so neither can be used
    # to tell a registered address from an unregistered one.
    a = wrong_password.data.replace(b"demo@spendly.com", b"EMAIL")
    b = unknown_email.data.replace(b"nobody@nowhere.com", b"EMAIL")

    assert a == b


def test_failed_login_keeps_email_but_not_password(client):
    response = login(client, password="wrongpassword")
    body = response.data.decode()

    assert 'value="demo@spendly.com"' in body
    assert "wrongpassword" not in body


def test_failed_login_leaves_no_session(client):
    login(client, password="wrongpassword")
    response = client.get("/profile")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ------------------------------------------------------------------ #
# Route protection                                                    #
# ------------------------------------------------------------------ #

def test_guarded_routes_redirect_when_logged_out(client):
    for path in GUARDED:
        response = client.get(path)
        assert response.status_code == 302, path
        assert "/login" in response.headers["Location"], path


def test_guarded_routes_are_reachable_when_logged_in(client):
    login(client)
    for path in GUARDED:
        response = client.get(path)
        assert response.status_code == 200, path


def test_expense_placeholders_still_say_coming_soon(client):
    login(client)

    assert b"coming in Step 7" in client.get("/expenses/add").data
    assert b"coming in Step 8" in client.get("/expenses/1/edit").data
    assert b"coming in Step 9" in client.get("/expenses/1/delete").data


# ------------------------------------------------------------------ #
# Signing out                                                         #
# ------------------------------------------------------------------ #

def test_logout_redirects_to_landing(client):
    login(client)
    response = client.get("/logout")

    assert response.status_code == 302
    assert response.headers["Location"] in ("/", "http://localhost/")


def test_logout_blocks_the_profile_again(client):
    login(client)
    client.get("/logout")
    response = client.get("/profile")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ------------------------------------------------------------------ #
# Navbar reflects the state                                           #
# ------------------------------------------------------------------ #

def test_navbar_shows_sign_in_when_logged_out(client):
    body = client.get("/").data

    assert b"Sign in" in body
    assert b"Sign out" not in body


def test_navbar_shows_sign_out_when_logged_in(client):
    login(client)
    body = client.get("/profile").data

    assert b"Sign out" in body
    assert b"Get started" not in body


# ------------------------------------------------------------------ #
# Edge cases                                                          #
# ------------------------------------------------------------------ #

def test_session_for_a_deleted_user_is_treated_as_logged_out(client, query, app):
    import database.db as db

    login(client)

    conn = db.get_db()
    try:
        with conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM users WHERE email = ?", (DEMO["email"],))
    finally:
        conn.close()

    # Must redirect, not raise.
    response = client.get("/profile")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_register_then_login_round_trip(client):
    client.post("/register", data={
        "name": "Round Trip",
        "email": "round@trip.com",
        "password": "supersecret",
    })
    response = client.post("/login", data={
        "email": "round@trip.com",
        "password": "supersecret",
    })

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_seeded_data_is_untouched(client, query):
    login(client)

    assert query("SELECT COUNT(*) AS n FROM users WHERE email = ?",
                 (DEMO["email"],))[0]["n"] == 1
    assert query("SELECT COUNT(*) AS n FROM expenses")[0]["n"] == 8

# ------------------------------------------------------------------ #
# Signed-in visitors are sent to their profile                        #
# ------------------------------------------------------------------ #

ANONYMOUS_ONLY = ["/", "/register", "/login"]


def test_anonymous_only_routes_redirect_when_logged_in(client):
    login(client)

    for path in ANONYMOUS_ONLY:
        response = client.get(path)
        assert response.status_code == 302, path
        assert response.headers["Location"].endswith("/profile"), path


def test_anonymous_only_routes_still_render_when_logged_out(client):
    for path in ANONYMOUS_ONLY:
        response = client.get(path)
        assert response.status_code == 200, path


def test_the_same_request_that_logs_you_in_does_not_cache_a_stale_user(client):
    """Regression: current_user() caches on g.

    anonymous_only asks "is anyone signed in?" before POST /login has
    written the session, so the cached answer has to be dropped once it
    has. Without that, everything after the login in the same app context
    still sees an anonymous visitor.
    """
    login(client)

    assert client.get("/profile").status_code == 200


def test_logging_out_restores_access_to_the_public_pages(client):
    login(client)
    client.get("/logout")

    for path in ANONYMOUS_ONLY:
        assert client.get(path).status_code == 200, path


# ------------------------------------------------------------------ #
# Form placeholders                                                   #
# ------------------------------------------------------------------ #

def test_form_placeholders_use_mohit(client):
    for path in ["/login", "/register"]:
        body = client.get(path).data.decode().lower()
        assert "nitish" not in body, path
        assert "mohit@example.com" in body, path
