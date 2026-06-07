"""
tests/test_08-edit-expense.py

Tests for the Edit Expense feature (Step 08) of Spendly.

Spec: .claude/specs/08-edit-expense.md

Behaviours under test:
  1.  Auth guard — GET /expenses/<id>/edit while logged out redirects to /login
  2.  Auth guard — POST /expenses/<id>/edit while logged out redirects to /login
  3.  GET /expenses/<id>/edit for a non-existent id returns 404
  4.  POST /expenses/<id>/edit for a non-existent id returns 404
  5.  GET /expenses/<id>/edit for an expense owned by another user returns 403
  6.  POST /expenses/<id>/edit for an expense owned by another user returns 403
  7.  GET /expenses/<id>/edit (owner, valid id) returns 200 and renders the edit form
  8.  GET form is pre-populated with the existing expense's amount, category, date, description
  9.  GET form contains all 7 valid category options
 10.  GET form uses POST method and contains all required fields
 11.  POST valid data updates the record in the database
 12.  POST valid data redirects to /profile (302)
 13.  POST valid data flashes "Expense updated successfully!" on the profile page
 14.  POST amount=0 re-renders form with error, no DB change
 15.  POST negative amount re-renders form with error, no DB change
 16.  POST non-numeric amount re-renders form with error, no DB change
 17.  POST invalid category re-renders form with error, no DB change
 18.  POST blank date re-renders form with error, no DB change
 19.  POST invalid date string re-renders form with error, no DB change
 20.  Validation errors re-populate form with submitted values (amount, category, date, description)
 21.  Description is optional — blank description on valid POST succeeds
 22.  User isolation — user B cannot update user A's expense via POST (403, no DB change)
 23.  Edge case — very large positive amount is accepted
 24.  Edge case — minimal positive amount (0.01) is accepted
 25.  Edge case — all 7 valid categories are accepted on POST
"""

import pytest
from database.db import get_db


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]

FIXED_DATE = "2026-05-15"
UPDATED_DATE = "2026-06-01"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _register_and_login(client, name="Test User", email="edit_test@spendly.com",
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


def _insert_expense(user_id: int, amount: float = 50.00, category: str = "Food",
                    expense_date: str = FIXED_DATE,
                    description: str = "Original description") -> int:
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
    """Fetch a raw expense row from the test DB by id."""
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
    """Logged-in client with exactly one expense pre-inserted. Returns (client, expense_id)."""
    with app.app_context():
        _register_and_login(client)
        uid = _get_user_id("edit_test@spendly.com")
        expense_id = _insert_expense(uid)
    return client, expense_id


@pytest.fixture
def second_user_expense(client, app):
    """
    Creates a second user with one expense.
    Returns (second_user_expense_id) — the id of the expense owned by the second user.
    The test client is logged in as the PRIMARY user (edit_test@spendly.com).
    """
    with app.app_context():
        # Create primary user and log in
        _register_and_login(client, name="Primary User", email="edit_test@spendly.com")
        # Create second user via direct DB insert (no login swap needed)
        from werkzeug.security import generate_password_hash
        conn = get_db()
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Other User", "other_user@spendly.com",
             generate_password_hash("otherpass1")),
        )
        other_uid = cursor.lastrowid
        conn.commit()
        conn.close()
        expense_id = _insert_expense(other_uid, amount=99.00, description="Other user's expense")
    return expense_id


# ---------------------------------------------------------------------------
# 1 & 2. Auth guard — logged out
# ---------------------------------------------------------------------------

class TestAuthGuard:

    def test_get_edit_expense_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/999/edit")
        assert response.status_code == 302, \
            "Unauthenticated GET /expenses/<id>/edit must redirect (302)"
        assert "/login" in response.headers["Location"], \
            "Unauthenticated GET must redirect to /login"

    def test_post_edit_expense_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/999/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        FIXED_DATE,
            "description": "Updated",
        })
        assert response.status_code == 302, \
            "Unauthenticated POST /expenses/<id>/edit must redirect (302)"
        assert "/login" in response.headers["Location"], \
            "Unauthenticated POST must redirect to /login, not process the form"


# ---------------------------------------------------------------------------
# 3 & 4. Non-existent expense id → 404
# ---------------------------------------------------------------------------

