# Spec: Edit Expense

## Overview
Allows a logged-in user to edit any of their existing expense records. Clicking an edit action on the profile page loads a pre-populated form. On submit, the record is updated in the database and the user is redirected back to the profile page. Only the owner of the expense may edit it — any attempt to edit another user's expense results in a 403.

## Depends on
- Step 01 — database schema (expenses table)
- Step 03 — session management (login required)
- Step 05 — `database/queries.py` pattern established
- Step 07 — add-expense form (same validation rules, reuse VALID_CATEGORIES)

## Routes
- `GET /expenses/<int:id>/edit` — render pre-populated edit form — logged-in only
- `POST /expenses/<int:id>/edit` — validate and apply update — logged-in only

## Database changes
No new tables or columns. Two new helper functions are needed in `database/db.py`:

- `get_expense_by_id(expense_id, user_id)` — returns the expense row if it belongs to `user_id`, else `None`
- `update_expense(expense_id, user_id, amount, category, expense_date, description)` — updates the row; scoped to `user_id` so a crafted request cannot overwrite another user's record

## Templates
- **Create:** `templates/edit_expense.html` — form identical in structure to `add_expense.html` but with field values pre-populated from the existing record and form action pointing to the edit route
- **Modify:** `templates/profile.html` — add an edit link/button per expense row that links to `url_for('edit_expense', id=expense.id)`

## Files to change
- `app.py` — replace the stub `GET /expenses/<int:id>/edit` with full GET + POST handler
- `database/db.py` — add `get_expense_by_id()` and `update_expense()`
- `templates/profile.html` — add edit action per expense row

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings or string concatenation in SQL
- `user_id` scope on every query — never fetch or update by `expense_id` alone
- Redirect to `/profile` with a flash message on successful update
- Use `abort(403)` if the expense does not belong to the logged-in user
- Use `abort(404)` if the expense id does not exist at all
- Use `abort(401)` (or redirect to `/login`) if the user is not logged in
- Reuse `VALID_CATEGORIES` from `app.py` for both server-side validation and template rendering
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Amount must be a positive number; date must be a valid `YYYY-MM-DD` string; category must be in `VALID_CATEGORIES`

## Definition of done
- [ ] Visiting `/expenses/1/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for an expense owned by another user returns 403
- [ ] Visiting `/expenses/<id>/edit` for a non-existent id returns 404
- [ ] The edit form loads with all fields pre-populated from the existing expense record
- [ ] Submitting valid changes updates the record in the database and redirects to `/profile`
- [ ] A success flash message is shown on the profile page after a successful edit
- [ ] Submitting an invalid amount (zero, negative, non-numeric) re-renders the form with an error
- [ ] Submitting an invalid category re-renders the form with an error
- [ ] The profile page shows an edit link for each expense row
