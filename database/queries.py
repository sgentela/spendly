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


def get_summary_stats(user_id: int) -> dict:
    conn = get_db()
    totals = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
        "FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    top = conn.execute(
        "SELECT category FROM expenses WHERE user_id = ? "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return {
        "total_spent":       _fmt_amount(totals["total"]),
        "transaction_count": totals["cnt"],
        "top_category":      top["category"] if top else "—",
    }


def get_recent_transactions(user_id: int, limit: int | None = None) -> list[dict]:
    conn = get_db()
    if limit is None:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
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


def get_category_breakdown(user_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? GROUP BY category ORDER BY total DESC",
        (user_id,),
    ).fetchall()
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