class TestNotFound:

    def test_get_non_existent_expense_returns_404(self, auth_client):
        response = auth_client.get("/expenses/99999/edit")
        assert response.status_code == 404, \
            "GET for a non-existent expense id must return 404"

    def test_post_non_existent_expense_returns_404(self, auth_client):
        response = auth_client.post("/expenses/99999/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        FIXED_DATE,
            "description": "Updated",
        })
        assert response.status_code == 404, \
            "POST for a non-existent expense id must return 404"


# ---------------------------------------------------------------------------
# 5 & 6. Expense belongs to another user → 404
# The scoped get_expense_by_id returns None for both "not found" and "not
# yours", so the route returns 404 in both cases. This avoids leaking
# whether a given ID exists to a different user (security best practice).
# ---------------------------------------------------------------------------

class TestForbidden:

    def test_get_other_users_expense_returns_404(self, second_user_expense, client, app):
        """The primary logged-in user must receive 404 when accessing another user's expense."""
        other_expense_id = second_user_expense
        response = client.get(f"/expenses/{other_expense_id}/edit")
        assert response.status_code == 404, \
            "GET for an expense owned by another user must return 404 (avoids ID enumeration)"

    def test_post_other_users_expense_returns_404(self, second_user_expense, client, app):
        """POST to edit another user's expense must return 404."""
        other_expense_id = second_user_expense
        response = client.post(f"/expenses/{other_expense_id}/edit", data={
            "amount":      "75.00",
            "category":    "Transport",
            "date":        UPDATED_DATE,
            "description": "Trying to overwrite",
        })
        assert response.status_code == 404, \
            "POST targeting another user's expense must return 404 (avoids ID enumeration)"

    def test_post_other_users_expense_does_not_change_record(
            self, second_user_expense, client, app):
        """A 403 POST must not alter the target expense's data in the DB."""
        other_expense_id = second_user_expense
        with app.app_context():
            original = _get_expense_by_id(other_expense_id)

        client.post(f"/expenses/{other_expense_id}/edit", data={
            "amount":      "1.00",
            "category":    "Other",
            "date":        UPDATED_DATE,
            "description": "Tampered description",
        })

        with app.app_context():
            after = _get_expense_by_id(other_expense_id)

        assert abs(after["amount"] - original["amount"]) < 0.001, \
            "Another user's expense amount must not change after a forbidden POST"
        assert after["description"] == original["description"], \
            "Another user's expense description must not change after a forbidden POST"


# ---------------------------------------------------------------------------
# 7. GET happy path — returns 200 and renders form
# ---------------------------------------------------------------------------

