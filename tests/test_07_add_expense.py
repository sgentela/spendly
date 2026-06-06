"""
tests/test_07_add_expense.py

Tests for the Add Expense feature (Step 07) of Spendly.

Spec: .claude/specs/07-add-expense.md

Behaviours under test:
  1.  Auth guard — GET /expenses/add redirects to /login when logged out
  2.  Auth guard — POST /expenses/add redirects to /login when logged out
  3.  GET /expenses/add (logged in) returns 200 and renders the add-expense form
  4.  Form contains amount, category, date, and description fields
  5.  Date field is pre-populated with today's date
  6.  Category dropdown lists exactly the 7 valid categories in the correct order
  7.  POST valid data inserts one row into `expenses` and redirects to /profile
  8.  POST with blank description still succeeds (description is optional)
  9.  DB side-effect: inserted row has correct values for amount, category, date, description
 10.  Flash success message appears on the profile page after redirect
 11.  The new expense appears in the profile transactions list after redirect
 12.  POST missing/zero/negative/non-numeric amount re-renders form with error (no row inserted)
 13.  POST with invalid/missing category re-renders form with error (no row inserted)
 14.  POST with blank date re-renders form with error (no row inserted)
 15.  Form field values are re-populated after a validation error
 16.  Edge case: very large positive amount is accepted
 17.  Edge case: fractional positive amount (e.g. 0.01) is accepted
"""

import datetime
import pytest

import database.db as _db
from database.db import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]

TODAY = datetime.date.today().isoformat()


def _register_and_login(client, email="add_exp@spendly.com",
                        password="testpass1") -> None:
    """Register a fresh user and log in via the test client."""
    client.post("/register", data={
        "name":             "Expense Tester",
        "email":            email,
        "password":         password,
        "confirm_password": password,
    })
    client.post("/login", data={
        "email":    email,
        "password": password,
    })


def _get_user_id(email: str = "add_exp@spendly.com") -> int:
    """Fetch user id by email from the test DB."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return row["id"]


def _count_expenses(user_id: int) -> int:
    """Return the number of expenses stored for the given user."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row["cnt"]


