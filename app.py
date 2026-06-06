import calendar
import os
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db, get_user_by_email, create_user
from database.queries import (
    get_user_by_id, get_summary_stats,
    get_recent_transactions, get_category_breakdown,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "spendly-dev-secret")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Date filter helpers                                                 #
# ------------------------------------------------------------------ #

def _months_ago(reference_date, n):
    m, y = reference_date.month - n, reference_date.year
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, min(reference_date.day, calendar.monthrange(y, m)[1])).isoformat()


def _fmt_iso_display(iso_str):
    return date.fromisoformat(iso_str).strftime("%d %b %Y") if iso_str else ""


def _resolve_date_filter(args):
    today = date.today()
    this_month_start = today.replace(day=1).isoformat()
    this_month_end   = today.replace(day=calendar.monthrange(today.year, today.month)[1]).isoformat()
    today_str        = today.isoformat()
    last_3_start     = _months_ago(today, 3)
    last_6_start     = _months_ago(today, 6)

    from_str     = args.get("from",   "").strip()
    to_str       = args.get("to",     "").strip()
    preset_param = args.get("preset", "").strip()
    date_range    = None
    filter_active = False
    date_error    = False

    if not from_str and not to_str and preset_param != "all_time":
        from_str      = last_6_start
        to_str        = today_str
        date_range    = (from_str, to_str)
        filter_active = True
    elif from_str and to_str:
        try:
            from_date = date.fromisoformat(from_str)
            to_date   = date.fromisoformat(to_str)
            if from_date <= to_date:
                date_range    = (from_str, to_str)
                filter_active = True
            else:
                date_error = True
        except ValueError:
            from_str = to_str = ""

    quick_filter_urls = {
        "all_time":      url_for("profile", preset="all_time"),
        "this_month":    url_for("profile", **{"from": this_month_start, "to": this_month_end}),
        "last_3_months": url_for("profile", **{"from": last_3_start,     "to": today_str}),
        "last_6_months": url_for("profile", **{"from": last_6_start,     "to": today_str}),
    }

    active_preset = "all_time"
    if filter_active:
        preset_ranges = {
            "this_month":    (this_month_start, this_month_end),
            "last_3_months": (last_3_start, today_str),
            "last_6_months": (last_6_start, today_str),
        }
        active_preset = next(
            (k for k, (f, t) in preset_ranges.items() if from_str == f and to_str == t),
            "custom",
        )

    return {
        "date_range":        date_range,
        "filter_active":     filter_active,
        "date_error":        date_error,
        "from_val":          from_str,
        "to_val":            to_str,
        "from_val_display":  _fmt_iso_display(from_str) if active_preset == "custom" else "",
        "to_val_display":    _fmt_iso_display(to_str)   if active_preset == "custom" else "",
        "quick_filter_urls": quick_filter_urls,
        "active_preset":     active_preset,
    }


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("landing"))
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if not name or not email or not password or not confirm_password:
        return render_template("register.html", error="All fields are required.")

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    if password != confirm_password:
        return render_template("register.html", error="Passwords do not match.")

    if get_user_by_email(email):
        return render_template("register.html", error="An account with that email already exists.")

    user_id = create_user(name, email, generate_password_hash(password))
    session.clear()
    session["user_id"] = user_id
    session["user_name"] = name

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("landing"))
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not email or not password:
        return render_template("login.html", error="All fields are required.")

    user = get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]

    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    fctx    = _resolve_date_filter(request.args)

    return render_template(
        "profile.html",
        user=get_user_by_id(user_id),
        stats=get_summary_stats(user_id,            date_range=fctx["date_range"]),
        transactions=get_recent_transactions(user_id, date_range=fctx["date_range"]),
        categories=get_category_breakdown(user_id,  date_range=fctx["date_range"]),
        **fctx,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true", port=5001)
