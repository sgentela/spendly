from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db, get_user_by_email, create_user

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"  # use env var in production

with app.app_context():
    init_db()
    seed_db()


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

    user_name = session.get("user_name", "Alex Johnson")
    user = {
        "name": user_name,
        "initials": "".join(p[0].upper() for p in user_name.split()[:2]),
        "email": "alex@example.com",
        "member_since": "January 2024",
    }

    stats = {
        "total_spent": "₹12,450.00",
        "transaction_count": 28,
        "top_category": "Food & Dining",
    }

    transactions = [
        {"date": "01 Jun 2025", "description": "Grocery Store",       "category": "food",          "label": "Food & Dining", "amount": "₹1,240.00"},
        {"date": "30 May 2025", "description": "Netflix Subscription", "category": "entertainment", "label": "Entertainment", "amount": "₹649.00"},
        {"date": "28 May 2025", "description": "Electricity Bill",     "category": "utilities",     "label": "Utilities",     "amount": "₹2,100.00"},
        {"date": "26 May 2025", "description": "Uber Ride",            "category": "transport",     "label": "Transport",     "amount": "₹320.00"},
        {"date": "24 May 2025", "description": "Medical Checkup",      "category": "health",        "label": "Health",        "amount": "₹800.00"},
    ]

    categories = [
        {"name": "Food & Dining", "slug": "food",          "amount": "₹4,820.00", "pct": 39},
        {"name": "Utilities",     "slug": "utilities",     "amount": "₹3,200.00", "pct": 26},
        {"name": "Entertainment", "slug": "entertainment", "amount": "₹1,948.00", "pct": 16},
        {"name": "Transport",     "slug": "transport",     "amount": "₹1,282.00", "pct": 10},
        {"name": "Health",        "slug": "health",        "amount": "₹1,200.00", "pct":  9},
    ]

    return render_template("profile.html", user=user, stats=stats,
                           transactions=transactions, categories=categories)


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
    app.run(debug=True, port=5001)
