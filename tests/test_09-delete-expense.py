"""
tests/test_09-delete-expense.py

Tests for the Delete Expense feature (Step 09) of Spendly.

Spec: .claude/specs/09-delete-expense.md

Behaviours under test:
  1.  Auth guard — GET /expenses/<id>/delete while logged out redirects to /login
  2.  Auth guard — POST /expenses/<id>/delete while logged out redirects to /login
  3.  GET /expenses/<id>/delete for a non-existent id returns 404
  4.  POST /expenses/<id>/delete for a non-existent id returns 404
  5.  GET /expenses/<id>/delete for an expense owned by another user returns 404
  6.  POST /expenses/<id>/delete for an expense owned by another user returns 404
  7.  GET happy path — returns 200 and shows expense amount on the confirmation page
  8.  GET happy path — shows expense category on the confirmation page
  9.  GET happy path — shows expense date on the confirmation page
 10.  GET happy path — shows expense description on the confirmation page
 11.  GET confirmation page contains a Cancel link back to /profile
 12.  GET confirmation form uses method="POST"
 13.  POST happy path — expense row no longer exists in DB after deletion
 14.  POST happy path — response redirects to /profile (302)
 15.  POST happy path — flash message "Expense deleted successfully!" visible on profile page
 16.  Expense no longer appears in profile transaction list after deletion
 17.  Cross-user POST — another user's expense row is unchanged after the 404
 18.  Cancel (GET only) — expense row still exists in DB after visiting confirmation page
 19.  Profile page contains a Delete link for each expense row
"""

import pytest
from database.db import get_db


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIXED_DATE = "2026-05-15"
FIXED_AMOUNT = 50.00
FIXED_CATEGORY = "Food"
FIXED_DESCRIPTION = "Lunch at work"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _register_and_login(client, name="Delete Test User", email="delete_test@spendly.com",
                        password="testpass1") -> None:
    """Register a fresh user and log in via the test client."""
    client.post("/register", data={
        "name":             name,
        "email":            email,
        "password":         password,
        "confirm_password": password,
    })
    client.post("/login", data={
        "email":    email,
        "password": password,
    })


def _get_user_id(email: str) -> int:
    """Fetch user id by email from the test DB."""
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"]


def _insert_expense(user_id: int, amount: float = FIXED_AMOUNT,
                    category: str = FIXED_CATEGORY,
                    expense_date: str = FIXED_DATE,
                    description: str = FIXED_DESCRIPTION) -> int:
    """Insert a single expense and return its id."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


def _get_expense_by_id(expense_id: int) -> dict | None:
    """Fetch a raw expense row from the test DB by id (no user_id scope)."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_client(client, app):
    """Logged-in client for the primary test user (no expenses pre-seeded)."""
    with app.app_context():
        _register_and_login(client)
    return client


@pytest.fixture
def auth_client_with_expense(client, app):
    """
    Logged-in client with exactly one expense pre-inserted.
    Returns (client, expense_id).
    """
    with app.app_context():
        _register_and_login(client)
        uid = _get_user_id("delete_test@spendly.com")
        expense_id = _insert_expense(uid)
    return client, expense_id


@pytest.fixture
def second_user_expense(client, app):
    """
    Creates a second user with one expense.
    Returns the id of the expense owned by the second user.
    The test client is logged in as the PRIMARY user (delete_test@spendly.com).
    """
    with app.app_context():
        # Create primary user and log in
        _register_and_login(client, name="Primary User", email="delete_test@spendly.com")
        # Create second user via direct DB insert
        from werkzeug.security import generate_password_hash
        conn = get_db()
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Other User", "other_delete@spendly.com",
             generate_password_hash("otherpass1")),
        )
        other_uid = cursor.lastrowid
        conn.commit()
        conn.close()
        expense_id = _insert_expense(
            other_uid, amount=99.00, description="Other user's expense"
        )
    return expense_id


# ---------------------------------------------------------------------------
# 1 & 2. Auth guard — logged out
# ---------------------------------------------------------------------------

