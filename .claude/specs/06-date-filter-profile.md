# Spec: Date Filter for Profile Page

## Overview
This feature adds a date range filter to the profile page, allowing users to narrow the transaction history, summary stats, and category breakdown to a specific time window. The user selects a start and end date via a form; the page reloads with those dates as query parameters and all three data sections update to reflect only expenses within that range. This is the first interactive filtering feature in Spendly and sets the pattern for future filter controls.

## Depends on
- Step 04 — Profile Page Design (profile.html template exists)
- Step 05 — Backend Routes Profile (profile route, query helpers in `database/queries.py`, and all four data-fetching functions are implemented)

## Routes
- `GET /profile?from=<date>&to=<date>` — same profile route, extended to accept optional `from` and `to` query parameters — logged-in only

No new routes.

## Database changes
No database changes. The `expenses.date` column already stores dates as `TEXT` in `YYYY-MM-DD` format, which supports direct string comparison for range filtering in SQLite.

## Templates
- **Modify:** `templates/profile.html`
  - Add a date filter form above the transaction history table
  - Form submits via `GET` to `/profile` with `from` and `to` inputs (type="date")
  - Pre-populate inputs with current filter values so they persist after submit
  - Show an "Active filter" indicator when a filter is applied, with a clear/reset link

## Files to change
- `app.py` — read `from` and `to` query params in the `profile()` route; pass them to all three query helpers and back to the template
- `database/queries.py` — add optional `start_date` and `end_date` parameters to `get_recent_transactions()`, `get_summary_stats()`, and `get_category_breakdown()`; apply `WHERE date BETWEEN ? AND ?` when provided
- `templates/profile.html` — add filter form and active-filter indicator

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw SQLite via `get_db()` only
- Parameterised queries only — never f-strings in SQL; date values must be passed as `?` placeholders
- Passwords hashed with werkzeug (unchanged — no auth changes in this step)
- Use CSS variables — never hardcode hex values in new styles
- All templates extend `base.html`
- Default behavior (no query params) must show all expenses — do not break existing profile behavior
- Date validation: if `from` > `to`, treat the filter as invalid and show all expenses with a warning message
- The same date range must be applied consistently to all three sections (stats, transactions, categories) — never filter one but not the others
- `from` and `to` are optional together — if only one is provided, ignore both and show all expenses

## Definition of done
- [ ] Visiting `/profile` with no query params defaults to Last 6 Months (product decision: intentional, not "all expenses")
- [ ] A date filter form with two date inputs (`From` and `To`) is visible on the profile page
- [ ] Submitting the form with a valid date range reloads the page and shows only transactions within that range
- [ ] Summary stats (total spent, transaction count, top category) reflect only the filtered date range
- [ ] Category breakdown reflects only the filtered date range
- [ ] The date inputs are pre-populated with the active filter values after submit
- [ ] An active-filter indicator appears when a filter is applied, with a working "clear" link that returns to `/profile` (no params)
- [ ] Submitting with `from` > `to` shows all expenses (or a visible warning) — no crash
- [ ] Submitting with only one date populated treats the filter as inactive and shows all expenses
