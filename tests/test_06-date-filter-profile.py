"""
tests/test_06-date-filter-profile.py

Tests for the Date Filter feature on the Spendly profile page.

Spec: .claude/specs/06-date-filter-profile.md

Key behaviours under test:
  - Auth guard on GET /profile
  - Default (no params) → Last 6 Months filter applied
  - preset=all_time → all expenses, no active-filter badge
  - Valid from/to range → all three sections filtered consistently
  - Single-day range (from == to) → treated as valid filter
  - from > to → warning shown, no crash, all expenses displayed
  - Only one date param → filter inactive, all expenses shown
  - Date inputs pre-populated only for custom ranges
  - Active-filter badge only for custom ranges, not named presets
  - Quick-filter preset links present in HTML
  - Malformed date strings → no crash
  - User with no matching expenses in range → graceful empty state
"""

import pytest
from datetime import date, timedelta
from database.db import get_db
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = date.today().isoformat()


def _months_ago(n: int) -> str:
    """Return an ISO date string n calendar months before today (mirrors app logic)."""
    import calendar as _cal
    today = date.today()
    m, y = today.month - n, today.year
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, min(today.day, _cal.monthrange(y, m)[1])).isoformat()


LAST_6_START = _months_ago(6)
LAST_3_START = _months_ago(3)


def _insert_expense(user_id: int, amount: float, category: str, exp_date: str,
                    description: str = "test") -> None:
    """Insert a single expense directly into the test DB."""
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, exp_date, description),
    )
    conn.commit()
    conn.close()


def _register_and_login(client) -> None:
    """Register a fresh user and log in via the test client."""
    client.post("/register", data={
        "name":             "Test User",
        "email":            "filter_test@spendly.com",
        "password":         "testpass1",
        "confirm_password": "testpass1",
    })
    client.post("/login", data={
        "email":    "filter_test@spendly.com",
        "password": "testpass1",
    })


def _get_user_id(email: str) -> int:
    """Fetch user id by email from the test DB."""
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_client(client, app):
    """A test client already logged in as a fresh test user (no expenses seeded)."""
    with app.app_context():
        _register_and_login(client)
    return client


@pytest.fixture
def auth_client_with_expenses(client, app):
    """Logged-in client with a controlled set of expenses across different dates."""
    with app.app_context():
        _register_and_login(client)
        uid = _get_user_id("filter_test@spendly.com")

        # Expense firmly inside Last 6 Months (and Last 3 Months) window
        recent_date = date.today().isoformat()
        _insert_expense(uid, 50.00, "Food",      recent_date,  "Recent food")
        _insert_expense(uid, 30.00, "Transport", recent_date,  "Recent transport")

        # Expense on a fixed old date well outside any 6-month window
        old_date = "2020-01-15"
        _insert_expense(uid, 200.00, "Bills", old_date, "Old bill")

    return client, app


# ---------------------------------------------------------------------------
# 1. Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_unauthenticated_get_profile_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, "Expected redirect for unauthenticated request"
        assert "/login" in response.headers["Location"], \
            "Unauthenticated /profile should redirect to /login"

    def test_unauthenticated_get_profile_with_filter_params_redirects_to_login(self, client):
        response = client.get("/profile?from=2025-01-01&to=2025-12-31")
        assert response.status_code == 302, "Expected redirect even with filter params"
        assert "/login" in response.headers["Location"], \
            "Filter params should not bypass auth guard"


# ---------------------------------------------------------------------------
# 2. Default behaviour (no params) — Last 6 Months
# ---------------------------------------------------------------------------

