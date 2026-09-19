# Spec: Edit Expense

## Overview
Step 7 made expenses writable; Step 8 makes them correctable. A mistyped amount
or the wrong category currently has no remedy short of opening the database by
hand. This step adds a per-row "Edit" action to the transaction table on
`/profile`, which opens the same form Step 7 built — this time pre-filled with
the expense as it stands — and saves the change back to the same row. The
interesting part of this step is not the form, which is already written, but
ownership: an expense id in the URL is a number anyone can change, so every read
and every write is scoped to the logged-in user in SQL, and an expense belonging
to somebody else is indistinguishable from one that does not exist.

## Depends on
- Step 1: Database setup (`expenses.id` is the primary key the URL names)
- Step 3: Login / Logout (`login_required`, and the session user that scopes ownership)
- Step 5: Backend connection (`get_recent_transactions` renders the rows that gain the action)
- Step 6: Date filter (the filtered table is where most edits will start)
- Step 7: Add expense (`templates/expense_form.html` and `validate_expense_form` are reused as they are)

## Routes
The existing `/expenses/<int:id>/edit` placeholder becomes a real two-method
route. Logged-in only, and additionally owner-only:

- `GET /expenses/<int:id>/edit` — render the form pre-filled with that expense — logged-in, owner only
- `POST /expenses/<int:id>/edit` — validate and update, then redirect to `/profile?updated=1` — logged-in, owner only

Both methods return **404** for an id that does not exist *and* for an id that
belongs to another user. The two cases are deliberately identical: a 403 on
someone else's expense would confirm that the expense exists, which is a way of
counting other people's records.

`GET /profile` reads one more optional query parameter, `updated`, for the
confirmation banner Step 7 introduced.

## Database changes
No database changes. The row is updated in place; `id`, `user_id` and
`created_at` are never touched, so `created_at` keeps meaning "when this was
first recorded" rather than drifting to the last edit.

## Templates
- **Create:** none. `templates/expense_form.html` from Step 7 already takes
  `form_title`, `form_action`, `submit_label` and `expense`; the edit view
  supplies the existing row instead of an empty one.
- **Modify:** `templates/profile.html`
  - The transaction table gains an "Actions" column: an icon-and-label "Edit"
    link per row, pointing at `url_for('edit_expense', id=expense['id'])`.
  - The header cell is visually hidden text rather than an empty `<th>`, so the
    column is announced to a screen reader without shouting on screen.
  - The `?updated=1` notice reuses the Step 7 banner, with its own wording.

## Files to change
- `app.py` — `edit_expense(id)` becomes a `GET`/`POST` view reusing
  `validate_expense_form`; a small `_owned_expense_or_404(id)` helper does the
  fetch-and-abort so the two methods cannot drift apart on the ownership check;
  `abort` joins the flask import
- `database/db.py` — `get_expense(expense_id, user_id)` and
  `update_expense(expense_id, user_id, amount, category, date, description)`,
  both scoped by `user_id` in the `WHERE` clause
- `database/queries.py` — `get_recent_transactions` selects `id` as well, so the
  table can link each row to its own edit page
- `templates/profile.html` — the Actions column and the updated notice
- `static/css/profile.css` — `.profile-txn-actions` and the `.profile-visually-hidden`
  helper for the header cell
- `tests/test_backend_connection.py` — one assertion pins the exact key set of a
  transaction row and now has to include `id`
- `tests/test_login.py` — the `/expenses/1/edit` placeholder assertion becomes an
  assertion that the pre-filled form renders

