# Spec: Login and Logout

## Overview
Step 2 created accounts but gave them nowhere to go: `/login` renders a complete form that POSTs
to itself, and `app.py` handles only GET, so signing in returns `405 Method Not Allowed` — the
same gap registration had before Step 2 closed it. This step gives Spendly a memory of who is
signed in. It adds a `SECRET_KEY`, a session-backed login, a logout that clears it, a
`@login_required` decorator, and a navbar that reflects the current state.

This is the hinge of the whole roadmap. Everything from Step 4 onward is a per-user view, and
none of it can be written until the app can answer "who is asking?". The decorator and the
`current_user` helper introduced here are the seam every later step builds on, which is why they
land now rather than being reinvented in Step 4.

The password check reuses `get_user_by_email()` exactly as Step 2 left it — that function already
returns `password_hash` for precisely this purpose, so no data-layer change is needed to log
someone in.

## Depends on
- **Step 1 — Database setup.** `get_db()`, the `users` table, and the seeded demo account.
- **Step 2 — Registration.** `get_user_by_email()` returning `password_hash`, the
  `?registered=1` success banner on the login page, and the `.auth-error` / `.auth-success`
  banner styles. Both steps are ✅ Done on `main`.

Steps 4 through 9 depend on this one for `@login_required` and `current_user`.

## Routes
- `POST /login` — validates credentials, stores `user_id` in the session, redirects to
  `/profile` — public — **new**.
- `GET /login` — **existing, modified**: redirects an already-logged-in visitor straight to
  `/profile` instead of showing the form again. Keeps the `?registered=1` banner.
- `GET /logout` — clears the session and redirects to `/` — logged-in — **replaces the
  placeholder** that currently returns the string "Logout — coming in Step 3".
- `GET /profile` — **existing placeholder, now guarded** by `@login_required` and rendering a
  real template instead of a string. Full profile content remains Step 4's job.
- `GET /expenses/add`, `/expenses/<int:id>/edit`, `/expenses/<int:id>/delete` — **existing
  placeholders, now guarded** by `@login_required`. Their bodies keep returning their
  "coming in Step N" strings.

No other new routes.

## Database changes
**No database changes.** Verified against `database/db.py`: logging in is a read of
`password_hash`, which `get_user_by_email()` already returns. Sessions are cookie-backed, so
nothing is persisted server-side.

One new **function** is added to `database/db.py` (no schema impact):

- `get_user_by_id(user_id)` — parameterised `SELECT id, name, email FROM users WHERE id = ?`,
  returning the `sqlite3.Row` or `None`. Deliberately **omits `password_hash`**: this is the
  lookup used on every request to resolve the session cookie, and the hash has no business being
  loaded into a request context that only needs a name to greet. Returns `None` for a session
  pointing at a deleted user, which the decorator must treat as logged out.

Do not touch `SCHEMA`, `init_db()`, `seed_db()`, `create_user()`, or `get_user_by_email()`.

## Templates
- **Create:**
  - `templates/profile.html` — a minimal logged-in page extending `base.html`, greeting the user
    by name and confirming the session works. It is a placeholder that Step 4 fills in, not a
    finished profile.

- **Modify:**
  - `templates/base.html` — the `.nav-links` block becomes conditional on `current_user`:
    logged out shows the existing "Sign in" / "Get started" pair unchanged; logged in shows the
    user's first name and a "Sign out" link to `url_for('logout')`. This is the single most
    visible proof that login and logout work.
  - `templates/login.html` — add `value="{{ email or '' }}"` to the email input so a failed
    attempt does not clear it, mirroring what Step 2 did for the register form. The password is
    never echoed. The existing `{% if success %}` and `{% if error %}` blocks stay as they are.

## Files to change
- `app.py` — configure `SECRET_KEY`; import `session` from flask and `check_password_hash` from
  `werkzeug.security`; add the `login_required` decorator and a `current_user` context processor;
  implement `POST /login` and the real `/logout`; apply the decorator to `/profile` and the three
  `/expenses/*` placeholders; render `profile.html` from `/profile`.
- `database/db.py` — add `get_user_by_id()`. Nothing else.
- `templates/base.html` — conditional nav.
- `templates/login.html` — sticky email value.
- `tests/test_login.py` — **new**, the suite for this step.
- `README.md` + `.github/assets/progress.svg` — roadmap to Step 3 ✅ / Step 4 Next, a
  "Step 3 — what done actually meant" `<details>` block, badge to 3 of 9. Only after the
  Definition of done passes.

