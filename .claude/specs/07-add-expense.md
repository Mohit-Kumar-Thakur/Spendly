# Spec: Add Expense

## Overview
Step 7 is the first step where Spendly stops being read-only. Everything up to
here reads the eight rows `seed_db()` inserted; from here a user can put their
own spending in. This step adds a full-page add-expense form reached from the
profile page, validates what comes back, writes one row to `expenses`, and
returns the user to `/profile` where the new expense is immediately visible in
the summary cards, the transaction table and the category breakdown. The form is
a plain server-rendered `POST` — no AJAX, no modal, no JavaScript — matching the
way registration and login already work.

## Depends on
- Step 1: Database setup (`expenses` table, the seven fixed `CATEGORIES`)
- Step 3: Login / Logout (`session["user_id"]`, `login_required`)
- Step 4: Profile page UI (where the entry point and the result both live)
- Step 5: Backend connection (the queries the new row flows into)
- Step 6: Date filter (the notice banner sits above the filter bar)

## Routes
The existing `/expenses/add` placeholder becomes a real two-method route.
Logged-in only, unchanged access level:

- `GET /expenses/add` — render the empty form, date pre-filled with today — logged-in
- `POST /expenses/add` — validate and insert, then redirect to `/profile?added=1` — logged-in

`GET /profile` is unchanged as a route, but now reads one extra query parameter,
`added`, purely to decide whether to show a confirmation banner.

## Database changes
No database changes. `expenses` already has `user_id`, `amount`, `category`,
`date`, `description` and a defaulted `created_at`, which is exactly the row
this form writes. `description` is already nullable, which is what lets it stay
optional.

## Templates
- **Create:** `templates/expense_form.html`
  - One form template, not an `add_expense.html`, because Step 8 renders the
    identical fields with values filled in. It is driven by variables —
    `form_title`, `form_subtitle`, `form_action`, `submit_label`, `expense`,
    `error` — so Step 8 reuses it without a second copy of the markup.
  - Fields: amount (currency-prefixed, `inputmode="decimal"`), category (the
    seven fixed values as a radio pill selector, not free text), date
    (`<input type="date">`, defaulting to today), description (optional).
  - Errors render in the existing `.auth-error` pattern, one message at a time,
    and every field is re-filled from what was submitted — nothing typed is lost
    to a validation failure.
  - Cancel is a quiet text link back to `/profile`, mirroring `.auth-switch`.
- **Modify:** `templates/profile.html`
  - An "Add expense" primary button in the "Transaction history" heading row.
  - The first-run empty state invites the user to add their first expense
    instead of only stating that there is nothing there.
  - A success notice above the filter bar when `?added=1` is present, which
    disappears on the next plain visit to `/profile`.

## Files to change
- `app.py` — `add_expense()` becomes a `GET`/`POST` view; a module-level
  `validate_expense_form(form)` helper owns parsing and validation so Step 8 can
  reuse it verbatim; `profile()` passes the notice through to the template
- `database/db.py` — `create_expense()` write helper, next to `create_user()`
- `templates/profile.html` — entry point, empty-state call to action, notice
- `static/css/style.css` — the notice and small-button styles, because Step 8
  and Step 9 both reuse them
- `static/css/profile.css` — the heading row that puts the button beside the
  title, and the notice block
- `tests/test_login.py` — the placeholder assertion for `/expenses/add` no
  longer holds and becomes an assertion that the real form renders

## Files to create
- `templates/expense_form.html`
- `static/css/expense-form.css`
- `tests/test_add_expense.py`

## New dependencies
No new dependencies. Parsing uses `datetime` and the built-in `float()`.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — every one of the five inserted values is a bound
  parameter
- Passwords hashed with werkzeug (unchanged; nothing here touches auth)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no new JavaScript
- Currency must always display as ₹
- `user_id` comes from the session, never from the form. A posted `user_id`
  field is ignored outright — otherwise anyone could file expenses against
  another account
- `category` is validated against `database.db.CATEGORIES` by exact match. An
  unknown category is rejected rather than stored, so the badge map, the
  breakdown and the filters can keep assuming seven values
- `amount` is parsed with `float()`, must be strictly greater than zero, and is
  rounded to 2 decimal places before insert. A blank, non-numeric, zero or
  negative amount is a validation error, never a 500 and never a stored row
- `amount` is capped at 10,000,000. Above that is far likelier to be a typo than
  a real expense, and an unbounded value breaks the table layout
- `date` is validated with `datetime.strptime(value, "%Y-%m-%d")`, exactly as
  Step 6 validates its filter bounds
