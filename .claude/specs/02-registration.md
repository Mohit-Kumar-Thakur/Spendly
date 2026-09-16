# Spec: Registration

## Overview
Step 2 makes the existing `/register` page real. Today `templates/register.html` renders a
complete three-field form that POSTs to `/register`, but `app.py` only registers a GET handler,
so submitting it returns `405 Method Not Allowed`. This step adds the POST branch, server-side
validation, and two new data-layer helpers so a visitor can create a genuine account whose
password is stored as a werkzeug hash in the `users` table built in Step 1. Registration is the
first point where Spendly writes user-supplied data, so it is also where the project's input
validation and parameterised-query conventions get established for every step that follows.

Registration deliberately stops at account creation. It does **not** start a session, because
sessions, `SECRET_KEY`, and the logged-in experience belong to Step 3 (Login / logout). A
successful registration redirects to `/login` with a confirmation banner, which leaves Step 3 a
clean seam to pick up.

## Depends on
- **Step 1 — Database setup.** Requires the `users` table (with its `UNIQUE` constraint on
  `email`), `get_db()` with `row_factory = sqlite3.Row`, and `init_db()` being called at startup.
  Step 1 is marked ✅ Done in the README roadmap and verified present in `database/db.py`.

No other steps are required. Step 3 (Login / logout) depends on this step, not the reverse.

## Routes
- `GET /register` — renders the registration form — public — **already exists**, unchanged apart
  from the `methods` list.
- `POST /register` — validates the submitted name, email, and password, creates the user, and
  redirects to `/login?registered=1`; on any validation failure re-renders `register.html` with
  an `error` message and the submitted values preserved — public — **new**.
- `GET /login` — **existing route, modified only** to read the `registered` query parameter and
  pass a `success` flag to the template. No change to its access level (public). The login
  form's POST handling remains out of scope for this step.

No other new routes.

## Database changes
**No database changes.** Verified against `database/db.py`: the `users` table already has
`id`, `name`, `email` (`TEXT NOT NULL UNIQUE`), `password_hash`, and `created_at`, which is
everything registration needs. The `SCHEMA` constant must not be edited in this step.

Two new **functions** are added to `database/db.py` (no schema impact):

- `get_user_by_email(email)` — `SELECT id, name, email, password_hash FROM users WHERE email = ?`;
  returns the `sqlite3.Row` or `None`. Written to be reusable by Step 3's login check.
- `create_user(name, email, password)` — hashes `password` with `generate_password_hash`, inserts
  the row inside a `with conn:` block, and returns the new `lastrowid`. Lets `sqlite3.IntegrityError`
  propagate so the caller can treat a lost race on the `UNIQUE` email as a user-facing error.

Both must follow the existing file's shape: open with `get_db()`, wrap the body in
`try: ... finally: conn.close()`.

## Templates

- **Create:** none. Both templates this feature needs already exist.

- **Modify:**
  - `templates/register.html`
    - Change the form action to `{{ url_for('register') }}` to match the `url_for` style used
      everywhere else in `base.html` and the `auth-switch` links.
    - Add `value="{{ name or '' }}"` to the name input and `value="{{ email or '' }}"` to the
      email input so a rejected submission does not wipe what the user typed. The password is
      never echoed back.
    - Add `minlength="8"` to the password input to match the server-side rule and the existing
      "Min. 8 characters" placeholder. This is a convenience only — the server check is
      authoritative.
    - The existing `{% if error %}<div class="auth-error">` block is already correct and stays
      as is.
  - `templates/login.html`
    - Add a success banner above the existing error block:
      `{% if success %}<div class="auth-success">Account created. Sign in to continue.</div>{% endif %}`.

## Files to change
- `app.py` — add `redirect`, `request`, and `url_for` to the `flask` import; import
  `create_user` and `get_user_by_email` from `database.db`; change the `/register` route to
  `methods=["GET", "POST"]` and implement the POST branch; add the `registered` query-parameter
  read to the `/login` route.
- `database/db.py` — add `get_user_by_email()` and `create_user()`. Do not touch `SCHEMA`,
  `init_db()`, or `seed_db()`.
- `templates/register.html` — `url_for` action, sticky `value` attributes, `minlength`.
- `templates/login.html` — success banner block.
- `static/css/style.css` — add an `.auth-success` rule next to the existing `.auth-error` rule
  (around line 413), built from the existing `--accent`, `--accent-light`, and `--radius-sm`
  variables so it mirrors the error banner's spacing and type scale.