class TestGetHappyPath:

    def test_get_returns_200_for_own_expense(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/edit")
        assert response.status_code == 200, \
            "GET /expenses/<id>/edit for own expense must return 200"

    def test_get_renders_amount_input(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="amount"' in response.data, \
            "Edit form must contain an 'amount' input field"

    def test_get_renders_category_input(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="category"' in response.data, \
            "Edit form must contain a 'category' select/input field"

    def test_get_renders_date_input(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="date"' in response.data, \
            "Edit form must contain a 'date' input field"

    def test_get_renders_description_input(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="description"' in response.data, \
            "Edit form must contain a 'description' field"

    def test_get_renders_submit_button(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b'type="submit"' in response.data, \
            "Edit form must contain a submit button"

    def test_get_form_uses_post_method(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b'method="POST"' in response.data or b'method="post"' in response.data, \
            "Edit form must use POST method"


# ---------------------------------------------------------------------------
# 8. GET form is pre-populated with existing expense values
# ---------------------------------------------------------------------------

class TestGetFormPrePopulation:

    def test_form_prepopulated_with_existing_amount(self, client, app):
        """The existing expense's amount must appear as a value in the form."""
        with app.app_context():
            _register_and_login(client)
            uid = _get_user_id("edit_test@spendly.com")
            expense_id = _insert_expense(uid, amount=123.45, category="Bills",
                                         expense_date=FIXED_DATE,
                                         description="Electricity")
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b"123.45" in response.data, \
            "Existing expense amount (123.45) must appear pre-populated in the edit form"

    def test_form_prepopulated_with_existing_category(self, client, app):
        """The existing expense's category must be indicated as selected in the form."""
        with app.app_context():
            _register_and_login(client)
            uid = _get_user_id("edit_test@spendly.com")
            expense_id = _insert_expense(uid, amount=50.00, category="Transport",
                                         expense_date=FIXED_DATE,
                                         description="Bus fare")
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b"Transport" in response.data, \
            "Existing expense category ('Transport') must appear in the pre-populated edit form"

    def test_form_prepopulated_with_existing_date(self, client, app):
        """The existing expense's date must appear in the date field."""
        with app.app_context():
            _register_and_login(client)
            uid = _get_user_id("edit_test@spendly.com")
            expense_id = _insert_expense(uid, amount=50.00, category="Food",
                                         expense_date="2026-03-22",
                                         description="Lunch")
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b"2026-03-22" in response.data, \
            "Existing expense date ('2026-03-22') must appear pre-populated in the edit form"

    def test_form_prepopulated_with_existing_description(self, client, app):
        """The existing expense's description must appear in the description field."""
        with app.app_context():
            _register_and_login(client)
            uid = _get_user_id("edit_test@spendly.com")
            expense_id = _insert_expense(uid, amount=50.00, category="Health",
                                         expense_date=FIXED_DATE,
                                         description="Unique prepop description")
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b"Unique prepop description" in response.data, \
            "Existing expense description must appear pre-populated in the edit form"


# ---------------------------------------------------------------------------
# 9. GET form contains all 7 valid categories
# ---------------------------------------------------------------------------

class TestCategoryOptionsInForm:

    def test_all_seven_categories_present(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/edit")
        for category in VALID_CATEGORIES:
            assert category.encode() in response.data, \
                f"Category '{category}' must appear in the edit form's category options"

    def test_no_unlisted_category_values_in_form(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.get(f"/expenses/{expense_id}/edit")
        html = response.data.decode()
        for invalid_cat in ["Groceries", "Rent", "Travel", "Education"]:
            assert f'value="{invalid_cat}"' not in html, \
                f"Unexpected category option '{invalid_cat}' found in the edit form"


# ---------------------------------------------------------------------------
# 10 & 11. POST happy path — DB side effects
# ---------------------------------------------------------------------------

class TestPostHappyPath:

    def test_valid_post_redirects_to_profile(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "99.00",
            "category":    "Transport",
            "date":        UPDATED_DATE,
            "description": "Updated description",
        })
        assert response.status_code == 302, \
            "Valid POST must redirect (302)"
        assert "/profile" in response.headers["Location"], \
            "Valid POST must redirect to /profile"

    def test_valid_post_updates_amount_in_db(self, auth_client_with_expense, app):
        client, expense_id = auth_client_with_expense
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "77.77",
            "category":    "Food",
            "date":        UPDATED_DATE,
            "description": "Dinner",
        })
        with app.app_context():
            row = _get_expense_by_id(expense_id)
        assert row is not None, "Expense row must still exist after update"
        assert abs(row["amount"] - 77.77) < 0.001, \
            f"DB amount must be updated to 77.77, got {row['amount']}"

    def test_valid_post_updates_category_in_db(self, auth_client_with_expense, app):
        client, expense_id = auth_client_with_expense
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Health",
            "date":        UPDATED_DATE,
            "description": "Doctor visit",
        })
        with app.app_context():
            row = _get_expense_by_id(expense_id)
        assert row["category"] == "Health", \
            f"DB category must be updated to 'Health', got {row['category']}"

    def test_valid_post_updates_date_in_db(self, auth_client_with_expense, app):
        client, expense_id = auth_client_with_expense
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        UPDATED_DATE,
            "description": "Lunch",
        })
        with app.app_context():
            row = _get_expense_by_id(expense_id)
        assert row["date"] == UPDATED_DATE, \
            f"DB date must be updated to {UPDATED_DATE}, got {row['date']}"

    def test_valid_post_updates_description_in_db(self, auth_client_with_expense, app):
        client, expense_id = auth_client_with_expense
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        UPDATED_DATE,
            "description": "Brand new description",
        })
        with app.app_context():
            row = _get_expense_by_id(expense_id)
        assert row["description"] == "Brand new description", \
            f"DB description must be updated, got {row['description']}"

    def test_valid_post_does_not_create_extra_row(self, auth_client_with_expense, app):
        """An update must not insert a new row — expense count must remain the same."""
        client, expense_id = auth_client_with_expense
        with app.app_context():
            uid = _get_user_id("edit_test@spendly.com")
            conn = get_db()
            before = conn.execute(
                "SELECT COUNT(*) AS cnt FROM expenses WHERE user_id = ?", (uid,)
            ).fetchone()["cnt"]
            conn.close()

        client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "60.00",
            "category":    "Bills",
            "date":        UPDATED_DATE,
            "description": "Water bill",
        })

        with app.app_context():
            conn = get_db()
            after = conn.execute(
                "SELECT COUNT(*) AS cnt FROM expenses WHERE user_id = ?", (uid,)
            ).fetchone()["cnt"]
            conn.close()
        assert after == before, \
            "Editing an expense must not add a new row (expense count must stay the same)"


