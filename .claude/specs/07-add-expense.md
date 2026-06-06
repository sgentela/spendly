# Spec: Add Expense

## Overview
This step implements the full add-expense flow: a form for logged-in users to record a new expense (amount, category, date, description) and a POST handler that validates input, inserts the row into the `expenses` table, and redirects to the profile page. This is the first write path for expense data and unlocks the rest of the CRUD steps.

## Depends on
- Step 01 — Database setup (`expenses` table, `get_db()`)
- Step 03 — Login/session (`session["user_id"]` available)
- Step 05 — Profile page (redirect destination after save)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert expense, redirect to `/profile` — logged-in only

## Database changes
No new tables or columns. The `expenses` table created in Step 01 already has all required columns:
- `user_id`, `amount`, `category`, `date`, `description`

A new helper `create_expense(user_id, amount, category, date, description)` must be added to `database/db.py`.

## Templates
- **Create:** `templates/add_expense.html` — form with fields: amount, category (dropdown), date, description (optional textarea)
- **Modify:** none

## Files to change
- `app.py` — replace the `GET /expenses/add` stub with full GET + POST handlers
- `database/db.py` — add `create_expense()` helper

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` — page-specific styles

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not applicable here, but no new auth logic either)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Redirect to `/login` if `session["user_id"]` is not set (use `abort(401)` or redirect)
- Amount must be a positive number — reject on server side with a flash message
- Category must be one of the fixed list: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- Date must be a valid YYYY-MM-DD string and not in the future
- Description is optional — store `None` if blank
- After successful insert, redirect to `url_for('profile')` with a success flash message
- Default the date field to today's date (server-rendered into the form via `datetime.date.today()`)

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders a form with amount, category dropdown, date, and description fields
- [ ] Date field is pre-populated with today's date
- [ ] Category dropdown lists exactly: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- [ ] Submitting the form with valid data inserts one row into `expenses` and redirects to `/profile`
- [ ] The new expense appears in the transactions list on the profile page immediately after redirect
- [ ] Submitting with a missing or zero/negative amount re-renders the form with an error message (no row inserted)
- [ ] Submitting with an invalid or missing category re-renders the form with an error message
- [ ] Submitting with a blank date re-renders the form with an error message
- [ ] Description field is optional — form submits successfully when left blank