## Files to create
- `templates/profile.html`
- `tests/test_login.py`

## New dependencies
**No new dependencies.** `flask.session` and `werkzeug.security.check_password_hash` are both
already available from the pinned `flask==3.1.3` / `werkzeug==3.1.6`. `python-dotenv` is
deliberately **not** added — see the `SECRET_KEY` rule below.

## Rules for implementation
- **No SQLAlchemy or ORMs.** `get_user_by_id()` goes through the existing `get_db()`.
- **Parameterised queries only.** The session's `user_id` is user-controlled data — it arrives in
  a cookie — and must never be interpolated into SQL.
- **Passwords hashed with werkzeug.** Verify with `check_password_hash(row["password_hash"], password)`.
  Never compare passwords with `==`, never re-hash the input and compare hashes.
- **Use CSS variables — never hardcode hex values.** Any new nav or profile styling composes from
  the existing tokens; reuse `.nav-links` and `.nav-cta` rather than inventing new colors.
- **All templates extend `base.html`.** `profile.html` must, and must use `{% block content %}`.
- `SECRET_KEY` comes from `os.environ.get("SECRET_KEY", <dev fallback>)`. `.env` is already
  gitignored, but do not add `python-dotenv` — a plain environment variable with a documented
  development default matches the project's "learning project" scope and keeps the dependency
  list where it is. The fallback must be obviously a development value, not a plausible secret.
- **The login error must be identical for an unknown email and a wrong password** — a single
  "Incorrect email or password." Distinct messages let an attacker enumerate registered accounts.
  Normalise the submitted email with `.strip().lower()` first, matching how Step 2 stored it.
- Call `session.clear()` on logout, not `session.pop("user_id")`, so nothing from this session
  survives into the next one.
- **Regenerate session state on login**: call `session.clear()` *before* setting `user_id`, so a
  pre-existing session cannot be carried into the new login.
- `login_required` must use `functools.wraps`, or Flask will raise a duplicate-endpoint error
  when two decorated views share the wrapper's `__name__`.
- A session holding an id that no longer exists in `users` must be treated as logged out, not
  crash. `current_user` returns `None` and the decorator redirects.
- `current_user` is exposed to templates through a **context processor**, so `base.html` can read
  it without every route passing it explicitly.
- Resolve the user **once per request** (`flask.g`), not once per template reference — the navbar
  and the page body must not trigger two separate queries.
- The `/expenses/*` placeholder bodies keep their "coming in Step N" strings. This step adds the
  guard, not the feature.
- **No password change, no "remember me", no password reset, no rate limiting.** Not this step.

## Definition of done
Verified by running `python -m pytest tests/ -v`, then `python app.py` and exercising
`http://localhost:5001`.

- [ ] `python app.py` starts with no errors and `GET /login` still renders the form.
- [ ] Signing in as `demo@spendly.com` / `demo123` redirects to `/profile` and the page greets the
      user by name.
- [ ] The navbar switches after login: "Sign in" / "Get started" are replaced by the user's name
      and "Sign out".
- [ ] A wrong password and an unregistered email produce responses that are identical apart
      from the email echoed back into the form — confirmed by diffing the two responses with
      the submitted address normalised out. The echoed value is the submitter's own input;
      everything else, including the message "Incorrect email or password.", must match, so
      neither response can be used to tell a registered address from an unregistered one.
- [ ] Email casing does not matter: `DEMO@Spendly.com` signs in successfully.
- [ ] After a failed attempt the email field is still filled and the password field is empty.
- [ ] `curl -i -X POST localhost:5001/login` with valid credentials returns `302` with a
      `Location` of `/profile` and a `Set-Cookie: session=...` header.
- [ ] Visiting `/profile` while logged out redirects to `/login`, not a 500 and not a 200.
- [ ] `/expenses/add`, `/expenses/1/edit` and `/expenses/1/delete` all redirect to `/login` when
      logged out, and return their placeholder strings when logged in.
- [ ] `GET /logout` redirects to `/`, the navbar reverts to the logged-out pair, and `/profile`
      is once again blocked.
- [ ] Visiting `/login` while already signed in redirects to `/profile` instead of showing the form.
- [ ] A session cookie naming a deleted user is treated as logged out — the app redirects to
      `/login` rather than raising.
- [ ] `grep -n "== password\|!= password" app.py` returns nothing — the hash check is the only
      comparison.
- [ ] The Step 2 flow still works end to end: register a new account, get redirected to `/login`
      with the banner, then sign in with those exact credentials.
- [ ] The demo account and its 8 seeded expenses are untouched.