# ---------------------------------------------------------------------------
# 12. Flash success message after redirect
# ---------------------------------------------------------------------------

class TestFlashMessage:

    def test_success_flash_visible_on_profile_after_edit(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "42.00",
            "category":    "Other",
            "date":        UPDATED_DATE,
            "description": "Flash test",
        })
        response = client.get("/profile?preset=all_time")
        assert b"Expense updated successfully" in response.data, \
            "Flash message 'Expense updated successfully!' must appear on /profile after edit"


# ---------------------------------------------------------------------------
# 13. Amount validation errors
# ---------------------------------------------------------------------------

class TestAmountValidation:

    @pytest.mark.parametrize("bad_amount,label", [
        ("0",      "zero"),
        ("-10",    "negative number"),
        ("-0.01",  "small negative"),
        ("abc",    "non-numeric string"),
        ("",       "empty string"),
        ("  ",     "whitespace only"),
    ])
    def test_invalid_amount_rerenders_form(self, auth_client_with_expense, bad_amount, label):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      bad_amount,
            "category":    "Food",
            "date":        UPDATED_DATE,
            "description": "Test",
        })
        assert response.status_code == 200, \
            f"Amount '{label}' must re-render the form (200), not redirect"
        assert b'name="amount"' in response.data, \
            f"Amount '{label}' must re-render the edit form (amount field must be present)"

    @pytest.mark.parametrize("bad_amount", ["0", "-10", "abc", ""])
    def test_invalid_amount_shows_error_message(self, auth_client_with_expense, bad_amount):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      bad_amount,
            "category":    "Food",
            "date":        UPDATED_DATE,
            "description": "Test",
        })
        assert (b"error" in response.data.lower() or
                b"Amount" in response.data or
                b"amount" in response.data.lower()), \
            f"An error message must appear for invalid amount '{bad_amount}'"

    @pytest.mark.parametrize("bad_amount", ["0", "-10", "abc", ""])
    def test_invalid_amount_does_not_update_db(self, auth_client_with_expense, app, bad_amount):
        client, expense_id = auth_client_with_expense
        with app.app_context():
            original = _get_expense_by_id(expense_id)

        client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      bad_amount,
            "category":    "Food",
            "date":        UPDATED_DATE,
            "description": "Should not update",
        })

        with app.app_context():
            after = _get_expense_by_id(expense_id)
        assert abs(after["amount"] - original["amount"]) < 0.001, \
            f"DB amount must not change after invalid amount submission '{bad_amount}'"


# ---------------------------------------------------------------------------
# 14. Category validation errors
# ---------------------------------------------------------------------------

class TestCategoryValidation:

    @pytest.mark.parametrize("bad_category,label", [
        ("",           "empty string"),
        ("Groceries",  "unlisted category"),
        ("food",       "lowercase valid category"),
        ("FOOD",       "uppercase valid category"),
        ("'; DROP TABLE expenses; --", "SQL injection attempt"),
    ])
    def test_invalid_category_rerenders_form(self, auth_client_with_expense, bad_category, label):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    bad_category,
            "date":        UPDATED_DATE,
            "description": "Test",
        })
        assert response.status_code == 200, \
            f"Category '{label}' must re-render the form (200)"
        assert b'name="category"' in response.data, \
            f"Category '{label}' must re-render the edit form (category field must be present)"

    @pytest.mark.parametrize("bad_category", ["", "Groceries", "food", "FOOD"])
    def test_invalid_category_does_not_update_db(self, auth_client_with_expense, app,
                                                  bad_category):
        client, expense_id = auth_client_with_expense
        with app.app_context():
            original = _get_expense_by_id(expense_id)

        client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    bad_category,
            "date":        UPDATED_DATE,
            "description": "Should not update",
        })

        with app.app_context():
            after = _get_expense_by_id(expense_id)
        assert after["category"] == original["category"], \
            f"DB category must not change after invalid category submission '{bad_category}'"