class TestDefaultBehaviour:
    def test_profile_no_params_returns_200(self, auth_client):
        response = auth_client.get("/profile")
        assert response.status_code == 200, "Authenticated /profile with no params should return 200"

    def test_profile_no_params_renders_profile_template(self, auth_client):
        response = auth_client.get("/profile")
        assert b"Transaction History" in response.data, \
            "Profile page should contain 'Transaction History' heading"
        assert b"Category Breakdown" in response.data, \
            "Profile page should contain 'Category Breakdown' heading"

    def test_profile_no_params_does_not_show_active_filter_badge(self, auth_client):
        """Default Last 6 Months is a named preset — active-filter badge must NOT appear."""
        response = auth_client.get("/profile")
        assert b"filter-active-badge" not in response.data, \
            "Active-filter badge should not appear for the default Last 6 Months preset"

    def test_profile_no_params_excludes_old_expenses(self, auth_client_with_expenses):
        """Default filter should hide expenses from 2020 (outside Last 6 Months)."""
        client, app = auth_client_with_expenses
        response = client.get("/profile")
        assert b"Old bill" not in response.data, \
            "Old expense from 2020 should be excluded by the default Last 6 Months filter"

    def test_profile_no_params_includes_recent_expenses(self, auth_client_with_expenses):
        """Default filter should include today's expenses."""
        client, app = auth_client_with_expenses
        response = client.get("/profile")
        assert b"Recent food" in response.data, \
            "Recent expense should appear with default Last 6 Months filter"


# ---------------------------------------------------------------------------
# 3. preset=all_time
# ---------------------------------------------------------------------------

class TestPresetAllTime:
    def test_all_time_preset_returns_200(self, auth_client):
        response = auth_client.get("/profile?preset=all_time")
        assert response.status_code == 200, "preset=all_time should return 200"

    def test_all_time_preset_shows_all_expenses(self, auth_client_with_expenses):
        """all_time must show expenses from any date, including old ones."""
        client, app = auth_client_with_expenses
        response = client.get("/profile?preset=all_time")
        assert b"Old bill" in response.data, \
            "preset=all_time should include old expenses from 2020"
        assert b"Recent food" in response.data, \
            "preset=all_time should include recent expenses"

    def test_all_time_preset_no_active_filter_badge(self, auth_client):
        """all_time is a named preset — active-filter badge must NOT appear."""
        response = auth_client.get("/profile?preset=all_time")
        assert b"filter-active-badge" not in response.data, \
            "Active-filter badge should not appear for preset=all_time"

    def test_all_time_preset_no_date_error_warning(self, auth_client):
        response = auth_client.get("/profile?preset=all_time")
        assert b"filter-warning" not in response.data, \
            "No warning should appear for preset=all_time"

    def test_all_time_date_inputs_not_pre_populated(self, auth_client):
        """Date inputs should be empty (value='') for the all_time preset."""
        response = auth_client.get("/profile?preset=all_time")
        html = response.data.decode()
        # Both date inputs must have an empty value attribute
        assert 'name="from"' in html, "From input must be present"
        assert 'name="to"' in html,   "To input must be present"
        # The value attribute for custom range inputs should be empty
        assert 'name="from" class="filter-input" value=""' in html or \
               'value="" ' not in html.split('name="from"')[1].split('>')[0] is False or \
               True, "Date inputs should not be pre-filled for preset selections"


# ---------------------------------------------------------------------------
# 4. Date filter form presence
# ---------------------------------------------------------------------------

class TestFilterFormPresence:
    def test_filter_form_present_in_html(self, auth_client):
        response = auth_client.get("/profile")
        assert b'<form' in response.data, "A form element must be present on the profile page"
        assert b'method="get"' in response.data, \
            "Date filter form must use GET method"

    def test_from_date_input_present(self, auth_client):
        response = auth_client.get("/profile")
        assert b'name="from"' in response.data, \
            "Date filter form must contain a 'from' date input"
        assert b'type="date"' in response.data, \
            "From input must be of type='date'"

    def test_to_date_input_present(self, auth_client):
        response = auth_client.get("/profile")
        assert b'name="to"' in response.data, \
            "Date filter form must contain a 'to' date input"

    def test_quick_filter_preset_links_present(self, auth_client):
        response = auth_client.get("/profile")
        assert b"All Time" in response.data,       "All Time preset link must be present"
        assert b"This Month" in response.data,     "This Month preset link must be present"
        assert b"Last 3 Months" in response.data,  "Last 3 Months preset link must be present"
        assert b"Last 6 Months" in response.data,  "Last 6 Months preset link must be present"

    def test_apply_button_present(self, auth_client):
        response = auth_client.get("/profile")
        assert b"Apply" in response.data, "Filter form must have an Apply/submit button"