class TestAuthGuard:

    def test_get_delete_expense_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/999/delete")
        assert response.status_code == 302, \
            "Unauthenticated GET /expenses/<id>/delete must redirect (302)"
        assert "/login" in response.headers["Location"], \
            "Unauthenticated GET must redirect to /login"

    def test_post_delete_expense_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/999/delete")
        assert response.status_code == 302, \
            "Unauthenticated POST /expenses/<id>/delete must redirect (302)"
        assert "/login" in response.headers["Location"], \
            "Unauthenticated POST must redirect to /login, not perform the deletion"


# ---------------------------------------------------------------------------
# 3 & 4. Non-existent expense id → 404
# ---------------------------------------------------------------------------

class TestNotFound:

    def test_get_non_existent_expense_returns_404(self, auth_client):
        response = auth_client.get("/expenses/99999/delete")
        assert response.status_code == 404, \
            "GET for a non-existent expense id must return 404"

    def test_post_non_existent_expense_returns_404(self, auth_client):
        response = auth_client.post("/expenses/99999/delete")
        assert response.status_code == 404, \
            "POST for a non-existent expense id must return 404"


# ---------------------------------------------------------------------------
# 5 & 6. Expense belongs to another user → 404
# get_expense_by_id is scoped to user_id, so a cross-user access looks
# identical to a missing record — the route aborts with 404 in both cases.
# ---------------------------------------------------------------------------

class TestCrossUserAccess:

    def test_get_other_users_expense_returns_404(self, second_user_expense, client, app):
        """Primary logged-in user must receive 404 when GETting another user's delete page."""
        other_expense_id = second_user_expense
        response = client.get(f"/expenses/{other_expense_id}/delete")
        assert response.status_code == 404, \
            "GET for an expense owned by another user must return 404 (avoids ID enumeration)"

    def test_post_other_users_expense_returns_404(self, second_user_expense, client, app):
        """Primary logged-in user must receive 404 when POSTing to another user's delete endpoint."""
        other_expense_id = second_user_expense
        response = client.post(f"/expenses/{other_expense_id}/delete")
        assert response.status_code == 404, \
            "POST targeting another user's expense must return 404 (avoids ID enumeration)"


# ---------------------------------------------------------------------------
# 7–10. GET happy path — confirmation page content
# ---------------------------------------------------------------------------