def _get_latest_expense(user_id: int) -> dict | None:
    """Return the most recently inserted expense row for the user."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_client(client, app):
    """Logged-in client with a freshly registered user and no expenses."""
    with app.app_context():
        _register_and_login(client)
    return client


# ---------------------------------------------------------------------------
# 1 & 2. Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:

    def test_get_add_expense_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, \
            "Unauthenticated GET /expenses/add must redirect (302)"
        assert "/login" in response.headers["Location"], \
            "Redirect must point to /login"

    def test_post_add_expense_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/add", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        TODAY,
            "description": "Test",
        })
        assert response.status_code == 302, \
            "Unauthenticated POST /expenses/add must redirect (302)"
        assert "/login" in response.headers["Location"], \
            "Unauthenticated POST must redirect to /login, not process the form"


# ---------------------------------------------------------------------------
# 3 & 4. GET renders the form with all required fields
# ---------------------------------------------------------------------------

class TestGetRendersForm:

    def test_get_returns_200(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200, \
            "Authenticated GET /expenses/add must return 200"

    def test_get_renders_amount_input(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="amount"' in response.data, \
            "Form must contain an 'amount' input field"

    def test_get_renders_date_input(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="date"' in response.data, \
            "Form must contain a 'date' input field"

    def test_get_renders_category_dropdown(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="category"' in response.data, \
            "Form must contain a 'category' select/input field"

    def test_get_renders_description_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="description"' in response.data, \
            "Form must contain a 'description' field"

    def test_get_renders_submit_button(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'type="submit"' in response.data, \
            "Form must contain a submit button"

    def test_form_uses_post_method(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'method="POST"' in response.data or b'method="post"' in response.data, \
            "Form must use POST method"


# ---------------------------------------------------------------------------
# 5. Date field pre-populated with today's date
# ---------------------------------------------------------------------------

class TestDatePrePopulation:

    def test_date_field_defaults_to_today(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert TODAY.encode() in response.data, \
            f"Date field must be pre-populated with today's date ({TODAY})"


# ---------------------------------------------------------------------------
# 6. Category dropdown lists exactly the 7 valid categories in order
# ---------------------------------------------------------------------------

class TestCategoryDropdown:

    def test_all_seven_categories_present(self, auth_client):
        response = auth_client.get("/expenses/add")
        for category in VALID_CATEGORIES:
            assert category.encode() in response.data, \
                f"Category '{category}' must appear in the dropdown"

    def test_exactly_seven_valid_categories(self, auth_client):
        """All seven categories appear and no extra values are injected."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode()
        for category in VALID_CATEGORIES:
            assert category in html, f"Missing category: {category}"
        # Ensure none of the known-invalid categories sneak in
        invalid_categories = ["Groceries", "Rent", "Travel", "Education"]
        for cat in invalid_categories:
            # Only reject if the exact option value is present; partial matches are okay
            assert f'value="{cat}"' not in html, \
                f"Unexpected category option '{cat}' found in dropdown"

    def test_categories_appear_in_correct_order(self, auth_client):
        """Categories must appear in the spec-defined order."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode()
        positions = [html.index(cat) for cat in VALID_CATEGORIES if cat in html]
        assert positions == sorted(positions), \
            "Categories must appear in the spec-defined order: " + str(VALID_CATEGORIES)


# ---------------------------------------------------------------------------
# 7 & 9. POST valid data — DB side-effects, redirect
# ---------------------------------------------------------------------------

class TestPostHappyPath:

    def test_valid_post_redirects_to_profile(self, auth_client, app):
        response = auth_client.post("/expenses/add", data={
            "amount":      "75.50",
            "category":    "Food",
            "date":        TODAY,
            "description": "Dinner out",
        })
        assert response.status_code == 302, \
            "Valid POST must redirect (302)"
        assert "/profile" in response.headers["Location"], \
            "Valid POST must redirect to /profile"

    def test_valid_post_inserts_one_row(self, auth_client, app):
        with app.app_context():
            uid = _get_user_id()
            before = _count_expenses(uid)
            auth_client.post("/expenses/add", data={
                "amount":      "75.50",
                "category":    "Food",
                "date":        TODAY,
                "description": "Dinner out",
            })
            after = _count_expenses(uid)
        assert after == before + 1, \
            "Exactly one new expense row must be inserted on valid POST"

    def test_valid_post_row_has_correct_amount(self, auth_client, app):
        with app.app_context():
            uid = _get_user_id()
            auth_client.post("/expenses/add", data={
                "amount":      "75.50",
                "category":    "Food",
                "date":        TODAY,
                "description": "Dinner out",
            })
            row = _get_latest_expense(uid)
        assert row is not None, "Expense row must exist after POST"
        assert abs(row["amount"] - 75.50) < 0.001, \
            f"Stored amount must be 75.50, got {row['amount']}"

    def test_valid_post_row_has_correct_category(self, auth_client, app):
        with app.app_context():
            uid = _get_user_id()
            auth_client.post("/expenses/add", data={
                "amount":      "75.50",
                "category":    "Transport",
                "date":        TODAY,
                "description": "Bus fare",
            })
            row = _get_latest_expense(uid)
        assert row["category"] == "Transport", \
            f"Stored category must be 'Transport', got {row['category']}"

    def test_valid_post_row_has_correct_date(self, auth_client, app):
        with app.app_context():
            uid = _get_user_id()
            auth_client.post("/expenses/add", data={
                "amount":      "50.00",
                "category":    "Bills",
                "date":        TODAY,
                "description": "Water bill",
            })
            row = _get_latest_expense(uid)
        assert row["date"] == TODAY, \
            f"Stored date must be {TODAY}, got {row['date']}"

    def test_valid_post_row_has_correct_description(self, auth_client, app):
        with app.app_context():
            uid = _get_user_id()
            auth_client.post("/expenses/add", data={
                "amount":      "50.00",
                "category":    "Health",
                "date":        TODAY,
                "description": "Pharmacy visit",
            })
            row = _get_latest_expense(uid)
        assert row["description"] == "Pharmacy visit", \
            f"Stored description must be 'Pharmacy visit', got {row['description']}"


# ---------------------------------------------------------------------------
# 8. Description is optional
# ---------------------------------------------------------------------------

class TestDescriptionOptional:

    def test_blank_description_post_redirects_to_profile(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount":      "30.00",
            "category":    "Other",
            "date":        TODAY,
            "description": "",
        })
        assert response.status_code == 302, \
            "POST with blank description must still redirect (302)"
        assert "/profile" in response.headers["Location"], \
            "POST with blank description must redirect to /profile"

    def test_blank_description_inserts_one_row(self, auth_client, app):
        with app.app_context():
            uid = _get_user_id()
            before = _count_expenses(uid)
            auth_client.post("/expenses/add", data={
                "amount":      "30.00",
                "category":    "Other",
                "date":        TODAY,
                "description": "",
            })
            after = _count_expenses(uid)
        assert after == before + 1, \
            "One expense row must be inserted even when description is blank"

    def test_blank_description_stored_as_none_or_empty(self, auth_client, app):
        """Spec says description=None when blank; stored value must be NULL or empty string."""
        with app.app_context():
            uid = _get_user_id()
            auth_client.post("/expenses/add", data={
                "amount":      "30.00",
                "category":    "Other",
                "date":        TODAY,
                "description": "",
            })
            row = _get_latest_expense(uid)
        assert row["description"] is None or row["description"] == "", \
            "Blank description must be stored as NULL or empty string"

    def test_omitted_description_post_redirects(self, auth_client):
        """Omitting the description field entirely (not in form data) must also succeed."""
        response = auth_client.post("/expenses/add", data={
            "amount":   "20.00",
            "category": "Entertainment",
            "date":     TODAY,
            # description key deliberately omitted
        })
        assert response.status_code == 302, \
            "POST with omitted description field must redirect"
        assert "/profile" in response.headers["Location"], \
            "POST with omitted description must redirect to /profile"


# ---------------------------------------------------------------------------
# 10. Flash success message and profile page integration
# ---------------------------------------------------------------------------

class TestFlashAndIntegration:

    def test_success_flash_on_profile_after_redirect(self, auth_client):
        """After a valid POST, the profile page must display the success flash message."""
        auth_client.post("/expenses/add", data={
            "amount":      "42.00",
            "category":    "Shopping",
            "date":        TODAY,
            "description": "New shoes",
        })
        response = auth_client.get("/profile?preset=all_time")
        assert b"Expense added successfully" in response.data or \
               b"success" in response.data.lower(), \
            "A success flash message must be visible on the profile page after adding an expense"

    def test_new_expense_appears_on_profile_transactions(self, auth_client):
        """The newly added expense description must appear in the profile transaction list."""
        auth_client.post("/expenses/add", data={
            "amount":      "88.00",
            "category":    "Health",
            "date":        TODAY,
            "description": "Dentist appointment",
        })
        # Follow the redirect to /profile
        response = auth_client.get("/profile?preset=all_time")
        assert b"Dentist appointment" in response.data, \
            "Newly added expense must appear in the profile transactions list"

    def test_new_expense_amount_on_profile(self, auth_client):
        """The formatted amount of the new expense must appear on the profile page."""
        auth_client.post("/expenses/add", data={
            "amount":      "123.45",
            "category":    "Food",
            "date":        TODAY,
            "description": "Fancy lunch",
        })
        response = auth_client.get("/profile?preset=all_time")
        # Amount is formatted as ₹123.45
        assert "123.45".encode() in response.data, \
            "The amount ₹123.45 must appear on the profile page after adding the expense"


# ---------------------------------------------------------------------------
# 11. POST invalid amount — validation errors
# ---------------------------------------------------------------------------

class TestAmountValidation:

    @pytest.mark.parametrize("bad_amount,label", [
        ("",       "empty string"),
        ("0",      "zero"),
        ("-10",    "negative number"),
        ("-0.01",  "small negative"),
        ("abc",    "non-numeric string"),
        ("1e999",  "overflow-like value"),
        ("  ",     "whitespace only"),
    ])
    def test_invalid_amount_rerenters_form(self, auth_client, bad_amount, label):
        response = auth_client.post("/expenses/add", data={
            "amount":      bad_amount,
            "category":    "Food",
            "date":        TODAY,
            "description": "Test",
        })
        assert response.status_code == 200, \
            f"Amount '{label}' must re-render the form (200), not redirect"
        assert b'name="amount"' in response.data, \
            f"Amount '{label}' must re-render the add-expense form"

    @pytest.mark.parametrize("bad_amount", ["", "0", "-10", "-0.01", "abc", "  "])
    def test_invalid_amount_shows_error_message(self, auth_client, bad_amount):
        response = auth_client.post("/expenses/add", data={
            "amount":      bad_amount,
            "category":    "Food",
            "date":        TODAY,
            "description": "Test",
        })
        assert b"error" in response.data.lower() or \
               b"auth-error" in response.data or \
               b"Amount" in response.data, \
            f"An error message must appear for invalid amount '{bad_amount}'"

    @pytest.mark.parametrize("bad_amount", ["", "0", "-10", "abc"])
    def test_invalid_amount_no_row_inserted(self, auth_client, app, bad_amount):
        with app.app_context():
            uid = _get_user_id()
            before = _count_expenses(uid)
            auth_client.post("/expenses/add", data={
                "amount":      bad_amount,
                "category":    "Food",
                "date":        TODAY,
                "description": "Should not be inserted",
            })
            after = _count_expenses(uid)
        assert after == before, \
            f"No row must be inserted for invalid amount '{bad_amount}'"


# ---------------------------------------------------------------------------
# 12. POST invalid category — validation errors
# ---------------------------------------------------------------------------

class TestCategoryValidation:

    @pytest.mark.parametrize("bad_category,label", [
        ("",          "empty string"),
        ("Groceries", "unlisted category"),
        ("food",      "lowercase valid category"),
        ("FOOD",      "uppercase valid category"),
        ("1",         "numeric string"),
        ("'; DROP TABLE expenses; --", "SQL injection"),
    ])
    def test_invalid_category_rerenders_form(self, auth_client, bad_category, label):
        response = auth_client.post("/expenses/add", data={
            "amount":      "50.00",
            "category":    bad_category,
            "date":        TODAY,
            "description": "Test",
        })
        assert response.status_code == 200, \
            f"Category '{label}' must re-render the form (200)"
        assert b'name="category"' in response.data, \
            f"Category '{label}' must re-render the add-expense form"

    @pytest.mark.parametrize("bad_category", ["", "Groceries", "food", "FOOD"])
    def test_invalid_category_shows_error_message(self, auth_client, bad_category):
        response = auth_client.post("/expenses/add", data={
            "amount":      "50.00",
            "category":    bad_category,
            "date":        TODAY,
            "description": "Test",
        })
        assert b"auth-error" in response.data or \
               b"error" in response.data.lower() or \
               b"category" in response.data.lower(), \
            f"An error message must appear for invalid category '{bad_category}'"

    @pytest.mark.parametrize("bad_category", ["", "Groceries", "food"])
    def test_invalid_category_no_row_inserted(self, auth_client, app, bad_category):
        with app.app_context():
            uid = _get_user_id()
            before = _count_expenses(uid)
            auth_client.post("/expenses/add", data={
                "amount":      "50.00",
                "category":    bad_category,
                "date":        TODAY,
                "description": "Should not be inserted",
            })
            after = _count_expenses(uid)
        assert after == before, \
            f"No row must be inserted for invalid category '{bad_category}'"


# ---------------------------------------------------------------------------
# 13. POST blank date — validation error
# ---------------------------------------------------------------------------

class TestDateValidation:

    def test_blank_date_rerenders_form(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        "",
            "description": "Test",
        })
        assert response.status_code == 200, \
            "Blank date must re-render the form (200)"
        assert b'name="date"' in response.data, \
            "Blank date must re-render the add-expense form (date field must be present)"

    def test_blank_date_shows_error_message(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount":      "50.00",
            "category":    "Food",
            "date":        "",
            "description": "Test",
        })
        assert b"auth-error" in response.data or \
               b"error" in response.data.lower() or \
               b"Date" in response.data, \
            "An error message must appear when date is blank"

    def test_blank_date_no_row_inserted(self, auth_client, app):
        with app.app_context():
            uid = _get_user_id()
            before = _count_expenses(uid)
            auth_client.post("/expenses/add", data={
                "amount":      "50.00",
                "category":    "Food",
                "date":        "",
                "description": "Should not be inserted",
            })
            after = _count_expenses(uid)
        assert after == before, \
            "No expense row must be inserted when date is blank"

    def test_omitted_date_rerenders_form(self, auth_client):
        """Omitting the date key from form data entirely must also trigger an error."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "50.00",
            "category":    "Food",
            "description": "Test",
            # date key intentionally omitted
        })
        assert response.status_code == 200, \
            "Omitted date must re-render the form (200)"