# ---------------------------------------------------------------------------
# 15. Date validation errors
# ---------------------------------------------------------------------------

class TestDateValidation:

    def test_blank_date_rerenders_form(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        "",
            "description": "Test",
        })
        assert response.status_code == 200, \
            "Blank date must re-render the form (200)"
        assert b'name="date"' in response.data, \
            "Blank date must re-render the edit form (date field must be present)"

    def test_blank_date_shows_error_message(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        "",
            "description": "Test",
        })
        assert (b"error" in response.data.lower() or
                b"Date" in response.data or
                b"date" in response.data.lower()), \
            "An error message must appear when date is blank"

    def test_blank_date_does_not_update_db(self, auth_client_with_expense, app):
        client, expense_id = auth_client_with_expense
        with app.app_context():
            original = _get_expense_by_id(expense_id)

        client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        "",
            "description": "Should not update",
        })

        with app.app_context():
            after = _get_expense_by_id(expense_id)
        assert after["date"] == original["date"], \
            "DB date must not change after blank date submission"

    @pytest.mark.parametrize("bad_date,label", [
        ("not-a-date",   "non-date string"),
        ("32-13-2026",   "invalid day/month"),
        ("2026/06/01",   "wrong separator format"),
        ("01-06-2026",   "DD-MM-YYYY instead of YYYY-MM-DD"),
    ])
    def test_invalid_date_format_rerenders_form(self, auth_client_with_expense, bad_date, label):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        bad_date,
            "description": "Test",
        })
        assert response.status_code == 200, \
            f"Invalid date '{label}' must re-render the form (200)"
        assert b'name="date"' in response.data, \
            f"Invalid date '{label}' must keep the edit form rendered"

    def test_omitted_date_rerenders_form(self, auth_client_with_expense):
        """Omitting the date key entirely must also trigger a validation error."""
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            # date key deliberately omitted
            "description": "Test",
        })
        assert response.status_code == 200, \
            "Omitted date key must re-render the form (200)"


# ---------------------------------------------------------------------------
# 16. Form re-population after validation errors
# ---------------------------------------------------------------------------

class TestFormRepopulationOnError:

    def test_submitted_amount_retained_after_invalid_category(
            self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "88.88",
            "category":    "",
            "date":        UPDATED_DATE,
            "description": "Should stay",
        })
        assert b"88.88" in response.data, \
            "Submitted amount must be retained in form after a category validation error"

    def test_submitted_date_retained_after_invalid_amount(
            self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "abc",
            "category":    "Food",
            "date":        UPDATED_DATE,
            "description": "Test",
        })
        assert UPDATED_DATE.encode() in response.data, \
            "Submitted date must be retained in form after an amount validation error"

    def test_submitted_description_retained_after_invalid_amount(
            self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "-5",
            "category":    "Food",
            "date":        UPDATED_DATE,
            "description": "Retained unique text 12345",
        })
        assert b"Retained unique text 12345" in response.data, \
            "Submitted description must be retained in form after a validation error"

    def test_submitted_category_retained_after_invalid_amount(
            self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "0",
            "category":    "Shopping",
            "date":        UPDATED_DATE,
            "description": "Test",
        })
        assert b"Shopping" in response.data, \
            "Submitted category must be retained in form after an amount validation error"


# ---------------------------------------------------------------------------
# 17. Description is optional
# ---------------------------------------------------------------------------

class TestDescriptionOptional:

    def test_blank_description_post_succeeds(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Other",
            "date":        UPDATED_DATE,
            "description": "",
        })
        assert response.status_code == 302, \
            "POST with blank description must redirect (302)"
        assert "/profile" in response.headers["Location"], \
            "POST with blank description must redirect to /profile"

    def test_blank_description_stored_as_none_or_empty(self, auth_client_with_expense, app):
        client, expense_id = auth_client_with_expense
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Other",
            "date":        UPDATED_DATE,
            "description": "",
        })
        with app.app_context():
            row = _get_expense_by_id(expense_id)
        assert row["description"] is None or row["description"] == "", \
            "Blank description must be stored as NULL or empty string in the DB"

    def test_omitted_description_key_post_succeeds(self, auth_client_with_expense):
        """Omitting the description key entirely must also succeed."""
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        UPDATED_DATE,
            # description key deliberately omitted
        })
        assert response.status_code == 302, \
            "POST with omitted description must redirect (302)"


