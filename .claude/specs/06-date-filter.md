# Spec: Date Filter

## Overview
Step 6 lets a logged-in user narrow their profile page to a date range. Today
`/profile` always shows everything a user has ever spent, which stops being
useful the moment the transaction list grows past a screenful. This step adds a
filter bar above the transaction history with four presets — All time, This
month, Last 30 days, This year — plus a custom start/end pair, and makes the
summary stats, the transaction table and the category breakdown all answer for
the same selected range. Filtering is server-side through query parameters on a
plain GET form: no AJAX, no JavaScript, and the filtered view is a real URL that
can be bookmarked, shared and reloaded.

## Depends on
- Step 1: Database setup (`expenses.date` stored as `YYYY-MM-DD` TEXT)
- Step 3: Login / Logout (`session["user_id"]`, `login_required`)
- Step 4: Profile page UI (filter bar sits inside the existing layout)
- Step 5: Backend connection (`database/queries.py` helpers to extend)

## Routes
No new routes. The existing `GET /profile` route is modified to read optional
query parameters — logged-in only, unchanged access level:

- `GET /profile` — unfiltered, all time (current behaviour, still the default)
- `GET /profile?range=month` — current calendar month to date
- `GET /profile?range=30d` — the last 30 days, today inclusive
- `GET /profile?range=year` — current calendar year to date
- `GET /profile?range=all` — explicit all time, same as no parameter
- `GET /profile?range=custom&start=YYYY-MM-DD&end=YYYY-MM-DD` — custom range

## Database changes
No database changes. `expenses.date` is already TEXT in `YYYY-MM-DD` form, which
sorts and compares correctly as a string, so `date >= ? AND date <= ?` is a
valid range test without any casting or new column.

## Templates
- **Modify**: `templates/profile.html`
  - Add a filter bar directly above the "Transaction history" heading: the four
    presets as links, and a custom range as a `GET` form with two
    `<input type="date">` fields and an Apply button.
  - The active preset is marked with `aria-current="page"` and a modifier class
    so it reads as selected.
  - The custom inputs are pre-filled with the range currently in effect, so
    reloading or editing one end never loses the other.
  - The three summary-stat notes read the active range ("across all time"
    becomes e.g. "1 Sep – 17 Sep 2026") instead of always claiming all time.
  - The transaction table's empty row and the breakdown's empty paragraph gain
    range-aware wording — "No expenses between 1 Sep and 5 Sep 2026" rather than
    the first-run "Nothing here yet" message, which stays for an empty account.
  - A `filter_error` message renders inside the filter bar when the submitted
    dates are unusable.

## Files to change
- `app.py` — `profile()` parses and validates the query parameters, resolves
  them to a concrete `(start, end)` pair, and passes the range plus its label
  into the template; a module-level helper owns the parsing so the route stays
  readable
- `database/queries.py` — `get_summary_stats`, `get_recent_transactions` and
  `get_category_breakdown` each take optional `start=None, end=None` and add the
  range predicate when given
- `templates/profile.html` — filter bar, active states, range-aware copy
- `static/css/profile.css` — `.profile-filter*` styles for the bar, preset
  chips, date inputs and the error message

## Files to create
- `tests/test_date_filter.py` — unit tests for the ranged query helpers and
  route tests for the filtered page

## New dependencies
No new dependencies. Date parsing uses `datetime` from the standard library.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — the two date bounds are bound values, never
  string-formatted into the SQL
- Passwords hashed with werkzeug (unchanged; nothing here touches auth)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no new JavaScript — the presets are links and the custom
  range is a plain `GET` form, so the page works with scripting disabled
- Currency must always display as ₹
- `start` and `end` are both **inclusive**
- Dates are validated with `datetime.strptime(value, "%Y-%m-%d")`. Anything that
  fails to parse is rejected — never passed through to SQL
- `start=None, end=None` must mean "no range predicate", so every existing
  caller and the Step 5 tests keep working unchanged
- Presets are computed from `date.today()` at request time, not cached at import
- Invalid input never 500s and never silently lies: a malformed date, an unknown
  `range` value, or `start` later than `end` falls back to all time and sets
  `filter_error` so the page says why it is showing everything
- A custom range with only one end filled is honoured as an open-ended range
  (start only = from that date onward; end only = up to that date)