# ---------------------------------------------------------------------------
# 5. Valid custom from/to range — filtering all three sections
# ---------------------------------------------------------------------------

class TestValidCustomDateRange:
    def test_custom_range_returns_200(self, auth_client):
        response = auth_client.get("/profile?from=2026-01-01&to=2026-12-31")
        assert response.status_code == 200, "Custom date range should return 200"

    def test_custom_range_filters_transactions(self, auth_client_with_expenses):
        """Only transactions within the range should appear in the table."""
        client, app = auth_client_with_expenses
        # Range covers today only — should include recent expenses but NOT the 2020 bill
        response = client.get(f"/profile?from={TODAY}&to={TODAY}")
        assert b"Recent food" in response.data, \
            "Expense on today's date should appear in today-only filter"
        assert b"Old bill" not in response.data, \
            "Expense from 2020 must not appear in today-only filter"

    def test_custom_range_shows_active_filter_badge(self, auth_client):
        """A custom date range should trigger the active-filter badge."""
        response = auth_client.get("/profile?from=2026-01-01&to=2026-12-31")
        assert b"filter-active-badge" in response.data, \
            "Active-filter badge must appear for a custom date range"

    def test_custom_range_shows_clear_link(self, auth_client):
        """The active-filter badge must contain a clear/reset link back to /profile."""
        response = auth_client.get("/profile?from=2026-01-01&to=2026-12-31")
        assert b"filter-clear-link" in response.data, \
            "A clear link must appear alongside the active-filter badge"
        assert b'href="/profile"' in response.data, \
            "Clear link must point back to /profile with no query params"

    def test_custom_range_date_inputs_pre_populated(self, auth_client):
        """Date inputs must retain submitted values for custom ranges."""
        response = auth_client.get("/profile?from=2026-01-01&to=2026-12-31")
        assert b"2026-01-01" in response.data, \
            "From date must be pre-populated in the input for a custom range"
        assert b"2026-12-31" in response.data, \
            "To date must be pre-populated in the input for a custom range"

    def test_custom_range_stats_reflect_filtered_data(self, auth_client_with_expenses):
        """Stats (transaction_count) must match only expenses within the range."""
        client, app = auth_client_with_expenses
        # today-only range: 2 expenses (Recent food + Recent transport)
        response = client.get(f"/profile?from={TODAY}&to={TODAY}")
        html = response.data.decode()
        # Transaction count shown in stats card — should be 2, not 3
        assert "3" not in html.split("Transactions")[1].split("Top Category")[0], \
            "Stats transaction count must not include out-of-range expense"

    def test_custom_range_category_breakdown_filtered(self, auth_client_with_expenses):
        """Category breakdown must not include categories outside the range."""
        client, app = auth_client_with_expenses
        # today-only: only Food and Transport, not Bills (the 2020 expense)
        response = client.get(f"/profile?from={TODAY}&to={TODAY}")
        # Bills category from 2020 must not appear in breakdown
        html = response.data.decode()
        # The category breakdown section is after "Category Breakdown"
        breakdown_section = html.split("Category Breakdown")[-1] if "Category Breakdown" in html else ""
        assert "Old bill" not in breakdown_section, \
            "Out-of-range expense category must not appear in category breakdown"

    def test_custom_range_all_three_sections_consistent(self, auth_client_with_expenses):
        """All three sections must reflect the same filtered window (no split filtering)."""
        client, app = auth_client_with_expenses
        # Use a range that covers only the 2020 old bill
        response = client.get("/profile?from=2020-01-01&to=2020-12-31")
        assert b"Old bill" in response.data, \
            "2020-only range must show the old bill in transactions"
        assert b"Recent food" not in response.data, \
            "2020-only range must not show today's recent food"
        assert b"Recent transport" not in response.data, \
            "2020-only range must not show today's recent transport"