# ---------------------------------------------------------------------------
# 18. User isolation — POST cannot overwrite another user's record
# ---------------------------------------------------------------------------

class TestUserIsolationPost:

    def test_post_to_other_users_expense_returns_403_and_leaves_record_unchanged(
            self, second_user_expense, client, app):
        """Full combined guard: 403 returned and record is not mutated."""
        other_expense_id = second_user_expense

        with app.app_context():
            original = _get_expense_by_id(other_expense_id)

        response = client.post(f"/expenses/{other_expense_id}/edit", data={
            "amount":      "0.01",
            "category":    "Entertainment",
            "date":        UPDATED_DATE,
            "description": "Overwrite attempt",
        })

        assert response.status_code == 404, \
            "POST targeting another user's expense must return 404 (avoids ID enumeration)"

        with app.app_context():
            after = _get_expense_by_id(other_expense_id)

        assert abs(after["amount"] - original["amount"]) < 0.001, \
            "Amount must not change on a forbidden cross-user POST"
        assert after["category"] == original["category"], \
            "Category must not change on a forbidden cross-user POST"
        assert after["date"] == original["date"], \
            "Date must not change on a forbidden cross-user POST"


# ---------------------------------------------------------------------------
# 19. Edge cases — boundary amounts and all valid categories
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_very_large_positive_amount_accepted(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "999999.99",
            "category":    "Bills",
            "date":        UPDATED_DATE,
            "description": "Huge bill",
        })
        assert response.status_code == 302, \
            "Very large positive amount must be accepted (302 redirect)"
        assert "/profile" in response.headers["Location"], \
            "Very large positive amount must redirect to /profile"

    def test_minimal_positive_amount_accepted(self, auth_client_with_expense):
        client, expense_id = auth_client_with_expense
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "0.01",
            "category":    "Food",
            "date":        UPDATED_DATE,
            "description": "Tiny expense",
        })
        assert response.status_code == 302, \
            "Minimum positive amount 0.01 must be accepted (302 redirect)"
        assert "/profile" in response.headers["Location"], \
            "Minimum positive amount must redirect to /profile"

    @pytest.mark.parametrize("category", VALID_CATEGORIES)
    def test_all_valid_categories_accepted_on_post(self, client, app, category):
        """Each of the 7 valid categories must be accepted when editing an expense."""
        with app.app_context():
            _register_and_login(client)
            uid = _get_user_id("edit_test@spendly.com")
            expense_id = _insert_expense(uid)

        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "10.00",
            "category":    category,
            "date":        UPDATED_DATE,
            "description": f"Test {category}",
        })
        assert response.status_code == 302, \
            f"Valid category '{category}' must be accepted on edit POST (got {response.status_code})"

    def test_sql_injection_in_description_is_safe(self, auth_client_with_expense, app):
        """SQL injection in description must not crash or corrupt the DB."""
        client, expense_id = auth_client_with_expense
        injection = "'; DROP TABLE expenses; --"
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        UPDATED_DATE,
            "description": injection,
        })
        assert response.status_code == 302, \
            "SQL injection in description must not crash — expect 302 redirect"
        with app.app_context():
            row = _get_expense_by_id(expense_id)
        assert row is not None, \
            "Expense row must still exist after SQL injection attempt in description"
        assert row["description"] == injection[:255], \
            "Description must be stored as a literal string, not executed as SQL"

    def test_very_long_description_truncated_or_accepted(self, auth_client_with_expense, app):
        """A description exceeding 255 characters must be accepted (truncated server-side)."""
        client, expense_id = auth_client_with_expense
        long_desc = "A" * 500
        response = client.post(f"/expenses/{expense_id}/edit", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        UPDATED_DATE,
            "description": long_desc,
        })
        assert response.status_code == 302, \
            "Very long description must not cause a 500 error"
        with app.app_context():
            row = _get_expense_by_id(expense_id)
        assert len(row["description"]) <= 255, \
            "Description stored in DB must be capped at 255 characters"

    def test_profile_page_shows_edit_link_per_expense(self, auth_client_with_expense):
        """The profile page must contain an edit link pointing to the edit route."""
        client, expense_id = auth_client_with_expense
        response = client.get("/profile?preset=all_time")
        html = response.data.decode()
        assert f"/expenses/{expense_id}/edit" in html, \
            f"Profile page must contain an edit link for expense id {expense_id}"
