# Spec: Delete Expense

## Overview
Allows a logged-in user to permanently delete one of their own expense records. Clicking the Delete link on the profile page loads a confirmation page showing the expense details. Submitting the confirmation form performs the deletion and redirects back to the profile page with a success flash message. Only the owner of the expense may delete it — any attempt to delete another user's expense (or a non-existent record) results in a 404.

## Depends on
- Step 01 — database schema (expenses table)
- Step 03 — session management (login required)
- Step 08 — `get_expense_by_id(expense_id, user_id)` already exists and follows the same auth pattern

## Routes
- `GET /expenses/<int:id>/delete` — render confirmation page showing the expense to be deleted — logged-in only
- `POST /expenses/<int:id>/delete` — perform the deletion — logged-in only

## Database changes
No new tables or columns. One new helper function needed in `database/db.py`:

- `delete_expense(expense_id, user_id)` — deletes the row scoped to `user_id`; returns `cursor.rowcount` so a 0 return (race between confirm-page load and form submit) can be surfaced as a 404

## Templates
- **Create:** `templates/delete_expense.html` — confirmation page showing the expense amount, category, date, and description, with a "Yes, delete" POST form and a "Cancel" link back to `/profile`
- **Modify:** `templates/profile.html` — add a Delete link in the existing `col-actions` cell alongside the Edit link

## Files to change
- `app.py` — replace the stub `GET /expenses/<int:id>/delete` with a full GET + POST handler
- `database/db.py` — add `delete_expense(expense_id, user_id)`
- `templates/profile.html` — add Delete link per expense row in the `col-actions` cell

## Files to create
- `templates/delete_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings or string concatenation in SQL
- `user_id` scope on every query — never delete by `expense_id` alone
- Use `get_expense_by_id(expense_id, user_id)` (already in `db.py`) to fetch the expense before rendering the confirmation page
- Use `abort(404)` if the expense does not exist or does not belong to the logged-in user
- Redirect to `/profile` with a flash message on successful deletion
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Passwords hashed with werkzeug (no passwords touched in this step, but rule stands)
- The confirmation page must use a `<form method="POST">` — never perform a destructive action on a GET request

## Definition of done
- [ ] Visiting `/expenses/1/delete` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/delete` for a non-existent or another user's expense returns 404
- [ ] The confirmation page shows the expense details (amount, category, date, description)
- [ ] Clicking "Cancel" on the confirmation page returns the user to `/profile` without deleting anything
- [ ] Submitting the confirmation form deletes the record from the database
- [ ] After deletion the user is redirected to `/profile` with a "Expense deleted successfully!" flash message
- [ ] The deleted expense no longer appears in the profile transaction list
- [ ] The profile page shows a Delete link for each expense row
