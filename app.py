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


@app.route("/profile")
@login_required
def profile():
    # Step 4 fills this in. For now it proves the session resolves.
    return render_template("profile.html")


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
