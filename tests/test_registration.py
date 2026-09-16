"""Step 2 — registration.

One test per row of the Definition of done in
.claude/specs/02-registration.md.
"""

VALID = {
    "name": "Test User",
    "email": "test@example.com",
    "password": "supersecret",
}


def count_users(query, email):
    return query("SELECT COUNT(*) AS n FROM users WHERE email = ?",
                 (email,))[0]["n"]


# ------------------------------------------------------------------ #
# Happy path                                                          #
# ------------------------------------------------------------------ #

def test_valid_registration_redirects_to_login(client):
    response = client.post("/register", data=VALID)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert "registered=1" in response.headers["Location"]


def test_valid_registration_creates_exactly_one_row(client, query):
    client.post("/register", data=VALID)

    assert count_users(query, "test@example.com") == 1


def test_password_is_hashed_not_stored_plaintext(client, query):
    client.post("/register", data=VALID)

    stored = query("SELECT password_hash FROM users WHERE email = ?",
                   ("test@example.com",))[0]["password_hash"]

    assert stored.startswith("scrypt:")
    assert stored != VALID["password"]
    assert VALID["password"] not in stored


def test_email_is_stored_lowercased(client, query):
    client.post("/register", data=dict(VALID, email="Test@EXAMPLE.com"))

    assert count_users(query, "test@example.com") == 1


def test_name_is_stripped_before_storing(client, query):
    client.post("/register", data=dict(VALID, name="  Test User  "))

    stored = query("SELECT name FROM users WHERE email = ?",
                   ("test@example.com",))[0]["name"]

    assert stored == "Test User"


# ------------------------------------------------------------------ #
# Validation failures                                                 #
# ------------------------------------------------------------------ #

def test_duplicate_email_is_rejected_regardless_of_casing(client, query):
    client.post("/register", data=VALID)
    response = client.post("/register", data=dict(VALID, email="TEST@Example.COM"))

    assert response.status_code == 200
    assert b"An account with that email already exists." in response.data
    assert count_users(query, "test@example.com") == 1


def test_short_password_is_rejected_server_side(client, query):
    response = client.post("/register", data=dict(VALID, password="1234567"))

    assert response.status_code == 200
    assert b"Password must be at least 8 characters." in response.data
    assert count_users(query, "test@example.com") == 0


def test_whitespace_only_name_is_rejected(client, query):
    response = client.post("/register", data=dict(VALID, name="   "))

    assert response.status_code == 200
    assert b"Please enter your name." in response.data
    assert count_users(query, "test@example.com") == 0


def test_email_without_at_sign_is_rejected(client, query):
    response = client.post("/register", data=dict(VALID, email="not-an-email"))

    assert response.status_code == 200
    assert b"Please enter a valid email address." in response.data
    assert query("SELECT COUNT(*) AS n FROM users")[0]["n"] == 1  # demo only


def test_failed_submission_keeps_name_and_email_but_not_password(client):
    response = client.post("/register", data=dict(VALID, password="short"))
    body = response.data.decode()

    assert 'value="Test User"' in body
    assert 'value="test@example.com"' in body
    assert "short" not in body


# ------------------------------------------------------------------ #
# Login page banner                                                   #
# ------------------------------------------------------------------ #

def test_login_shows_banner_after_registration(client):
    response = client.get("/login?registered=1")

    assert b"auth-success" in response.data
    assert b"Account created. Sign in to continue." in response.data


def test_login_has_no_banner_without_query_param(client):
    response = client.get("/login")

    assert b"auth-success" not in response.data


# ------------------------------------------------------------------ #
# Step 1 data must survive                                            #
# ------------------------------------------------------------------ #

def test_seeded_demo_data_is_untouched(client, query):
    client.post("/register", data=VALID)

    assert count_users(query, "demo@spendly.com") == 1
    assert query("SELECT COUNT(*) AS n FROM expenses")[0]["n"] == 8


def test_get_register_still_renders(client):
    response = client.get("/register")

    assert response.status_code == 200
    assert b"Create your account" in response.data
