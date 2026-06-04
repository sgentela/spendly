from database.db import get_db
from datetime import datetime

MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

CATEGORY_MAP = {
    "Food":          ("food",          "Food & Dining"),
    "Transport":     ("transport",     "Transport"),
    "Bills":         ("bills",         "Bills"),
    "Health":        ("health",        "Health"),
    "Entertainment": ("entertainment", "Entertainment"),
    "Shopping":      ("shopping",      "Shopping"),
    "Other":         ("other",         "Other"),
}


def _fmt_date(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b %Y")


def _date_filter(date_range: tuple[str, str] | None) -> tuple[str, list]:
    if date_range:
        return " AND date >= ? AND date <= ?", list(date_range)
    return "", []


def _fmt_amount(v: float) -> str:
    return f"₹{v:,.2f}"


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    ca = row["created_at"]
    member_since = f"{MONTH_NAMES[int(ca[5:7]) - 1]} {ca[:4]}"
    name = row["name"]
    return {
        "name":         name,
        "initials":     "".join(p[0].upper() for p in name.split()[:2]),
        "email":        row["email"],
        "member_since": member_since,
    }


def get_summary_stats(user_id: int, date_range: tuple[str, str] | None = None) -> dict:
    conn = get_db()
    clause, date_params = _date_filter(date_range)
    params = [user_id] + date_params
    totals = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
        "FROM expenses WHERE user_id = ?" + clause,
        tuple(params),
    ).fetchone()
    top = conn.execute(
        "SELECT category FROM expenses WHERE user_id = ?" + clause +
        " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        tuple(params),
    ).fetchone()
    conn.close()
    return {
        "total_spent":       _fmt_amount(totals["total"]),
        "transaction_count": totals["cnt"],
        "top_category":      top["category"] if top else "—",
    }


def get_recent_transactions(
    user_id: int,
    limit: int | None = None,
    date_range: tuple[str, str] | None = None,
) -> list[dict]:
    conn = get_db()
    clause, date_params = _date_filter(date_range)
    sql    = "SELECT date, description, category, amount FROM expenses WHERE user_id = ?" + clause
    params = [user_id] + date_params
    sql   += " ORDER BY date DESC, id DESC"
    if limit is not None:
        sql    += " LIMIT ?"
        params += [limit]
    rows = conn.execute(sql, tuple(params)).fetchall()
    conn.close()
    result = []
    for row in rows:
        slug, label = CATEGORY_MAP.get(row["category"], (row["category"].lower(), row["category"]))
        result.append({
            "date":        _fmt_date(row["date"]),
            "description": row["description"] or "",
            "category":    slug,
            "label":       label,
            "amount":      _fmt_amount(row["amount"]),
        })
    return result


def get_category_breakdown(user_id: int, date_range: tuple[str, str] | None = None) -> list[dict]:
    conn = get_db()
    clause, date_params = _date_filter(date_range)
    sql    = "SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = ?" + clause
    params = [user_id] + date_params
    sql   += " GROUP BY category ORDER BY total DESC"
    rows = conn.execute(sql, tuple(params)).fetchall()
    conn.close()
    if not rows:
        return []
    grand = sum(r["total"] for r in rows)
    pcts = [int(r["total"] / grand * 100) for r in rows]
    pcts[0] += 100 - sum(pcts)   # largest category absorbs rounding remainder
    result = []
    for row, pct in zip(rows, pcts):
        slug, label = CATEGORY_MAP.get(row["category"], (row["category"].lower(), row["category"]))
        result.append({
            "name":   label,
            "slug":   slug,
            "amount": _fmt_amount(row["total"]),
            "pct":    pct,
        })
    return result