- `README.md` — flip the roadmap table row for Step 2 from `⬜ Next` to `✅ **Done**`, move
  `⬜ Next` onto Step 3, and add a "Step 2 — what done actually meant" `<details>` block matching
  the existing Step 1 one. Also update the "1 of 9 steps complete" alt text on the progress
  image. Do this only once the Definition of done below fully passes.

## Files to create
None. Every file this feature touches already exists.

## New dependencies
**No new dependencies.** `flask` and `werkzeug` are already pinned in `requirements.txt`
(`flask==3.1.3`, `werkzeug==3.1.6`), and `werkzeug.security.generate_password_hash` is already
imported in `database/db.py`.

## Rules for implementation
- **No SQLAlchemy or ORMs.** Use the `sqlite3` standard library through the existing `get_db()`.
- **Parameterised queries only.** Never build SQL with f-strings, `%`, `.format()`, or
  concatenation — the email comes straight from user input.
- **Passwords hashed with werkzeug.** Call `generate_password_hash` from
  `werkzeug.security`. A plaintext or custom-hashed password in `password_hash` fails this step.
- **Use CSS variables — never hardcode hex values.** `.auth-success` must be composed from
  `var(--accent)`, `var(--accent-light)`, `var(--radius-sm)` and friends.
- **All templates extend `base.html`.** Both modified templates already do; keep the
  `{% extends %}` and `{% block content %}` structure intact.
- Validate on the **server**, in this order, returning the first failure: name is non-empty after
  `.strip()`; email is non-empty and contains `@`; password is at least 8 characters; email is not
  already registered (checked with `get_user_by_email`). HTML `required` / `minlength` attributes
  are a convenience, not the check.
- Normalise the email before storing and before the duplicate check: `email.strip().lower()`.
  Store `name.strip()`. Do **not** strip or alter the password.
- Wrap `create_user` in `try/except sqlite3.IntegrityError` in the route and surface the same
  "An account with that email already exists." message, so a concurrent duplicate insert cannot
  produce a 500.
- Error messages must not reveal more than needed and must be a single, plain sentence rendered
  through the existing `.auth-error` div.
- **No sessions, no `SECRET_KEY`, no `flash()`, and no login state in this step** — those are
  Step 3. Carry the success message via the `?registered=1` query parameter instead.
- On success, `redirect(url_for("login", registered=1))` — a POST must never return a rendered
  page directly, so a browser refresh cannot double-submit.
- Leave every placeholder route in `app.py` (`/logout`, `/profile`, `/expenses/*`) untouched.

## Definition of done
Each item is verified by running `python app.py` and exercising the app at
`http://localhost:5001`, or by inspecting the database afterwards.

- [ ] `python app.py` starts with no errors and `GET /register` still renders the form.
- [ ] Submitting a valid new name / email / password lands on `/login` with the URL showing
      `?registered=1` and a green "Account created. Sign in to continue." banner above the form.
- [ ] `sqlite3 expense_tracker.db "SELECT name, email, password_hash FROM users ORDER BY id DESC LIMIT 1"`
      shows the new row, with the email lowercased and `password_hash` starting with `scrypt:`
      — never the plaintext password.
- [ ] Submitting the **same email again** (any casing, e.g. `USER@Example.com`) re-renders the
      register page with "An account with that email already exists." and creates no second row —
      `SELECT COUNT(*) FROM users WHERE email = ?` stays at 1.
- [ ] Submitting a password of 7 characters (with the browser's `minlength` bypassed via curl:
      `curl -i -X POST localhost:5001/register -d "name=A&email=a@b.com&password=1234567"`)
      returns a 200 with the validation error, not a 302 and not a new row.
- [ ] Submitting a name of only spaces, or an email with no `@`, returns the matching error and
      creates no row.
- [ ] After any failed submission the name and email fields are still filled in with what was
      typed, and the password field is empty.
- [ ] `curl -i -X POST localhost:5001/register` with valid data returns `302` with a
      `Location` header pointing at `/login` — confirming the POST/redirect/GET pattern.
- [ ] `grep -n "f\"SELECT\|f'SELECT\|% (\|.format(" database/db.py` returns nothing — no string
      interpolation reached the SQL.
- [ ] The demo account from Step 1 (`demo@spendly.com`) is untouched and the 8 seeded expenses
      still exist — `SELECT COUNT(*) FROM expenses` still returns 8.
- [ ] `grep -n "#" static/css/style.css` shows no new hex literal in the `.auth-success` rule.
- [ ] Visiting `/login` directly, with no query parameter, shows **no** success banner.