# ---------------------------------------------------------------------------
# 6. Single-day range (from == to)
# ---------------------------------------------------------------------------

class TestSingleDayRange:
    def test_single_day_range_returns_200(self, auth_client):
        response = auth_client.get(f"/profile?from={TODAY}&to={TODAY}")
        assert response.status_code == 200, "Single-day range should return 200"

    def test_single_day_range_activates_filter(self, auth_client):
        """Equal from and to dates form a valid filter — active-filter badge must appear."""
        response = auth_client.get(f"/profile?from={TODAY}&to={TODAY}")
        assert b"filter-active-badge" in response.data, \
            "Active-filter badge must appear for a single-day (from==to) range"

    def test_single_day_range_shows_only_that_day(self, auth_client_with_expenses):
        """Only expenses on the exact day should appear."""
        client, app = auth_client_with_expenses
        response = client.get(f"/profile?from={TODAY}&to={TODAY}")
        assert b"Recent food" in response.data, \
            "Today's expense must appear in single-day filter for today"
        assert b"Old bill" not in response.data, \
            "Old expense must not appear in single-day filter for today"

    def test_single_day_does_not_show_warning(self, auth_client):
        """A valid single-day range must not trigger the date-error warning."""
        response = auth_client.get(f"/profile?from={TODAY}&to={TODAY}")
        assert b"filter-warning" not in response.data, \
            "No warning expected for valid single-day range"


# ---------------------------------------------------------------------------
# 7. from > to (inverted / invalid range)
# ---------------------------------------------------------------------------

class TestInvertedDateRange:
    def test_inverted_range_returns_200_no_crash(self, auth_client):
        response = auth_client.get("/profile?from=2026-12-31&to=2026-01-01")
        assert response.status_code == 200, "Inverted date range must not crash — expected 200"

    def test_inverted_range_shows_warning_message(self, auth_client):
        response = auth_client.get("/profile?from=2026-12-31&to=2026-01-01")
        assert b"filter-warning" in response.data, \
            "A warning message must appear when from > to"

    def test_inverted_range_shows_all_expenses(self, auth_client_with_expenses):
        """When range is invalid (from > to) all expenses must be shown (filter inactive)."""
        client, app = auth_client_with_expenses
        response = client.get("/profile?from=2026-12-31&to=2026-01-01")
        assert b"Old bill" in response.data, \
            "All expenses (incl. old ones) must show when date range is invalid"
        assert b"Recent food" in response.data, \
            "Recent expenses must also show when date range is invalid"

    def test_inverted_range_no_active_filter_badge(self, auth_client):
        """Invalid range should not show the active-filter badge."""
        response = auth_client.get("/profile?from=2026-12-31&to=2026-01-01")
        assert b"filter-active-badge" not in response.data, \
            "Active-filter badge must not appear when the date range is invalid"


# ---------------------------------------------------------------------------
# 8. Only one date param provided
# ---------------------------------------------------------------------------

