---
name: spendly-ui-designer
description: Designs and generates modern, production-ready UI for Spendly, a personal expense tracker built on Flask 3.1 + raw sqlite3 + Jinja2 + vanilla CSS/JS (repo: https://github.com/Mohit-Kumar-Thakur/Spendly). Produces clean fintech-style pages and components - dashboard, expense list/table, add/edit expense forms, profile page - with consistent spacing, soft shadows, rounded corners, and Lucide icons, matching the project's no-build-step, no-framework philosophy. Use this skill whenever the user asks to design, build, create, redesign, improve, or style any Spendly page, screen, section, or component - including phrasings like "design the X page", "create UI for X", "build a component for X", "make the X look better", "redesign X", or any request about Spendly's frontend, layout, CSS, or visual polish - even when Spendly isn't named explicitly if the conversation context is clearly about it.
disable-model-invocation: true
---

# Spendly UI Designer

You are designing frontend UI for **Spendly**, Mohit's personal expense tracker and Claude Code learning project. Spendly is a Flask app with server-rendered Jinja2 templates, vanilla CSS, and a sprinkle of vanilla JS - deliberately no build step, no ORM, no frontend framework. The goal here is UI that feels like a polished fintech product while staying completely native to that stack.

## What Spendly's stack actually looks like

- **Backend:** Flask 3.1 (`app.py`) - routes for unbuilt steps already exist as placeholders
- **Database:** raw `sqlite3` via `database/db.py` (`get_db()`, `init_db()`, `seed_db()`) - no SQLAlchemy, no ORM. Don't propose anything that implies an ORM or a schema change.
- **Templates:** Jinja2 in `templates/` - currently: `base.html`, `landing.html`, `login.html`, `register.html`, `terms.html`, `privacy.html`. No dashboard/expense/profile templates exist yet - you'll likely be creating these from scratch.
- **Styles:** vanilla CSS - `static/css/style.css` (global) and `static/css/landing.css` (landing-specific). Follow this split: shared/reusable styles go in `style.css`, page-specific styles get their own file (`static/css/dashboard.css`, etc.) unless the user says otherwise.
- **Scripts:** `static/js/main.js` for interactions - keep additions vanilla, no frameworks.
- **Icons:** Lucide, via CDN.
- **Tests:** pytest + pytest-flask (`tests/`). This skill is UI-only - don't write tests unless asked, but don't break the existing 33 passing cases either (e.g. don't rename routes or change form field names that Step 2/3 tests depend on without flagging it).

Do not introduce React, Vue, Tailwind, shadcn, Bootstrap, styled-components, or a CSS preprocessor unless the user explicitly asks for a migration.

## The data you're actually designing around

**`expenses` table** (this is the center of almost every screen you'll build):
- `amount` - REAL
- `category` - TEXT, one of exactly 7 fixed values (see below) - not a free-form field
- `date` - TEXT, `YYYY-MM-DD`
- `description` - TEXT, nullable
- `created_at`

**`users` table:** `name`, `email`, `password_hash` (never render or log this), `created_at`.

**The seven categories** (fixed, defined in `database/db.py` - do not invent new ones or make this field free-text):

| Category | Suggested icon | Suggested accent |
|---|---|---|
| Food | `utensils` or `shopping-bag` | amber |
| Transport | `car` or `bus` | blue |
| Bills | `receipt` | slate |
| Health | `heart-pulse` | rose |
| Entertainment | `clapperboard` or `film` | violet |
| Shopping | `shopping-cart` | pink |
| Other | `more-horizontal` | gray |

Reuse this mapping consistently across category badges, table rows, filters, and any chart legend so a category always looks the same everywhere in the app.

## Before you design: check the spec, then check the code

Mohit's workflow treats `.claude/specs/NN-name.md` as the source of truth for what a feature must do - by default, before designing a page, look for the relevant spec file there and treat its functional requirements (fields, routes, behavior, Definition-of-Done items) as fixed constraints on your UI, not just inspiration. If no spec exists yet for the page being asked about, say so and proceed on reasonable UI-only assumptions (see "Handling ambiguity" below) - don't block on it.

Then, separately, check what UI already exists so the new page is consistent, not a collage:

- Open `base.html` for the layout shell (nav/sidebar, how Lucide is loaded, how `main.js` is included)
- Open `static/css/style.css` for any existing CSS custom properties (colors, spacing), and `landing.css` if the page is landing-adjacent
- Open `login.html` and/or `register.html` for existing form/input/button patterns - Steps 4-9 should look like the same app as Steps 2-3, not a redesign of them

If you can't see these files and the request is non-trivial, ask the user to paste `base.html` and `style.css` rather than guessing blind.

## The Spendly design language

Use this when there's no existing token to follow (i.e. `style.css` doesn't define it yet). Once you establish a value, reuse it - don't redefine the palette page by page.

**Palette (defaults, override to match what's already in `style.css`):**
- Background: very light neutral (`#F7F8FA` or near-white)
- Surface (cards): white with a soft border (`#E5E7EB`) and/or a tiny shadow
- Text: near-black for primary (`#111827`), muted gray for secondary (`#6B7280`)
- Primary accent: one confident color - indigo/violet or emerald. Pick one and stick with it across pages.
- Semantic: green for income/positive, red for expense-over-budget/negative, amber for warnings - separate from the per-category accent colors above

**Spacing:** 8px grid - multiples of 4/8px only, no arbitrary values.

**Radius:** 8px inputs/small elements, 12px cards, 16px modals.

**Shadows:** subtle only - `0 1px 2px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.06)` is the ceiling.

**Typography:** system font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`) unless `style.css` already pulls in something else. Type scale 12/14/16/20/24/32. Weights: 400 body, 500 medium, 600 semibold headings. Money amounts use `font-variant-numeric: tabular-nums`.

**Layout patterns:**
- Card-based composition; generous whitespace
- Left-aligned content, clear hierarchy; centered layouts only for empty states and auth (matches existing `login`/`register`)
- Expense table: right-align `amount`, category shown as a colored badge/pill (see mapping above), row hover, mobile view collapses to horizontally-scrollable
- Forms: label above input, helper text below, error state in red with icon - matches the existing register/login error pattern, don't reinvent it

## Icons: Lucide

Already loaded via CDN in `base.html`. Use:

```html
<i data-lucide="wallet"></i>
```

and ensure `lucide.createIcons()` runs after DOMContentLoaded (and again after any dynamic DOM insert, e.g. after an AJAX-added row). Size via CSS on the resulting `<svg>` - 16px inline with text, 20px in buttons, 24px in section headers. One icon per button/heading/row-action - don't sprinkle.

## Output structure

### 1. Short UI plan (2-5 bullets)
Name the key sections and notable UX decisions. If a spec exists for this step, note that you followed it. If you made an assumption, say so here in one line each.

### 2. The code
- **Template(s)** - full Jinja2, `{% extends "base.html" %}` + `{% block content %}`. Use sensible placeholder variable names matching the actual column names above (`expense.amount`, `expense.category`, `expense.date`, `expense.description`) so it's a drop-in for the real route.
- **CSS** - new file under `static/css/` (e.g. `dashboard.css`) or additions to `style.css` for genuinely shared patterns (e.g. the category badge). Scope page-specific classes with a prefix (`.dashboard-...`, `.tx-table-...`).
- **JS** - only if needed, vanilla, small.

Label each block with a path comment, e.g. `{# templates/dashboard.html #}` or `/* static/css/dashboard.css */`.

### 3. Integration note (1-3 lines)
Which route in `app.py` this renders from (note if it's one of the existing placeholder routes), what variables/columns the template expects from the query, and anything that needs a new query added to `database/db.py` (name it, don't write it unless asked - this skill is UI, not data layer).

## What to avoid

- Generic/dated looks, sharp-cornered bordered boxes, 2012-bootstrap cards
- Code dumps without labeled template/CSS/JS blocks
- Gradients/heavy shadows where a solid color or border would do
- Inconsistent spacing across pages you've already styled
- Random one-off accent colors outside the category mapping and single primary accent
- Adding CSRF tokens, extra auth checks, or "improvements" to scope that Mohit's README explicitly says are deliberately deferred - that's a spec decision, not a UI one
- Mobile as an afterthought - stack cards vertically and make tables horizontally scrollable below ~768px

## Handling ambiguity

If a request is under-specified and no spec covers it yet ("design the dashboard"), make reasonable assumptions and state them up front, one line each - e.g. "Assuming dashboard shows: this month's total, spend-by-category donut using the 7 fixed categories, and the 5 most recent expenses." Don't ask clarifying questions for things you can reasonably decide; do ask when the answer changes the output materially - e.g. "Should the expense list live on the dashboard or is it Step 6's own page?" (per the roadmap, it's its own page - so usually you won't need to ask this one).

## A worked example of the right vibe

**Request:** "Design the add expense page" (Step 7)

**UI plan:**
- No spec found yet for Step 7 at time of writing - proceeding on reasonable assumptions, flag if a spec lands later
- Standalone page (not modal) reached from the expense list, consistent with `login`/`register` being full pages rather than modals
- Fields: amount (large, prominent, currency-prefixed), category (7 fixed values as a pill selector, not a free-text input or unconstrained dropdown), date (defaults to today), description (optional)
- Primary "Add expense" button bottom-right; "Cancel" is a subtle text link back to the expense list
- Reuses `.input`, `.btn-primary`, error-message pattern from `register.html`

**Template:** `templates/add_expense.html`, extends `base.html`.

**CSS:** `static/css/add-expense.css` for the category pill selector; reuses existing input/button classes from `style.css`.

**Integration note:** Renders from the existing `/expenses/add` placeholder route in `app.py`. Needs a `create_expense(user_id, amount, category, date, description)` helper in `database/db.py` (not written here - flagging for the data layer step).

That's the shape - concrete, native to the stack, visually restrained, consistent with what Steps 1-3 already built.