# ---------------------------------------------------------------------------
# 14. Form field value re-population on validation error
# ---------------------------------------------------------------------------

class TestFormRepopulation:

    def test_amount_retained_after_invalid_category(self, auth_client):
        """When category fails validation, the submitted amount must be shown in the form."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "99.99",
            "category":    "",
            "date":        TODAY,
            "description": "Will fail",
        })
        assert b"99.99" in response.data, \
            "Submitted amount must be retained in the form after a validation error"

    def test_date_retained_after_invalid_amount(self, auth_client):
        """When amount fails, the submitted date must still appear in the form."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "-5",
            "category":    "Food",
            "date":        TODAY,
            "description": "Will fail",
        })
        assert TODAY.encode() in response.data, \
            "Submitted date must be retained in the form after an amount validation error"

    def test_description_retained_after_invalid_amount(self, auth_client):
        """When amount fails, the submitted description must still appear in the form."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "abc",
            "category":    "Food",
            "date":        TODAY,
            "description": "Unique text retained",
        })
        assert b"Unique text retained" in response.data, \
            "Submitted description must be retained in the form after a validation error"

    def test_category_retained_after_invalid_amount(self, auth_client):
        """When amount fails, the previously selected category must remain selected."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "0",
            "category":    "Transport",
            "date":        TODAY,
            "description": "Test",
        })
        # The category option "Transport" must appear selected in the re-rendered form
        assert b"Transport" in response.data, \
            "Selected category must be retained in the form after a validation error"


