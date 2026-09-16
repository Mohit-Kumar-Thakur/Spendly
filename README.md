# Spendly

A personal expense tracker built with Flask and SQLite.

> **Why this project exists**
>
> I'm building Spendly to learn [Claude Code](https://claude.com/claude-code). The expense
> tracker is the excuse; the real goal is getting fluent with the tool — writing specs that an
> agent can actually execute, planning before coding, reviewing what the agent produces instead
> of accepting it, and keeping the whole thing in a sane git workflow.
>
> So the interesting part of this repo isn't the app. It's `.claude/specs/` and the commit
> history: each feature starts as a written spec, becomes a plan, gets implemented on its own
> branch, and lands through a pull request.

---

## The workflow I'm practising

Every step of the build follows the same loop:

1. **Write the spec** — a numbered markdown file in `.claude/specs/` describing the schema,
   functions, routes, rules, and a Definition of Done. Concrete enough that there's little left
   to guess.
2. **Plan before touching code** — Claude Code reads the spec and the existing code, asks about
   anything genuinely ambiguous, and writes an implementation plan I approve before any edit.
3. **Implement on a branch** — `feature/<step-name>`, one step per branch.
4. **Verify against the Definition of Done** — every checkbox in the spec gets actually
   exercised, not assumed.
5. **Commit, push, open a PR, merge to `main`.**

Lesson learned the hard way in Step 1: I let the agent write `database/db.py` *before* reading
the spec, and got a perfectly reasonable implementation that didn't match the spec at all — a
`categories` table instead of a `category` column, wrong category list, wrong column names. It
all had to be thrown out and redone. **Spec first, then code.** That's the habit this project is
really teaching.

---

## Tech stack

| | |
| --- | --- |
| Backend | Flask 3.1 |
| Database | SQLite (`sqlite3` standard library — no ORM) |
| Templating | Jinja2 |
| Frontend | Plain HTML + CSS, a little vanilla JavaScript |
| Passwords | `werkzeug.security` |
| Testing | pytest + pytest-flask |

No SQLAlchemy, no build step, no frontend framework. Everything is hand-written so there's
nothing hiding what's actually going on.

---

## Project structure

```
expense-tracker/
├── app.py                  # Flask app, routes, startup DB init
├── database/
│   ├── __init__.py
│   └── db.py               # get_db() / init_db() / seed_db()
├── templates/              # Jinja templates (base, landing, login, register, ...)
├── static/
│   ├── css/                # style.css, landing.css
│   └── js/main.js
├── .claude/
│   └── specs/              # One spec per build step — the source of truth
├── requirements.txt
└── expense_tracker.db      # Created on first run (gitignored)
```

---

## Getting started

```bash
git clone https://github.com/Mohit-Kumar-Thakur/Spendly.git
cd Spendly

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5001**.

The database is created and seeded automatically on startup, so there's no migration step. To
rebuild it from scratch at any point:

```bash
rm expense_tracker.db
python -m database.db
```

### Demo account

| | |
| --- | --- |
| Email | `demo@spendly.com` |
| Password | `demo123` |

Seeded with 8 sample expenses spread across every category. (Login itself arrives in Step 2 —
until then the account just sits in the database.)

---

## Database

Two tables, both created with `CREATE TABLE IF NOT EXISTS` so startup is idempotent.

**`users`**

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | INTEGER | Primary key, autoincrement |
| `name` | TEXT | Not null |
| `email` | TEXT | Not null, unique |
| `password_hash` | TEXT | Not null |
| `created_at` | TEXT | Defaults to `datetime('now')` |

**`expenses`**

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | INTEGER | Primary key, autoincrement |
| `user_id` | INTEGER | Not null, FK → `users.id`, `ON DELETE CASCADE` |
| `amount` | REAL | Not null |
| `category` | TEXT | Not null |
| `date` | TEXT | Not null, `YYYY-MM-DD` |
| `description` | TEXT | Nullable |
| `created_at` | TEXT | Defaults to `datetime('now')` |

Categories are a fixed list in `database/db.py`: **Food, Transport, Bills, Health,
Entertainment, Shopping, Other**.

### Rules the data layer sticks to

- Parameterized queries only — never string formatting in SQL.
- `PRAGMA foreign_keys = ON` on every connection, so a bad `user_id` actually fails instead of
  quietly inserting.
- `row_factory = sqlite3.Row`, so rows are accessed by column name.
- `seed_db()` returns early if any user exists — running it repeatedly can't duplicate data.
- Passwords are hashed with `generate_password_hash`, never stored in plain text.

---

## Build roadmap

| Step | Feature | Status |
| --- | --- | --- |
| 1 | Database setup — schema, connection helper, seed data | ✅ Done |
| 2 | Registration | ⬜ |
| 3 | Login / logout | ⬜ |
| 4 | Profile page | ⬜ |
| 5 | Dashboard | ⬜ |
| 6 | Expense list | ⬜ |
| 7 | Add expense | ⬜ |
| 8 | Edit expense | ⬜ |
| 9 | Delete expense | ⬜ |

Routes for the unbuilt steps already exist in `app.py` as placeholders, so the shape of the app
is visible from the start.

---

## A note on scope

This is a learning project, not production software. The dev server runs in debug mode, there's
no CSRF protection or rate limiting yet, and the demo credentials are committed on purpose.
Don't deploy it anywhere that matters.