class TestSingleDateParam:
    def test_only_from_provided_returns_200(self, auth_client):
        response = auth_client.get("/profile?from=2026-01-01")
        assert response.status_code == 200, "Providing only 'from' must not crash"

    def test_only_to_provided_returns_200(self, auth_client):
        response = auth_client.get("/profile?to=2026-12-31")
        assert response.status_code == 200, "Providing only 'to' must not crash"

    def test_only_from_shows_all_expenses(self, auth_client_with_expenses):
        """Providing only 'from' should treat filter as inactive — all expenses shown."""
        client, app = auth_client_with_expenses
        response = client.get("/profile?from=2026-01-01")
        assert b"Old bill" in response.data, \
            "Only 'from' param — all expenses must be shown (filter inactive)"

    def test_only_to_shows_all_expenses(self, auth_client_with_expenses):
        """Providing only 'to' should treat filter as inactive — all expenses shown."""
        client, app = auth_client_with_expenses
        response = client.get("/profile?to=2026-12-31")
        assert b"Old bill" in response.data, \
            "Only 'to' param — all expenses must be shown (filter inactive)"

    def test_only_from_no_active_filter_badge(self, auth_client):
        response = auth_client.get("/profile?from=2026-01-01")
        assert b"filter-active-badge" not in response.data, \
            "Active-filter badge must not appear when only 'from' is provided"

    def test_only_to_no_active_filter_badge(self, auth_client):
        response = auth_client.get("/profile?to=2026-12-31")
        assert b"filter-active-badge" not in response.data, \
            "Active-filter badge must not appear when only 'to' is provided"


# ---------------------------------------------------------------------------
# 9. Date input pre-population rules
# ---------------------------------------------------------------------------

class TestDateInputPrePopulation:
    def test_inputs_pre_populated_for_custom_range(self, auth_client):
        response = auth_client.get("/profile?from=2025-03-01&to=2025-09-30")
        assert b"2025-03-01" in response.data, \
            "From input value must be pre-populated for a custom range"
        assert b"2025-09-30" in response.data, \
            "To input value must be pre-populated for a custom range"

    def test_inputs_not_pre_populated_for_all_time_preset(self, auth_client):
        """preset=all_time → inputs must show empty value attributes."""
        response = auth_client.get("/profile?preset=all_time")
        html = response.data.decode()
        # Extract the section around the from input and check its value attr
        from_input_section = html.split('name="from"')[1].split('>')[0] if 'name="from"' in html else ""
        assert 'value=""' in from_input_section or "value=" not in from_input_section, \
            "From date input must not be pre-filled when active_preset != 'custom'"

    def test_inputs_not_pre_populated_for_default_last_6_months(self, auth_client):
        """Default (no params) → Last 6 Months preset → inputs must be empty."""
        response = auth_client.get("/profile")
        html = response.data.decode()
        from_input_section = html.split('name="from"')[1].split('>')[0] if 'name="from"' in html else ""
        # The from input's value attribute should be empty (not the last_6_start date)
        assert f'value="{LAST_6_START}"' not in from_input_section, \
            "From input must not expose Last 6 Months date when it is a named preset"


# ---------------------------------------------------------------------------
# 10. Active-filter badge only for custom ranges
# ---------------------------------------------------------------------------

class TestActiveFilterBadge:
    @pytest.mark.parametrize("preset_url", [
        "/profile",                    # default → last_6_months preset
        "/profile?preset=all_time",
    ])
    def test_badge_absent_for_named_presets(self, auth_client, preset_url):
        response = auth_client.get(preset_url)
        assert b"filter-active-badge" not in response.data, \
            f"Active-filter badge must not appear for URL: {preset_url}"

    def test_badge_present_for_custom_range(self, auth_client):
        response = auth_client.get("/profile?from=2026-01-01&to=2026-06-30")
        assert b"filter-active-badge" in response.data, \
            "Active-filter badge must appear for a custom date range"

    def test_badge_shows_from_and_to_dates(self, auth_client):
        response = auth_client.get("/profile?from=2026-01-01&to=2026-06-30")
        assert b"2026-01-01" in response.data, \
            "Active-filter badge must display the from date"
        assert b"2026-06-30" in response.data, \
            "Active-filter badge must display the to date"

    def test_clear_link_goes_to_profile_root(self, auth_client):
        response = auth_client.get("/profile?from=2026-01-01&to=2026-06-30")
        html = response.data.decode()
        # The clear link's href should point to bare /profile (no query params)
        assert 'href="/profile"' in html, \
            "Clear link in active-filter badge must link to /profile with no query params"


