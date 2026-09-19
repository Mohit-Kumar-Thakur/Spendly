import functools
import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import (
    Flask,
    abort,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from database import queries
from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    get_db,
    get_expense,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
    update_expense,
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


def anonymous_only(view):
    """Send signed-in visitors straight to their profile.

    The mirror of login_required. The landing page, the register form and
    the login form are all things you only need while signed out, so
    reaching any of them with a live session means the profile is what
    was actually wanted.
    """
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is not None:
            return redirect(url_for("profile"))
        return view(*args, **kwargs)

    return wrapped


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
@anonymous_only
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
@anonymous_only
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
@anonymous_only
def login():
    if request.method == "GET":
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
    # current_user() may already have cached "nobody" on g earlier in this
    # same request — anonymous_only asks before the session exists. Drop
    # the cache so anything reading it after this point sees the new user.
    g.pop("user", None)
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
    g.pop("user", None)
    return redirect(url_for("landing"))


# Lucide icon per category, fixed by .claude/skills/frontend-design so a
# category looks identical everywhere in the app. Keyed by the exact
# CATEGORIES values in database/db.py.
CATEGORY_ICONS = {
    "Food": "utensils",
    "Transport": "car",
    "Bills": "receipt",
    "Health": "heart-pulse",
    "Entertainment": "clapperboard",
    "Shopping": "shopping-cart",
    "Other": "more-horizontal",
}


def avatar_initials(name):
    """One or two initials for the avatar circle.

    Doing this here rather than in Jinja keeps the template free of
    indexing that would blow up on a single-word or empty name.
    """
    parts = name.split()
    return "".join(part[0] for part in parts[:2]).upper() or "?"


# ------------------------------------------------------------------ #
# Date filtering                                                      #
# ------------------------------------------------------------------ #

DATE_FORMAT = "%Y-%m-%d"

# A filtered table shows the whole range rather than the ten most recent
# rows: choosing a range and then seeing only part of it would be worse
# than no filter at all. This is a guard against an enormous range, not a
# page size.
TXN_LIMIT = 100

# Label and key for each preset chip, in the order they are shown. The
# template iterates this, so the chips and the resolver below can never
# drift apart.
FILTER_PRESETS = (
    ("all", "All time"),
    ("30d", "Last 30 days"),
    ("month", "This month"),
    ("year", "This year"),
)


def _parse_date(value):
    """A YYYY-MM-DD string as a date, or None if it is anything else.

    Everything the query string offers goes through here first, so a value
    that is not a date can never reach the SQL layer.
    """
    try:
        return datetime.strptime(value.strip(), DATE_FORMAT).date()
    except (AttributeError, ValueError):
        return None


def _format_range_label(start, end):
    """Human wording for the range currently in effect.

    Built in Python off queries.MONTHS rather than strftime for the reason
    _format_member_since gives: %B follows the machine's locale, and the
    %-d that would drop the leading zero does not exist on Windows.
    """
    def one(value):
        return "%d %s %d" % (
            value.day, queries.MONTHS[value.month - 1][:3], value.year)

    if start and end:
        # Within one year the year is said once, at the end: "1 Sep – 5 Sep
        # 2026" rather than repeating 2026 either side of the dash.
        if start.year == end.year:
            return "%d %s – %s" % (
                start.day, queries.MONTHS[start.month - 1][:3], one(end))
        return "%s – %s" % (one(start), one(end))
    if start:
        return "Since %s" % one(start)
    if end:
        return "Up to %s" % one(end)
    return "All time"


def resolve_date_range(args, today=None):
    """Turn the query string into a concrete, validated range.

    Returns one dict rather than a pair because the page needs all of it:
    which chip is lit, what the two date inputs should say, how to name
    the range in the surrounding copy, and whether to explain itself.

    Nothing in here can fail the request. Every rejected input falls back
    to all time and sets an error — a profile page that 400s over a typo
    in a date box would be a worse answer than one that shows everything
    and says why. today is injectable so the preset tests can pin it.
    """
    today = today or date.today()
    preset = (args.get("range") or "all").strip().lower()
    start = end = None
    error = None

    if preset == "custom":
        # Empty is not the same as wrong: a blank end means "open ended",
        # while an unparseable one means the whole filter is untrustworthy.
        raw_start, raw_end = args.get("start", ""), args.get("end", "")
        start, end = _parse_date(raw_start), _parse_date(raw_end)

        if (raw_start and start is None) or (raw_end and end is None):
            start = end = None
            error = "That didn't look like a date — showing all time instead."
        elif start and end and start > end:
            start = end = None
            error = "The start date is after the end date — showing all time."
    elif preset == "30d":
        # Today counts as one of the thirty, so the window is 29 days back.
        start, end = today - timedelta(days=29), today
    elif preset == "month":
        start, end = today.replace(day=1), today
    elif preset == "year":
        start, end = date(today.year, 1, 1), today
    elif preset != "all":
        preset = "all"
        error = "That filter isn't one I know — showing all time."

    # A custom range with nothing in it, or one that was rejected above, is
    # all time by another name. Collapsing it here means the chips, the
    # label and the copy all agree without the template re-deriving it.
    if preset == "custom" and not (start or end):
        preset = "all"

    return {
        "range": preset,
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "label": _format_range_label(start, end),
        "error": error,
    }


# ------------------------------------------------------------------ #
# The expense form                                                    #
# ------------------------------------------------------------------ #

# Above this an amount is far likelier to be a typo than a real expense,
# and an unbounded value has nowhere to sit in the transaction table.
MAX_AMOUNT = 10_000_000

MAX_DESCRIPTION = 200

# Keyed by the query parameter each redirect sets. The text comes from
# here rather than from the URL, so ?added=<anything> can only ever show
# the sentence below or nothing at all.
NOTICES = {
    "added": "Expense added.",
    "updated": "Expense updated.",
}


def owned_expense_or_404(expense_id):
    """Fetch one of the logged-in user's expenses, or give up with a 404.

    Every method of the edit and delete routes goes through here, so the
    four of them cannot drift apart on the ownership check. 404 rather
    than 403 for someone else's expense: a 403 would confirm that the
    expense exists, which is a way of counting other people's records.
    """
    expense = get_expense(expense_id, current_user()["id"])
    if expense is None:
        abort(404)
    return expense


def render_expense_form(action, title, submit_label, expense, error=None):
    """Render the shared add/edit form.

    The GET, the rejected POST and Step 8's edit view all render the same
    template with the same six arguments; routing them through here is
    what stops the three from drifting apart.
    """
    return render_template(
        "expense_form.html",
        form_action=action,
        form_title=title,
        submit_label=submit_label,
        categories=CATEGORIES,
        category_icons=CATEGORY_ICONS,
        expense=expense,
        error=error,
    )


def validate_expense_form(form, today=None):
    """Check one submitted expense and return (values, error).

    Shared by adding and editing so the two can never disagree about what
    a valid expense is — an edit that could store something the add form
    refuses would be a hole in the same wall.

    values always comes back populated, error or not, so a rejected form
    can be re-rendered with what the user actually typed instead of
    clearing itself. First failure wins, the way register() already does
    it, so there is one thing to fix at a time.

    today is injectable so the future-date rule can be tested without
    waiting for tomorrow.
    """
    raw_amount = form.get("amount", "").strip()
    category = form.get("category", "").strip()
    raw_date = form.get("date", "").strip()
    description = form.get("description", "").strip()

    values = {
        "amount": raw_amount,
        "category": category,
        "date": raw_date,
        "description": description,
    }

    parsed_date = _parse_date(raw_date)

    if not raw_amount:
        return values, "Please enter an amount."

    try:
        amount = float(raw_amount)
    except ValueError:
        return values, "Amount must be a number, like 250 or 12.50."

    # float() accepts "inf" and "nan". A stored infinity would turn every
    # SUM on the profile page into inf, and nan fails every comparison
    # including the ones below, so neither can be left to the range check.
    if amount != amount or amount in (float("inf"), float("-inf")):
        return values, "Amount must be a number, like 250 or 12.50."
    if amount <= 0:
        return values, "Amount must be greater than zero."
    if amount > MAX_AMOUNT:
        return values, "That amount looks too large — please check it."

    if category not in CATEGORIES:
        return values, "Please choose one of the listed categories."

    if parsed_date is None:
        return values, "Please enter a valid date."
    if parsed_date > (today or date.today()):
        # Every Step 6 preset ends at today, so a future expense would be
        # invisible under all of them and the page would disagree with
        # itself about what has been spent.
        return values, "An expense cannot be dated in the future."

    if len(description) > MAX_DESCRIPTION:
        return values, ("Description must be %d characters or fewer."
                        % MAX_DESCRIPTION)

    # The parsed, normalised row — what the caller hands to the database.
    values["amount"] = round(amount, 2)
    values["date"] = parsed_date.isoformat()
    # Empty means "no description", which the column stores as NULL. An
    # empty string would render as a blank cell that looks like a bug.
    values["description"] = description or None

    return values, None


@app.route("/profile")
@login_required
def profile():
    # login_required has already resolved the session, so this id exists.
    user_id = current_user()["id"]

    date_filter = resolve_date_range(request.args)
    start, end = date_filter["start"], date_filter["end"]

    # The first of "added", "updated", "deleted" that is present. Only the
    # key is read from the URL; the sentence comes from NOTICES.
    notice = next((text for key, text in NOTICES.items()
                   if key in request.args), None)

    # Four independent reads rather than one joined query: each answers a
    # different section of the page, and a join would have to fan the
    # user row out across every expense to get them in one trip.
    user = queries.get_user_by_id(user_id)
    stats = queries.get_summary_stats(user_id, start, end)

    return render_template(
        "profile.html",
        profile_user=user,
        initials=avatar_initials(user["name"]),
        stats=stats,
        expenses=queries.get_recent_transactions(user_id, TXN_LIMIT,
                                                 start, end),
        breakdown=queries.get_category_breakdown(user_id, start, end),
        category_icons=CATEGORY_ICONS,
        date_filter=date_filter,
        filter_presets=FILTER_PRESETS,
        notice=notice,
        # Short-circuited: the extra query only runs when the range came
        # back empty, which is the only time the two empty states differ.
        has_expenses=bool(stats["transaction_count"])
        or queries.has_any_expenses(user_id),
    )


# ------------------------------------------------------------------ #
# Expense routes                                                      #
# ------------------------------------------------------------------ #

@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    action = url_for("add_expense")

    if request.method == "GET":
        # Today is the overwhelmingly common answer, and the only value
        # the date input can be pre-filled with that is certain to pass
        # validation.
        blank = {"amount": "", "category": "", "description": "",
                 "date": date.today().isoformat()}
        return render_expense_form(action, "Add an expense",
                                   "Add expense", blank)

    values, error = validate_expense_form(request.form)

    if error:
        # values, not the empty form — nothing typed is lost to a mistake
        # in one field.
        return render_expense_form(action, "Add an expense",
                                   "Add expense", values, error)

    # The owner comes from the session. Reading it from the form would let
    # anyone file expenses against somebody else's account.
    create_expense(current_user()["id"], **values)

    # POST/redirect/GET so a refresh cannot file the same expense twice.
    return redirect(url_for("profile", added=1))

@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(id):
    # Fetched before anything is parsed, so an id that is not the user's
    # 404s without the form data ever being looked at.
    expense = owned_expense_or_404(id)
    action = url_for("edit_expense", id=id)

    if request.method == "GET":
        # "%.2f" so the field opens reading 12.50 rather than 12.5,
        # matching the amount as the transaction table prints it.
        return render_expense_form(action, "Edit expense", "Save changes", {
            "amount": "%.2f" % expense["amount"],
            "category": expense["category"],
            "date": expense["date"],
            "description": expense["description"],
        })

    values, error = validate_expense_form(request.form)

    if error:
        # The submitted values, not the stored ones — what the user is
        # looking at is their unsaved edit, and re-rendering the database
        # row would silently throw it away.
        return render_expense_form(action, "Edit expense", "Save changes",
                                   values, error)

    if not update_expense(id, current_user()["id"], **values):
        # Nothing matched, so the row went between opening the form and
        # saving it. A confirmation banner here would be a lie.
        abort(404)

    return redirect(url_for("profile", updated=1))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/<int:id>/delete")
@login_required
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
