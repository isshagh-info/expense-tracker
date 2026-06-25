import csv
from collections import defaultdict
from datetime import datetime, timedelta
from io import StringIO

from flask import (
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import Budget, Transaction, User


CATEGORIES = [
    "Salary",
    "Freelance",
    "Food",
    "Transport",
    "Housing",
    "Bills",
    "Shopping",
    "Health",
    "Entertainment",
    "Savings",
    "Other",
]


def parse_amount(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError("Enter a valid amount.")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    return round(amount, 2)


def parse_date(value):
    if not value:
        return datetime.now()
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Enter a valid date.")


def current_month():
    return datetime.now().strftime("%Y-%m")


def month_bounds(month):
    start = datetime.strptime(month, "%Y-%m")
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def get_transaction_or_404(transaction_id):
    return Transaction.query.filter_by(
        id=transaction_id, user_id=current_user.id
    ).first_or_404()


def build_dashboard_context(month, selected_type, category):
    start, end = month_bounds(month)
    query = Transaction.query.filter_by(user_id=current_user.id)
    month_query = query.filter(Transaction.date >= start, Transaction.date < end)

    if selected_type in ("income", "expense"):
        query = query.filter_by(type=selected_type)
        month_query = month_query.filter_by(type=selected_type)
    if category:
        query = query.filter_by(category=category)
        month_query = month_query.filter_by(category=category)

    transactions = query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    month_transactions = month_query.all()
    all_transactions = Transaction.query.filter_by(user_id=current_user.id).all()

    total_income = sum(t.amount for t in all_transactions if t.type == "income")
    total_expense = sum(t.amount for t in all_transactions if t.type == "expense")
    month_income = sum(t.amount for t in month_transactions if t.type == "income")
    month_expense = sum(t.amount for t in month_transactions if t.type == "expense")
    expense_by_category = {}
    for transaction in month_transactions:
        if transaction.type == "expense":
            expense_by_category[transaction.category] = (
                expense_by_category.get(transaction.category, 0) + transaction.amount
            )

    budgets = Budget.query.filter_by(user_id=current_user.id, month=month).all()
    budget_progress = []
    for budget in budgets:
        spent = expense_by_category.get(budget.category, 0)
        budget_progress.append(
            {
                "budget": budget,
                "spent": spent,
                "remaining": budget.amount - spent,
                "percent": min(round((spent / budget.amount) * 100), 100)
                if budget.amount
                else 0,
            }
        )

    recent_categories = sorted({t.category for t in all_transactions} | set(CATEGORIES))

    return {
        "transactions": transactions,
        "balance": total_income - total_expense,
        "total_income": total_income,
        "total_expense": total_expense,
        "month_income": month_income,
        "month_expense": month_expense,
        "month_balance": month_income - month_expense,
        "budget_progress": budget_progress,
        "categories": recent_categories,
        "filters": {"month": month, "type": selected_type, "category": category},
    }


def register_routes(app):
    @app.route("/")
    def home():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not username or not email or not password:
                flash("Please fill in every field.", "error")
                return render_template("register.html"), 400
            if len(password) < 6:
                flash("Password must be at least 6 characters.", "error")
                return render_template("register.html"), 400
            if User.query.filter((User.email == email) | (User.username == username)).first():
                flash("That username or email is already registered.", "error")
                return render_template("register.html"), 409

            user = User(
                username=username,
                email=email,
                password=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.commit()

            flash("Account created. You can log in now.", "success")
            return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()

            if user and check_password_hash(user.password, password):
                login_user(user)
                flash("Welcome back.", "success")
                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "error")
            return render_template("login.html"), 401

        return render_template("login.html")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        month = request.args.get("month") or current_month()
        selected_type = request.args.get("type", "")
        category = request.args.get("category", "")
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            flash("Invalid month filter.", "error")
            return redirect(url_for("dashboard"))

        return render_template(
            "dashboard.html",
            **build_dashboard_context(month, selected_type, category),
        )

    @app.route("/dashboard/daily-summary")
    @login_required
    def daily_summary():
        month = request.args.get("month") or current_month()
        try:
            start_str = request.args.get("start")
            end_str = request.args.get("end")
            start = parse_date(start_str) if start_str else month_bounds(month)[0]
            end = parse_date(end_str) if end_str else month_bounds(month)[1] - timedelta(days=1)
        except ValueError as error:
            return {"error": str(error)}, 400
        if end < start:
            return {"error": "End date must be on or after the start date."}, 400

        end_of_day = end.replace(hour=23, minute=59, second=59)
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= start,
            Transaction.date <= end_of_day,
        ).all()

        totals = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
        day = start
        while day <= end:
            totals[day.strftime("%Y-%m-%d")]
            day += timedelta(days=1)
        for transaction in transactions:
            day_key = transaction.date.strftime("%Y-%m-%d")
            totals[day_key][transaction.type] += transaction.amount

        labels = sorted(totals)
        return {
            "labels": labels,
            "income": [round(totals[day]["income"], 2) for day in labels],
            "expense": [round(totals[day]["expense"], 2) for day in labels],
        }

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/transactions/add", methods=["GET", "POST"])
    @login_required
    def add_transaction():
        if request.method == "POST":
            try:
                amount = parse_amount(request.form.get("amount"))
                date = parse_date(request.form.get("date"))
            except ValueError as error:
                flash(str(error), "error")
                return render_template(
                    "transaction_form.html", transaction=None, categories=CATEGORIES
                ), 400

            transaction = Transaction(
                amount=amount,
                type=request.form.get("type", "expense"),
                category=request.form.get("category", "Other").strip() or "Other",
                date=date,
                description=request.form.get("description", "").strip(),
                user_id=current_user.id,
            )
            if transaction.type not in ("income", "expense"):
                flash("Choose income or expense.", "error")
                return render_template(
                    "transaction_form.html", transaction=None, categories=CATEGORIES
                ), 400

            db.session.add(transaction)
            db.session.commit()
            flash("Transaction added.", "success")
            return redirect(url_for("dashboard"))

        return render_template(
            "transaction_form.html", transaction=None, categories=CATEGORIES
        )

    @app.route("/transactions/<int:transaction_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_transaction(transaction_id):
        transaction = get_transaction_or_404(transaction_id)
        categories = sorted(set(CATEGORIES) | {transaction.category})
        if request.method == "POST":
            try:
                transaction.amount = parse_amount(request.form.get("amount"))
                transaction.date = parse_date(request.form.get("date"))
            except ValueError as error:
                flash(str(error), "error")
                return render_template(
                    "transaction_form.html", transaction=transaction, categories=categories
                ), 400

            transaction.type = request.form.get("type", "expense")
            transaction.category = request.form.get("category", "Other").strip() or "Other"
            transaction.description = request.form.get("description", "").strip()

            if transaction.type not in ("income", "expense"):
                flash("Choose income or expense.", "error")
                return render_template(
                    "transaction_form.html", transaction=transaction, categories=categories
                ), 400

            db.session.commit()
            flash("Transaction updated.", "success")
            return redirect(url_for("dashboard"))

        return render_template(
            "transaction_form.html", transaction=transaction, categories=categories
        )

    @app.post("/transactions/<int:transaction_id>/delete")
    @login_required
    def delete_transaction(transaction_id):
        transaction = get_transaction_or_404(transaction_id)
        db.session.delete(transaction)
        db.session.commit()
        flash("Transaction deleted.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/budgets", methods=["GET", "POST"])
    @login_required
    def budgets():
        month = request.args.get("month") or request.form.get("month") or current_month()
        if request.method == "POST":
            try:
                amount = parse_amount(request.form.get("amount"))
                datetime.strptime(month, "%Y-%m")
            except ValueError as error:
                flash(str(error), "error")
                return redirect(url_for("budgets", month=month))

            category = request.form.get("category", "Other").strip() or "Other"
            budget = Budget.query.filter_by(
                user_id=current_user.id, month=month, category=category
            ).first()
            if budget:
                budget.amount = amount
                flash("Budget updated.", "success")
            else:
                db.session.add(
                    Budget(
                        user_id=current_user.id,
                        month=month,
                        category=category,
                        amount=amount,
                    )
                )
                flash("Budget created.", "success")
            db.session.commit()
            return redirect(url_for("budgets", month=month))

        context = build_dashboard_context(month, "", "")
        context["categories"] = sorted(set(context["categories"]))
        context["filters"] = {"month": month}
        return render_template("budgets.html", **context)

    @app.post("/budgets/<int:budget_id>/delete")
    @login_required
    def delete_budget(budget_id):
        budget = Budget.query.filter_by(id=budget_id, user_id=current_user.id).first_or_404()
        month = budget.month
        db.session.delete(budget)
        db.session.commit()
        flash("Budget deleted.", "success")
        return redirect(url_for("budgets", month=month))

    @app.route("/transactions/export")
    @login_required
    def export_transactions():
        rows = Transaction.query.filter_by(user_id=current_user.id).order_by(
            Transaction.date.desc()
        )
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["date", "type", "category", "description", "amount"])
        for transaction in rows:
            writer.writerow(
                [
                    transaction.date.strftime("%Y-%m-%d"),
                    transaction.type,
                    transaction.category,
                    transaction.description or "",
                    f"{transaction.amount:.2f}",
                ]
            )

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=transactions.csv"},
        )

    @app.route("/add", methods=["GET", "POST"])
    @login_required
    def legacy_add_transaction():
        return add_transaction()
