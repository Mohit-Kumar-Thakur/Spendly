# Spec: Delete Expense

## Overview
Step 9 closes the loop: an expense filed by mistake can be removed. It is the
last of the four operations and the only irreversible one, so the shape of the
step is driven by that. Deleting takes two moves — an Edit-style "Delete" action
on the transaction row opens a confirmation page showing exactly which expense
is about to go, and only the form on that page actually removes it. The removal
itself is a `POST`, never a `GET`, so no link a browser or crawler might follow
on its own can destroy data. Ownership is enforced the same way Step 8 enforces
it: in SQL, with a missing expense and someone else's expense giving the same
404.

## Depends on
- Step 1: Database setup (`expenses.id`)
- Step 3: Login / Logout (`login_required` and the session user)
- Step 5: Backend connection (the table the action sits in)
- Step 7: Add expense (the notice banner and the button styles)
- Step 8: Edit expense (`get_expense`, `_owned_expense_or_404`, the Actions column, and the `id` on each transaction row)

## Routes
The existing `/expenses/<int:id>/delete` placeholder becomes a real two-method
route. Logged-in only, and additionally owner-only:

- `GET /expenses/<int:id>/delete` — confirmation page naming the expense — logged-in, owner only
- `POST /expenses/<int:id>/delete` — delete the row, then redirect to `/profile?deleted=1` — logged-in, owner only

Keeping `GET` as a harmless confirmation page rather than removing it is
deliberate: it means the action in the table is a plain link with no JavaScript
behind it, while the destructive half is still `POST`-only.

Both methods return **404** for an unknown id and for another user's id, for the
same reason as Step 8.

`GET /profile` reads one more optional query parameter, `deleted`, for the
confirmation banner.

## Database changes
No database changes, and no soft-delete column. `DELETE` removes the row
outright. An `is_deleted` flag would mean every query in `database/queries.py`
growing a filter it does not have today, and the confirmation step is the
safeguard this project's scope calls for.

## Templates
- **Create:** `templates/delete_expense.html`
  - A centred confirmation card in the `.auth-card` idiom: a heading, the
    expense's date, category badge, description and amount laid out so the user
    can see they are deleting the right thing, a warning that it cannot be
    undone, a `POST` form with a single destructive submit button, and a Cancel
    link back to `/profile`.
- **Modify:** `templates/profile.html`
  - The Actions column from Step 8 gains a "Delete" link next to "Edit".
  - The `?deleted=1` notice reuses the Step 7 banner with its own wording.

## Files to change
- `app.py` — `delete_expense(id)` becomes a `GET`/`POST` view reusing
  `_owned_expense_or_404` from Step 8
- `database/db.py` — `delete_expense(expense_id, user_id)`, scoped by `user_id`
  in the `WHERE` clause and returning whether a row was removed
- `templates/profile.html` — the Delete action and the deleted notice
- `static/css/style.css` — `.btn-danger` for the destructive submit, alongside
  the button styles Step 7 added
- `static/css/profile.css` — the delete action's muted-to-danger hover
- `tests/test_login.py` — the `/expenses/1/delete` placeholder assertion becomes
  an assertion that the confirmation page renders

## Files to create
- `templates/delete_expense.html`
- `tests/test_delete_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only
- Passwords hashed with werkzeug (unchanged; nothing here touches auth)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no new JavaScript
- Currency must always display as ₹
- **The deletion happens on `POST` only.** A `GET` that deletes would be
  destroyed by any link prefetcher, and the confirmation step would be
  meaningless
- **Ownership is enforced in SQL** — `DELETE FROM expenses WHERE id = ? AND
  user_id = ?`. The confirmation page having already checked is not enough; the
  id is resubmitted with the form and must be re-checked at the point of the
  write
- `delete_expense` returns whether a row was removed, and the view treats zero
  rows as a 404, so double-submitting the confirmation form does not pretend to
  delete something twice
- Deleting is scoped to exactly one row — the `WHERE` names a primary key, and
  the statement is never executed without both bound parameters
- Other users' expenses and the user's other expenses are untouched; a test
  asserts the surrounding rows survive, not just that the count dropped by one
- The confirmation page shows the real stored values, read fresh, not values
  passed through the query string
- No CSRF token, consistent with the rest of the project
- The `GUARDED` list in `tests/test_login.py` keeps working unchanged because
  `GET` on the delete route stays a valid 200 page for the owner

## Tests to write

### Unit tests
File: `tests/test_delete_expense.py`

| Function | Input | Expected outcome |
|---|---|---|
| `delete_expense` | id 1, its real owner | returns truthy; the row is gone and the other 7 remain |
| `delete_expense` | id 1, a different user's id | returns falsy; all 8 rows remain |
| `delete_expense` | an id that does not exist | returns falsy, no exception |
| `delete_expense` | the same id twice | truthy then falsy |
| `delete_expense` | one of two users' expenses | the other user's rows are untouched |
| `get_summary_stats` | after deleting the ₹120.00 shopping expense | total 217.54, count 7, top category no longer "Shopping" |

### Route tests
`GET /expenses/1/delete` authenticated as the owner:
- Returns 200
- Names the expense — its description, its amount and its category
- Contains a form posting to `/expenses/1/delete`
- Deletes nothing — the count is still 8 afterwards
- No longer contains "coming in Step 9"

`POST /expenses/1/delete` as the owner:
- Returns 302 to `/profile`
- The row is gone, 7 remain, and the remaining 7 are the ones that were not
  deleted
- Following the redirect, the profile shows 7 transactions, the reduced total,
  and a confirmation banner
- The deleted description no longer appears anywhere on the page

`POST /expenses/1/delete` twice:
- The second attempt returns 404 and removes nothing further

`GET` and `POST /expenses/999/delete`, authenticated:
- Both return 404

`GET` and `POST /expenses/1/delete` as a second registered user:
- Both return 404, and all 8 rows survive

`GET` and `POST /expenses/1/delete` unauthenticated:
- Both redirect to `/login`, and all 8 rows survive

`GET /profile` authenticated:
- Has a delete link for every transaction shown, pointing at the right ids

Deleting the last remaining expense:
- The profile page falls back to the first-run empty state, shows ₹0.00, and
  the breakdown is empty rather than dividing by zero

## Definition of done
- [ ] Every row of the transaction table has a Delete action next to Edit
- [ ] Clicking it opens a confirmation page naming that exact expense — date, category, description and amount
- [ ] Nothing is deleted by opening that page
- [ ] Cancel returns to `/profile` with the expense still there
- [ ] Confirming removes exactly that one expense and returns to `/profile`
- [ ] The transaction count drops from 8 to 7 and the total drops by exactly the deleted amount
- [ ] The category breakdown percentages still add up to 100 % afterwards
- [ ] A confirmation banner appears after deleting and is gone on the next plain visit to `/profile`
- [ ] Refreshing the confirmation page after deleting gives a 404, not a second deletion
- [ ] `/expenses/999/delete` returns 404 by `GET` and by `POST`
- [ ] Signed in as a second account, both methods return 404 and the seed user still has all 8 expenses
- [ ] Signed out, both methods bounce to `/login` and delete nothing
- [ ] Deleting every expense leaves the profile on the first-run empty state, not a broken page
- [ ] Deleting an expense does not touch any other user's data
- [ ] The whole suite passes, including Steps 2–8