class TestGetConfirmationPage:

    def test_get_returns_200_for_own_expense(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/delete")
        assert response.status_code == 200, \
            "GET /expenses/<id>/delete for own expense must return 200"

    def test_get_shows_expense_amount(self, client, app):
        """The confirmation page must display the expense amount."""
        with app.app_context():
            _register_and_login(client)
            uid = _get_user_id("delete_test@spendly.com")
            expense_id = _insert_expense(uid, amount=123.45)
        response = client.get(f"/expenses/{expense_id}/delete")
        assert b"123.45" in response.data, \
            "Confirmation page must show the expense amount (123.45)"

    def test_get_shows_expense_category(self, client, app):
        """The confirmation page must display the expense category."""
        with app.app_context():
            _register_and_login(client)
            uid = _get_user_id("delete_test@spendly.com")
            expense_id = _insert_expense(uid, category="Transport")
        response = client.get(f"/expenses/{expense_id}/delete")
        assert b"Transport" in response.data, \
            "Confirmation page must show the expense category (Transport)"

    def test_get_shows_expense_date(self, client, app):
        """The confirmation page must display the expense date."""
        with app.app_context():
            _register_and_login(client)
            uid = _get_user_id("delete_test@spendly.com")
            expense_id = _insert_expense(uid, expense_date="2026-03-22")
        response = client.get(f"/expenses/{expense_id}/delete")
        assert b"2026-03-22" in response.data, \
            "Confirmation page must show the expense date (2026-03-22)"

    def test_get_shows_expense_description(self, client, app):
        """The confirmation page must display the expense description when present."""
        with app.app_context():
            _register_and_login(client)
            uid = _get_user_id("delete_test@spendly.com")
            expense_id = _insert_expense(uid, description="Unique confirm desc 99887")
        response = client.get(f"/expenses/{expense_id}/delete")
        assert b"Unique confirm desc 99887" in response.data, \
            "Confirmation page must show the expense description"


# ---------------------------------------------------------------------------
# 11. Cancel link points back to /profile
# ---------------------------------------------------------------------------

class TestCancelLink:

    def test_confirmation_page_contains_cancel_link_to_profile(
            self, auth_client_with_expense):
        """The confirmation page must contain a link back to /profile."""
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/delete")
        html = response.data.decode()
        assert "/profile" in html, \
            "Confirmation page must contain a cancel link pointing to /profile"

    def test_cancel_link_is_an_anchor_tag(self, auth_client_with_expense):
        """The cancel navigation must be an <a> tag with an href to /profile."""
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/delete")
        html = response.data.decode()
        assert 'href' in html and '/profile' in html, \
            "Confirmation page must include an anchor tag linking to /profile for cancel"


# ---------------------------------------------------------------------------
# 12. Confirmation form uses POST method — no destructive action on GET
# ---------------------------------------------------------------------------

class TestFormMethod:

    def test_confirmation_form_uses_post_method(self, auth_client_with_expense):
        """The delete confirmation form must declare method='POST'."""
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/delete")
        assert (b'method="POST"' in response.data or
                b'method="post"' in response.data), \
            "Delete confirmation form must use method='POST' — destructive action must not occur on GET"


# ---------------------------------------------------------------------------
# 13. POST happy path — DB side effect: expense row removed
# ---------------------------------------------------------------------------

class TestPostDeletesFromDb:

    def test_valid_post_removes_expense_from_db(self, auth_client_with_expense, app):
        """After a valid POST the expense row must no longer exist in the database."""
        client, expense_id = auth_client_with_expense
        client.post(f"/expenses/{expense_id}/delete")
        with app.app_context():
            row = _get_expense_by_id(expense_id)
        assert row is None, \
            f"Expense id={expense_id} must not exist in the DB after a successful DELETE POST"

    def test_valid_post_decrements_expense_count(self, auth_client_with_expense, app):
        """The total number of expense rows for the user must decrease by exactly 1."""
        client, expense_id = auth_client_with_expense
        with app.app_context():
            uid = _get_user_id("delete_test@spendly.com")
            conn = get_db()
            count_before = conn.execute(
                "SELECT COUNT(*) AS cnt FROM expenses WHERE user_id = ?", (uid,)
            ).fetchone()["cnt"]
            conn.close()

        client.post(f"/expenses/{expense_id}/delete")

        with app.app_context():
            conn = get_db()
            count_after = conn.execute(
                "SELECT COUNT(*) AS cnt FROM expenses WHERE user_id = ?", (uid,)
            ).fetchone()["cnt"]
            conn.close()

        assert count_after == count_before - 1, \
            f"Expense count must decrease by 1 after deletion (was {count_before}, got {count_after})"


# ---------------------------------------------------------------------------
# 14. POST happy path — redirect to /profile
# ---------------------------------------------------------------------------

class TestPostRedirect:

    def test_valid_post_redirects_to_profile(self, auth_client_with_expense):
        """A valid DELETE POST must return a 302 redirect."""
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/delete")
        assert response.status_code == 302, \
            "Valid DELETE POST must redirect (302)"
        assert "/profile" in response.headers["Location"], \
            "Valid DELETE POST must redirect to /profile"


# ---------------------------------------------------------------------------
# 15. POST happy path — flash message visible on profile page
# ---------------------------------------------------------------------------

class TestFlashMessage:

    def test_success_flash_visible_on_profile_after_delete(self, auth_client_with_expense):
        """Flash message 'Expense deleted successfully!' must appear on /profile after deletion."""
        client, expense_id = auth_client_with_expense
        client.post(f"/expenses/{expense_id}/delete")
        response = client.get("/profile?preset=all_time", follow_redirects=True)
        assert b"Expense deleted successfully!" in response.data, \
            "Flash message 'Expense deleted successfully!' must appear on /profile after deletion"

    def test_success_flash_visible_following_redirect(self, auth_client_with_expense):
        """Following the redirect from the DELETE POST must deliver the flash message."""
        client, expense_id = auth_client_with_expense
        response = client.post(
            f"/expenses/{expense_id}/delete", follow_redirects=True
        )
        assert b"Expense deleted successfully!" in response.data, \
            "Flash message must be visible when following the POST redirect to /profile"


# ---------------------------------------------------------------------------
# 16. Expense no longer appears in profile transaction list
# ---------------------------------------------------------------------------

class TestExpenseGoneFromProfile:

    def test_deleted_expense_not_in_profile_list(self, client, app):
        """After deletion the expense's unique description must not appear in the profile list."""
        with app.app_context():
            _register_and_login(client)
            uid = _get_user_id("delete_test@spendly.com")
            expense_id = _insert_expense(
                uid, description="UniqueSentinel87654", expense_date="2026-05-15"
            )

        client.post(f"/expenses/{expense_id}/delete")
        response = client.get("/profile?preset=all_time")
        assert b"UniqueSentinel87654" not in response.data, \
            "Deleted expense's description must not appear in the profile transaction list"

    def test_other_expenses_still_on_profile_after_deletion(self, client, app):
        """Deleting one expense must leave the user's other expenses visible on the profile."""
        with app.app_context():
            _register_and_login(client)
            uid = _get_user_id("delete_test@spendly.com")
            expense_to_delete = _insert_expense(
                uid, description="ToBeDeleted", expense_date="2026-05-10"
            )
            expense_to_keep = _insert_expense(
                uid, description="ShouldRemain99", expense_date="2026-05-11"
            )

        client.post(f"/expenses/{expense_to_delete}/delete")
        response = client.get("/profile?preset=all_time")
        assert b"ShouldRemain99" in response.data, \
            "Surviving expense must still appear in the profile list after deleting a different expense"


# ---------------------------------------------------------------------------
# 17. Cross-user POST — target record is untouched
# ---------------------------------------------------------------------------

class TestCrossUserPostLeavesRecordUnchanged:

    def test_post_to_other_users_expense_does_not_delete_record(
            self, second_user_expense, client, app):
        """A 404 cross-user POST must not remove the target expense from the DB."""
        other_expense_id = second_user_expense
        with app.app_context():
            original = _get_expense_by_id(other_expense_id)

        client.post(f"/expenses/{other_expense_id}/delete")

        with app.app_context():
            after = _get_expense_by_id(other_expense_id)

        assert after is not None, \
            "Another user's expense must still exist in the DB after a cross-user DELETE POST"
        assert abs(after["amount"] - original["amount"]) < 0.001, \
            "Another user's expense amount must be unchanged after a cross-user DELETE POST"
        assert after["description"] == original["description"], \
            "Another user's expense description must be unchanged after a cross-user DELETE POST"


# ---------------------------------------------------------------------------
# 18. Cancel (GET only) — expense row still exists in DB
# ---------------------------------------------------------------------------

class TestCancelDoesNotDelete:

    def test_get_confirmation_page_does_not_delete_expense(
            self, auth_client_with_expense, app):
        """Visiting the confirmation page (GET) must not delete the expense."""
        client, expense_id = auth_client_with_expense
        client.get(f"/expenses/{expense_id}/delete")
        with app.app_context():
            row = _get_expense_by_id(expense_id)
        assert row is not None, \
            "GET to the confirmation page must NOT delete the expense — only POST should do that"

    def test_multiple_gets_do_not_delete_expense(self, auth_client_with_expense, app):
        """Multiple visits to the confirmation page must not trigger deletion."""
        client, expense_id = auth_client_with_expense
        client.get(f"/expenses/{expense_id}/delete")
        client.get(f"/expenses/{expense_id}/delete")
        client.get(f"/expenses/{expense_id}/delete")
        with app.app_context():
            row = _get_expense_by_id(expense_id)
        assert row is not None, \
            "Repeated GET requests to the confirmation page must not delete the expense"


# ---------------------------------------------------------------------------
# 19. Profile page contains a Delete link per expense row
# ---------------------------------------------------------------------------

class TestProfileDeleteLink:

    def test_profile_shows_delete_link_for_expense(self, auth_client_with_expense):
        """The profile page must contain a delete link pointing to the expense's delete route."""
        client, expense_id = auth_client_with_expense
        response = client.get("/profile?preset=all_time")
        html = response.data.decode()
        assert f"/expenses/{expense_id}/delete" in html, \
            f"Profile page must contain a delete link for expense id={expense_id}"