## Files to create
- `tests/test_edit_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — the id and the user id are bound values like
  everything else
- Passwords hashed with werkzeug (unchanged; nothing here touches auth)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no new JavaScript
- Currency must always display as ₹
- **Ownership is enforced in SQL, not in Python.** Both `get_expense` and
  `update_expense` carry `AND user_id = ?`. A check done only in the view is one
  forgotten `if` away from letting anyone edit anyone's expenses
- `update_expense` returns whether it changed a row, and the view treats zero
  rows as a 404 — the same answer `GET` gives, so a record that vanishes between
  opening the form and saving it does not 500
- Validation is Step 7's `validate_expense_form`, called unchanged. Editing must
  not be able to store an amount, category or date that adding would refuse
- `id`, `user_id` and `created_at` are never written
- The route reuses `templates/expense_form.html`. If it needs a shape the
  template does not have, the template changes for both steps rather than a
  second near-identical file appearing
- A failed validation re-renders the form with what was submitted, not with what
  is in the database — the user's unsaved edit is what they are looking at
- On success, redirect rather than render, so a refresh cannot replay the update
- Saving without changing anything is a success, not an error
- No CSRF token, consistent with the rest of the project
- Returning to the filter that was active before clicking "Edit" is out of scope,
  exactly as in Step 7

## Tests to write

### Unit tests
File: `tests/test_edit_expense.py`

| Function | Input | Expected outcome |
|---|---|---|
| `get_expense` | id 1, its real owner | the row, with amount, category, date and description |
| `get_expense` | id 1, a different user's id | `None` — never another user's row |
| `get_expense` | an id that does not exist | `None` |
| `update_expense` | id 1, its owner, new values | returns truthy; the row reads back with the new values |
| `update_expense` | id 1, a different user's id | returns falsy; the row is unchanged |
| `update_expense` | an id that does not exist | returns falsy, no exception |
| `update_expense` | valid update | `created_at` is byte-identical before and after |
| `update_expense` | `description=None` | clears the previous description to `NULL` |
| `get_recent_transactions` | seed user | every row carries an `id` alongside date, description, category and amount |

### Route tests
`GET /expenses/1/edit` authenticated as the owner:
- Returns 200
- The amount, category, date and description fields hold the stored values
- The form posts back to `/expenses/1/edit`
- No longer contains "coming in Step 8"

`GET /profile` authenticated:
- Contains an edit link for every transaction shown
- The links point at the ids of the rows actually rendered

`POST /expenses/1/edit` with valid changes, as the owner:
- Returns 302 to `/profile`
- The row holds the new values, and the expense count is still 8 — an edit is
  not an insert
- Following the redirect, the profile shows the new amount and a confirmation
  banner
- The summary total moves by exactly the difference

`POST /expenses/1/edit` changing only the category:
- The amount and date are untouched

`GET` and `POST /expenses/999/edit` (no such expense), authenticated:
- Both return 404

`GET` and `POST /expenses/1/edit` as a second registered user who does not own it:
- Both return 404, and the row is unchanged afterwards

`GET` and `POST /expenses/1/edit` unauthenticated:
- Both redirect to `/login` (302), and the row is unchanged

`POST /expenses/1/edit` with an invalid amount, category, date or future date:
- Returns 200 with an error message and no redirect
- The stored row is unchanged
- The form still shows the rejected input, not the stored values

`POST /expenses/1/edit` resubmitting the values it already has:
- Returns 302, the row is unchanged, and nothing errors

## Definition of done
- [ ] Every row of the transaction table on `/profile` has an Edit action
- [ ] Clicking it opens the form with that expense's amount, category, date and description already filled in
- [ ] Changing the amount from ₹12.50 to ₹20.00 and saving returns to `/profile` with the new amount in the table
- [ ] The total spent moves by exactly ₹7.50 and the transaction count stays at 8
- [ ] Changing only the category moves the row's badge and the breakdown, and leaves the amount alone
- [ ] Changing the date moves the row into or out of the active date filter as expected
- [ ] A confirmation banner appears after saving and is gone on the next plain visit to `/profile`
- [ ] Visiting `/expenses/999/edit` returns a 404 page, not a traceback
- [ ] Signed in as a second account, `/expenses/1/edit` returns 404 by `GET` and by `POST`, and the seed user's expense is untouched afterwards
- [ ] Signed out, both methods bounce to `/login`
- [ ] An invalid amount or a future date is refused with the same wording Step 7 uses, and the stored row does not change
- [ ] Refreshing after a save does not apply the edit twice
- [ ] `created_at` is unchanged by an edit
- [ ] The Actions column does not break the table at 375px wide
- [ ] The whole suite passes, including Steps 2–7