- The filtered transaction list shows every row in range up to a cap of 100;
  the `limit` parameter keeps its default of 10 for callers that omit it
- The range label is formatted as "1 Sep – 17 Sep 2026" and built in Python, not
  Jinja, for the same locale reason `_format_member_since` spells out months

## Tests to write

### Unit tests
File: `tests/test_date_filter.py`

| Function | Input | Expected output |
|---|---|---|
| `get_summary_stats` | `start="2026-09-01", end="2026-09-05"` | `total_spent` 135.80, `transaction_count` 3, `top_category` "Bills" |
| `get_summary_stats` | range containing no expenses | `{"total_spent": 0, "transaction_count": 0, "top_category": "—"}` |
| `get_summary_stats` | `start=None, end=None` | identical to the unfiltered Step 5 result (337.54 / 8 / "Shopping") |
| `get_recent_transactions` | `start="2026-09-10", end="2026-09-16"` | 3 rows, newest first, every date inside the range |
| `get_recent_transactions` | boundary range `start="2026-09-01", end="2026-09-01"` | 1 row — both bounds inclusive |
| `get_recent_transactions` | range containing no expenses | empty list |
| `get_recent_transactions` | `start` only, no `end` | every expense on or after that date |
| `get_category_breakdown` | `start="2026-09-01", end="2026-09-05"` | 3 categories, `pct` integers summing to 100 |
| `get_category_breakdown` | range containing no expenses | empty list |
| range resolver | `range=month` | start is the 1st of the current month, end is today |
| range resolver | `range=30d` | end is today, start is 29 days earlier |
| range resolver | `range=year` | start is 1 January of the current year, end is today |
| range resolver | `range=all` or missing | `(None, None)` |
| range resolver | `range=custom` with malformed `start` | `(None, None)` plus an error message |
| range resolver | `start` later than `end` | `(None, None)` plus an error message |

### Route tests
`GET /profile?range=custom&start=2026-09-01&end=2026-09-05` — authenticated as
the seed user:
- Returns 200
- Shows ₹135.80 as total spent and 3 transactions
- Contains "Electricity bill" and does not contain "New running shoes"
- Breakdown lists Bills, Transport and Food only

`GET /profile?range=custom&start=2026-01-01&end=2026-01-31` (empty range):
- Returns 200
- Shows ₹0.00, 0 transactions, and the range-aware empty message
- Does not show the first-run "Nothing here yet" copy

`GET /profile?range=custom&start=not-a-date&end=2026-09-05`:
- Returns 200, not 400 or 500
- Shows the unfiltered totals (₹337.54, 8 transactions)
- Contains the filter error message

`GET /profile?range=custom&start=2026-09-30&end=2026-09-01` (reversed):
- Returns 200 with unfiltered totals and the filter error message

`GET /profile?range=banana`:
- Returns 200 with unfiltered totals

`GET /profile?range=month` — unauthenticated:
- Redirects to `/login` (302) and renders no expense data

`GET /profile` (no parameters):
- Exactly the same data as before Step 6 — 8 transactions, ₹337.54

## Definition of done
- [ ] `/profile` with no query string still shows all 8 seeded expenses and ₹337.54
- [ ] Clicking "Last 30 days", "This month" and "This year" each reload the page with the matching `?range=` URL and the clicked chip visibly selected
- [ ] Entering 2026-09-01 and 2026-09-05 in the custom fields shows exactly 3 transactions, ₹135.80 total, and "Bills" as top category
- [ ] The category breakdown for that range shows 3 categories whose percentages add up to 100 %
- [ ] Both bounds are inclusive — a start and end of 2026-09-01 returns the ₹12.50 canteen lunch
- [ ] The summary-stat notes and the empty states name the active range rather than "across all time"
- [ ] After filtering, the two date inputs still show the dates that are in effect
- [ ] A reversed range and a mistyped date each render the full unfiltered page plus a visible explanation — no traceback, no 500
- [ ] The filtered URL can be copied into a new tab and reproduces the same view
- [ ] A brand-new user with no expenses sees ₹0.00 and the first-run empty copy under every preset
- [ ] All amounts still display the ₹ symbol
- [ ] The whole suite passes, including the Step 5 tests, with no changes to them
