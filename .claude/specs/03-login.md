# Spec: Login

## Overview
Implement user login and logout so registered Spendly users can authenticate and end their session. This step wires up `POST /login` to validate credentials against the hashed password stored in the database, writes the user into the Flask session on success, and implements `GET /logout` to clear that session. It is the gateway to all protected routes (profile, expenses) that follow in subsequent steps. `GET /login` already renders `login.html`; this step completes its behaviour.

## Depends on
- Step 01 — Database Setup (`get_db()`, `users` table, and `get_user_by_email()` must be implemented)
- Step 02 — Registration (user rows must exist in the database; session keys `user_id` / `user_name` convention established)

## Routes
- `POST /login` — **new** — validates email/password, starts session, redirects to `/profile` — public
- `GET /logout` — **implement stub** — clears session, redirects to `/login` — logged-in

## Database changes
No new tables or columns. `get_user_by_email(email)` already exists in `database/db.py` and is sufficient.

## Templates
- **Modify:** `templates/login.html`
  - Set `method="POST"` and `action="{{ url_for('login') }}"` on the form (remove any hardcoded URL)
  - Ensure fields: `name="email"` and `name="password"`
  - Render `{{ error }}` message when present (same pattern as `register.html`)

## Files to change
- `app.py` — add `POST` method to the `login` route; import `check_password_hash` from `werkzeug.security`; validate credentials and set `session["user_id"]` / `session["user_name"]`; implement `logout` to call `session.clear()` and redirect
- `templates/login.html` — wire form action with `url_for('login')`, add error display

## Files to create
None.

## New dependencies
No new pip packages. Uses:
- `werkzeug.security.check_password_hash` (already installed)
- `flask.session` (already imported in `app.py`)

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords verified with `werkzeug.security.check_password_hash`; never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- On invalid email or wrong password, re-render `login.html` with `error="Invalid email or password."` — use the same message for both cases to avoid user enumeration
- On success, write `session["user_id"]` and `session["user_name"]` then redirect to `url_for('profile')`
- `logout` must call `session.clear()` (not just pop individual keys) then redirect to `url_for('login')`
- Route functions stay thin — credential lookup goes through `get_user_by_email()` in `database/db.py`

## Definition of done
- [ ] Submitting the login form with valid credentials starts a session and redirects to `/profile`
- [ ] `session["user_id"]` and `session["user_name"]` are set after successful login
- [ ] Submitting with a wrong password shows `"Invalid email or password."` on the same page
- [ ] Submitting with an unregistered email shows `"Invalid email or password."` on the same page
- [ ] Submitting with blank fields shows a validation error on the same page
- [ ] Visiting `/logout` clears the session and redirects to `/login`
- [ ] The login form action uses `url_for('login')`, not a hardcoded string
- [ ] App starts without errors after changes