- A date in the future is rejected. Step 6's presets all end at today, so a
  future expense would be invisible under every preset except All time — the
  page would quietly disagree with itself
- `description` is optional, stripped, capped at 200 characters, and stored as
  `NULL` when empty rather than as an empty string
- Validation reports one error at a time, first failure wins, the same way
  `register()` already does
- On success, redirect rather than render — `POST`/redirect/`GET`, so a refresh
  cannot file the same expense twice
- The seven category radios are rendered by looping `CATEGORIES`, never by
  hand-writing seven blocks, so adding a category stays a one-line change
- No CSRF token. The README defers that deliberately for the whole project;
  this step does not quietly change that decision
- Returning to the filter that was active before clicking "Add expense" is out
  of scope — the redirect goes to the unfiltered `/profile`

## Tests to write

### Unit tests
File: `tests/test_add_expense.py`

| Function | Input | Expected outcome |
|---|---|---|
| `create_expense` | valid row for the seed user | returns the new id; the row reads back with the exact values |
| `create_expense` | `description=None` | row stores `NULL`, not `""` |
| `create_expense` | `user_id` that does not exist | raises `sqlite3.IntegrityError` (foreign key) |
| `validate_expense_form` | all four fields valid | no error; amount is a rounded float, date is `YYYY-MM-DD` |
| `validate_expense_form` | amount `""` | error naming the amount |
| `validate_expense_form` | amount `"abc"` | error, no exception |
| `validate_expense_form` | amount `"0"` and `"-5"` | error for both |
| `validate_expense_form` | amount `"12.567"` | accepted, rounded to `12.57` |
| `validate_expense_form` | amount `"99999999"` | error — above the cap |
| `validate_expense_form` | category `"Bitcoin"` | error — not one of the seven |
| `validate_expense_form` | category `""` | error |
| `validate_expense_form` | date `"31-09-2026"` | error — wrong format |
| `validate_expense_form` | date one day in the future | error |
| `validate_expense_form` | date exactly today | accepted |
| `validate_expense_form` | description of 300 characters | error — over the cap |
| `validate_expense_form` | description `"  "` | accepted, stored value is `None` |

### Route tests
`GET /expenses/add` authenticated:
- Returns 200 and contains all seven category labels
- The date field is pre-filled with today's date
- No longer contains "coming in Step 7"

`GET /expenses/add` unauthenticated:
- Redirects to `/login` (302)

`POST /expenses/add` with a valid expense, authenticated as the seed user:
- Returns 302 to `/profile`
- `expenses` now holds 9 rows for that user, the new one with the posted values
- Following the redirect, the page shows the new description and the updated
  total (₹337.54 plus the new amount)
- The page shows a confirmation banner

`POST /expenses/add` unauthenticated:
- Redirects to `/login` and inserts nothing — the count stays at 8

`POST /expenses/add` with each invalid field in turn (bad amount, bad category,
bad date, future date, over-long description):
- Returns 200, re-renders the form, no redirect
- Shows an error message
- Inserts nothing — the count stays at 8
- Keeps the other fields filled in

`POST /expenses/add` with a `user_id` field naming another user:
- The row is filed against the logged-in user, not the posted one

`POST /expenses/add` twice with the same data:
- Two separate rows — an expense is not deduplicated

A second registered user posting an expense:
- Their expense appears on their profile and not on the seed user's

## Definition of done
- [ ] `/expenses/add` renders a styled form instead of the Step 7 placeholder string
- [ ] The category selector shows exactly the seven categories from `database/db.py`
- [ ] The date field opens pre-filled with today
- [ ] Submitting ₹250 of "Food" dated today with a description redirects to `/profile`
- [ ] The profile page then shows 9 transactions and a total ₹250 higher
- [ ] The new expense appears in the transaction table with the right badge and icon
- [ ] The category breakdown percentages still add up to 100 %
- [ ] A confirmation banner appears after adding and is gone on the next plain visit to `/profile`
- [ ] Submitting a blank amount, "abc", 0, -5 or 99999999 re-renders the form with one clear message and stores nothing
- [ ] Submitting a future date is refused with an explanation
- [ ] The description can be left blank and the expense still saves
- [ ] Nothing typed into the form is lost when validation fails
- [ ] Refreshing the page after a successful add does not create a second expense
- [ ] `/expenses/add` bounces to `/login` when signed out, by `GET` and by `POST`
- [ ] The "Add expense" button is reachable from `/profile` and from the first-run empty state
- [ ] The page is usable at 375px wide — the category pills wrap, nothing overflows
- [ ] The whole suite passes, including Steps 2–6
