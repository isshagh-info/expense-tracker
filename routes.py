from flask import render_template, redirect, url_for, request
from models import *
from app import db, app
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

@app.route("/")
def home():
    return "Hello, Expense"

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        # 🔥 CHECK IF USER EXISTS
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            return "Email already exists!"

        hashed_password = generate_password_hash(password)

        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if not user:
            return "User not found"

        if check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            return "Invalid password"

    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expense = sum(t.amount for t in transactions if t.type == "expense")
    balance = total_income - total_expense

    return render_template("dashboard.html",
                           transactions=transactions,
                           balance=balance)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/add", methods=["GET", "POST"])
@login_required
def add_transaction():
    if request.method == "POST":
        amount = float(request.form["amount"])
        type_ = request.form["type"]
        category = request.form["category"]
        # date = request.form["date"]
        description = request.form["description"]

        transaction = Transaction(
            amount=amount,
            type=type_,
            category=category,
            # date=date,
            description=description,
            user_id=current_user.id
        )

        db.session.add(transaction)
        db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("add_transaction.html")

@app.route("/users")
def users():
    all_users = User.query.all()
    return "<br>".join([f"{u.email} - {u.password}" for u in all_users])
