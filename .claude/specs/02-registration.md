# Spec: Registration

## Overview
Implement user registration so visitors can create a Spendly account. This step wires up the `POST /register` route, adds DB helpers for user creation, and sets up Flask sessions so the newly registered user is logged in immediately. On success the user is shown a success message and then redirected to the login page. This is the entry point for all authenticated features that follow. It builds directly on Step 01's database schema (the `users` table already exists).

## Depends on
- Step 01 — Database Setup (users table, `get_db()` must be implemented)

## Routes
- `GET /register` — already implemented, renders `register.html` — public
- `POST /register` — **new** — validates form input, creates user, starts session, redirects — public

## Database changes
No new tables or columns. The `users` table from Step 01 is sufficient.

New helper functions to add to `database/db.py`:
- `get_user_by_email(email)` — returns a user row or `None`
- `create_user(name, email, password_hash)` — inserts a new user row, returns the new `id`

## Templates
- **Modify:** `templates/register.html`
  - Change `action="/register"` → `action="{{ url_for('register') }}"` (remove hardcoded URL)
  - Add a "Confirm password" input field (`name="confirm_password"`) directly below the password field

## Files to change
- `app.py` — add `POST` method to the `register` route; import `session`, `redirect`, `request`, `url_for`, `abort` from flask; add `app.secret_key`; validate that `password == confirm_password`
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `templates/register.html` — fix hardcoded form action URL; add confirm password field

## Files to create
None.

## New dependencies
No new pip packages. Uses:
- `werkzeug.security.generate_password_hash` / `check_password_hash` (already installed)
- `flask.session` (built-in)

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`; never store plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.secret_key` must be set before any session usage; use a hard-coded dev string for now (e.g. `"spendly-dev-secret"`) — a comment noting it should come from env in production is acceptable
- On duplicate email, re-render `register.html` with `error="An account with that email already exists."` — do **not** abort
- On validation failure (missing fields, password < 8 chars, passwords do not match), re-render with a descriptive `error` message
- Confirm password check must happen after length check and before the DB duplicate check
- On success, write `session["user_id"]` and `session["user_name"]` then redirect to `url_for('login')`
- Route function must stay thin — all DB work goes through the helpers in `database/db.py`

## Definition of done
- [ ] Submitting the form with valid data creates a new row in `users` with a hashed password
- [ ] After successful registration, the user is redirected to `/login`
- [ ] `session["user_id"]` is set after registration
- [ ] Submitting with mismatched passwords shows `"Passwords do not match."` error on the same page
- [ ] Submitting with an already-registered email shows the error message on the same page without crashing
- [ ] Submitting with a password shorter than 8 characters shows a validation error
- [ ] Submitting with any blank field shows a validation error
- [ ] The form action uses `url_for('register')`, not a hardcoded string
- [ ] No raw SQL strings — all queries use `?` placeholders
- [ ] App starts without errors after changes
