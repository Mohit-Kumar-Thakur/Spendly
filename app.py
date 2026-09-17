import functools
import os
import sqlite3

from flask import (
    Flask,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_db,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)

# Sessions are signed with this. The fallback is a development value on
# purpose — set SECRET_KEY in the environment for anything real.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-not-a-secret")

# Make sure the database exists and has demo data before any route runs.
with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Authentication helpers                                              #
# ------------------------------------------------------------------ #

def current_user():
    """The logged-in user row, or None.

    Cached on g so the navbar and the page body share one query per
    request. A session pointing at a deleted user counts as logged out.
    """
    if "user" not in g:
        user_id = session.get("user_id")
        g.user = get_user_by_id(user_id) if user_id else None
    return g.user


@app.context_processor
def inject_current_user():
    """Let base.html read current_user without every route passing it."""
    return {"current_user": current_user()}


def login_required(view):
    """Send anonymous visitors to the login page.

    functools.wraps is load-bearing: without it every decorated view
    would register under the wrapper's name and Flask would reject the
    second one as a duplicate endpoint.
    """
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    # Normalise what we store, but never touch the password itself.
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    # First failure wins, so the user fixes one thing at a time.
    error = None
    if not name:
        error = "Please enter your name."
    elif not email or "@" not in email:
        error = "Please enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif get_user_by_email(email):
        error = "An account with that email already exists."

    if error is None:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            # Another request claimed this email between the check above
            # and the insert. Same message, no 500.
            error = "An account with that email already exists."

    if error:
        # Hand back name and email so the form stays filled in.
        # The password is never echoed.
        return render_template("register.html", error=error,
                               name=name, email=email)

    # POST/redirect/GET so a refresh cannot submit twice.
    return redirect(url_for("login", registered=1))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if current_user():
            return redirect(url_for("profile"))
        # "registered" is set by the redirect out of /register.
        return render_template("login.html",
                               success=request.args.get("registered"))

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = get_user_by_email(email)

    # One message for both an unknown email and a wrong password —
    # separate wording would let anyone enumerate registered accounts.
    if user is None or not check_password_hash(user["password_hash"],
                                               password):
        return render_template("login.html",
                               error="Incorrect email or password.",
                               email=email)

    # Clear first so nothing from a previous session survives the login.
    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    # clear(), not pop() — nothing from this session should survive.
    session.clear()
    return redirect(url_for("landing"))


# ------------------------------------------------------------------ #
# Profile page data                                                   #
#                                                                     #
# Step 4 builds the layout against hardcoded values so the design can  #
# be settled before any querying exists. These three constants mirror  #
# SAMPLE_EXPENSES in database/db.py exactly, so when Step 5 swaps them #
# for real queries the page should not visibly change. Delete this     #
# whole block then.                                                    #
# ------------------------------------------------------------------ #

# Newest first — the order a real "recent transactions" query would use.
PROFILE_EXPENSES = [
    {"date": "2026-09-16", "description": "Coffee and pastry",
     "category": "Food", "amount": 8.75},
    {"date": "2026-09-13", "description": "Birthday gift",
     "category": "Other", "amount": 25.00},
    {"date": "2026-09-11", "description": "New running shoes",
     "category": "Shopping", "amount": 120.00},
    {"date": "2026-09-09", "description": "Streaming subscription",
     "category": "Entertainment", "amount": 15.99},
    {"date": "2026-09-07", "description": "Pharmacy - cold medicine",
     "category": "Health", "amount": 32.00},
    {"date": "2026-09-05", "description": "Electricity bill",
     "category": "Bills", "amount": 78.30},
    {"date": "2026-09-03", "description": "Monthly metro pass",
     "category": "Transport", "amount": 45.00},
    {"date": "2026-09-01", "description": "Lunch at the canteen",
     "category": "Food", "amount": 12.50},
]

PROFILE_STATS = {
    "total": 337.54,          # the eight amounts above, summed
    "count": 8,
    "top_category": "Shopping",
}

# "bar" is a width percentage scaled against the largest category, not a
# share of the total — small categories would otherwise all flatten to a
# stub. Rounded to 5 because the widths come from a CSS class ladder
# (.bar-w-*), since the spec forbids inline styles.
PROFILE_BREAKDOWN = [
    {"category": "Shopping",      "total": 120.00, "bar": 100},
    {"category": "Bills",         "total": 78.30,  "bar": 65},
    {"category": "Transport",     "total": 45.00,  "bar": 40},
    {"category": "Health",        "total": 32.00,  "bar": 25},
    {"category": "Other",         "total": 25.00,  "bar": 20},
    {"category": "Food",          "total": 21.25,  "bar": 20},
    {"category": "Entertainment", "total": 15.99,  "bar": 15},
]

# Hardcoded for now; Step 5 reads users.created_at instead.
PROFILE_MEMBER_SINCE = "September 2026"


def avatar_initials(name):
    """One or two initials for the avatar circle.

    Doing this here rather than in Jinja keeps the template free of
    indexing that would blow up on a single-word or empty name.
    """
    parts = name.split()
    return "".join(part[0] for part in parts[:2]).upper() or "?"


@app.route("/profile")
@login_required
def profile():
    user = current_user()
    return render_template(
        "profile.html",
        initials=avatar_initials(user["name"]),
        member_since=PROFILE_MEMBER_SINCE,
        stats=PROFILE_STATS,
        expenses=PROFILE_EXPENSES,
        breakdown=PROFILE_BREAKDOWN,
    )


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/add")
@login_required
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
@login_required
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
@login_required
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