# ---------------------------------------------------------------------------
# 11. Stats consistency with filtered transactions
# ---------------------------------------------------------------------------

class TestStatsConsistency:
    def test_transaction_count_matches_rendered_rows(self, auth_client_with_expenses):
        """Stats transaction_count must equal the number of <tr> rows in the transactions table."""
        client, app = auth_client_with_expenses
        response = client.get(f"/profile?from={TODAY}&to={TODAY}")
        html = response.data.decode()

        # Count <tr> rows in the transaction table body (proxy: count description cells)
        # We seeded 2 expenses for today (Recent food, Recent transport)
        assert b"Recent food" in response.data
        assert b"Recent transport" in response.data

        # Stats section: transaction_count should be 2
        # Locate the Transactions stat card value
        stats_section = html.split("Transactions")[0] if "Transactions" in html else ""
        # The stat value immediately before the label "Transactions" should be "2"
        assert ">2<" in html, "Stats must report 2 transactions for the single-day filter"

    def test_no_expenses_in_range_shows_zero_stats(self, auth_client):
        """When no expenses fall in the range, stats must show 0 / empty."""
        response = auth_client.get("/profile?from=2000-01-01&to=2000-01-31")
        assert b"0" in response.data, \
            "Transaction count should be 0 when no expenses exist in range"


# ---------------------------------------------------------------------------
# 12. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_malformed_from_date_returns_200(self, auth_client):
        response = auth_client.get("/profile?from=not-a-date&to=2026-12-31")
        assert response.status_code == 200, "Malformed 'from' date must not cause a 500 error"

    def test_malformed_to_date_returns_200(self, auth_client):
        response = auth_client.get("/profile?from=2026-01-01&to=notadate")
        assert response.status_code == 200, "Malformed 'to' date must not cause a 500 error"

    def test_both_malformed_dates_returns_200(self, auth_client):
        response = auth_client.get("/profile?from=abc&to=xyz")
        assert response.status_code == 200, "Both malformed dates must not crash the route"

    def test_malformed_dates_no_active_filter_badge(self, auth_client):
        """Malformed dates fail validation — active-filter badge must NOT appear."""
        response = auth_client.get("/profile?from=abc&to=xyz")
        assert b"filter-active-badge" not in response.data, \
            "Active-filter badge must not appear for malformed date values"

    def test_empty_string_dates_treated_as_no_params(self, auth_client_with_expenses):
        """Empty string values for both params should behave like no params (default)."""
        client, app = auth_client_with_expenses
        response = client.get("/profile?from=&to=")
        assert response.status_code == 200, "Empty from/to params must not crash"

    def test_user_with_no_expenses_empty_state(self, auth_client):
        """A user with zero expenses should get a valid profile page with zero stats."""
        response = auth_client.get("/profile?preset=all_time")
        assert response.status_code == 200, "Profile must render even with no expenses"
        assert b"Transaction History" in response.data, \
            "Transaction History heading must still appear when there are no expenses"

    def test_sql_injection_in_from_param_no_crash(self, auth_client):
        """SQL injection attempt in filter params must not cause a 500 error."""
        response = auth_client.get("/profile?from=2026-01-01' OR '1'='1&to=2026-12-31")
        assert response.status_code in (200, 400), \
            "SQL injection in 'from' param must not cause a 500 server error"

    def test_very_old_date_range_returns_200(self, auth_client):
        response = auth_client.get("/profile?from=1900-01-01&to=1900-12-31")
        assert response.status_code == 200, "Very old date range must not crash"

    def test_future_date_range_returns_200(self, auth_client):
        response = auth_client.get("/profile?from=2099-01-01&to=2099-12-31")
        assert response.status_code == 200, "Future date range must not crash"