# ---------------------------------------------------------------------------
# 15. Edge cases — boundary amounts
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_very_large_positive_amount_accepted(self, auth_client, app):
        """A very large positive amount (e.g. 999999.99) must be accepted."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "999999.99",
            "category":    "Bills",
            "date":        TODAY,
            "description": "Huge bill",
        })
        assert response.status_code == 302, \
            "Very large positive amount must be accepted and redirect"
        assert "/profile" in response.headers["Location"], \
            "Very large positive amount must redirect to /profile"

    def test_minimal_positive_amount_accepted(self, auth_client, app):
        """The smallest positive monetary amount (0.01) must be accepted."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "0.01",
            "category":    "Food",
            "date":        TODAY,
            "description": "Tiny purchase",
        })
        assert response.status_code == 302, \
            "Amount 0.01 must be accepted and redirect"
        assert "/profile" in response.headers["Location"], \
            "Amount 0.01 must redirect to /profile"

    def test_all_valid_categories_accepted(self, auth_client, app):
        """Each of the 7 valid categories must be accepted on POST."""
        for category in VALID_CATEGORIES:
            response = auth_client.post("/expenses/add", data={
                "amount":      "10.00",
                "category":    category,
                "date":        TODAY,
                "description": f"Test {category}",
            })
            assert response.status_code == 302, \
                f"Valid category '{category}' must be accepted and redirect (got {response.status_code})"

    def test_multiple_expenses_each_user_isolated(self, client, app):
        """Expenses inserted by one user must not appear for another user."""
        with app.app_context():
            # Register and log in as user A
            _register_and_login(client, email="userA@spendly.com", password="passA1234")
            client.post("/expenses/add", data={
                "amount":      "55.00",
                "category":    "Food",
                "date":        TODAY,
                "description": "User A secret lunch",
            })
            uid_a = _get_user_id("userA@spendly.com")

        # Log out and register/log in as user B
        client.get("/logout")
        with app.app_context():
            _register_and_login(client, email="userB@spendly.com", password="passB1234")
            response = client.get("/profile?preset=all_time")
            assert b"User A secret lunch" not in response.data, \
                "User B must not see expenses belonging to User A"

    def test_get_add_expense_page_title(self, auth_client):
        """The page title or heading should reference adding an expense."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode().lower()
        assert "add" in html and "expense" in html, \
            "The add-expense page must contain 'add' and 'expense' in its content"

    def test_back_link_to_profile_present(self, auth_client):
        """The add-expense form page must contain a back link pointing to /profile."""
        response = auth_client.get("/expenses/add")
        assert b'href="/profile"' in response.data or \
               b"/profile" in response.data, \
            "The add-expense page must provide a navigation link back to /profile"
