import unittest

from app import create_app
from extensions import db
from models import Budget, Transaction, User


class ExpenseTrackerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "SECRET_KEY": "test-secret",
            }
        )
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def register(self, username="alex", email="alex@example.com", password="secret1"):
        return self.client.post(
            "/register",
            data={"username": username, "email": email, "password": password},
            follow_redirects=True,
        )

    def login(self, email="alex@example.com", password="secret1"):
        return self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    def register_and_login(self):
        self.register()
        return self.login()

    def test_register_login_logout_flow(self):
        response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Account created", response.data)
        self.assertEqual(User.query.count(), 1)
        self.assertNotEqual(User.query.first().password, "secret1")

        response = self.login()
        self.assertIn(b"Dashboard", response.data)
        self.assertIn(b"Welcome back", response.data)

        response = self.client.get("/logout", follow_redirects=True)
        self.assertIn(b"You have been logged out", response.data)
        self.assertIn(b"Welcome back", response.data)

    def test_auth_validation_rejects_duplicate_and_bad_login(self):
        self.register()

        duplicate = self.register()
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn(b"already registered", duplicate.data)

        bad_login = self.client.post(
            "/login",
            data={"email": "alex@example.com", "password": "wrong"},
            follow_redirects=True,
        )
        self.assertEqual(bad_login.status_code, 401)
        self.assertIn(b"Invalid email or password", bad_login.data)

    def test_transaction_create_edit_delete_and_dashboard_totals(self):
        self.register_and_login()

        response = self.client.post(
            "/transactions/add",
            data={
                "amount": "1200",
                "type": "income",
                "category": "Salary",
                "date": "2026-06-01",
                "description": "June pay",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Transaction added", response.data)

        response = self.client.post(
            "/transactions/add",
            data={
                "amount": "45.25",
                "type": "expense",
                "category": "Food",
                "date": "2026-06-02",
                "description": "Groceries",
            },
            follow_redirects=True,
        )
        self.assertEqual(Transaction.query.count(), 2)
        self.assertIn(b"$1154.75", response.data)

        expense = Transaction.query.filter_by(type="expense").first()
        response = self.client.post(
            f"/transactions/{expense.id}/edit",
            data={
                "amount": "50",
                "type": "expense",
                "category": "Food",
                "date": "2026-06-03",
                "description": "Market",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Transaction updated", response.data)
        self.assertEqual(db.session.get(Transaction, expense.id).amount, 50)

        response = self.client.post(
            f"/transactions/{expense.id}/delete", follow_redirects=True
        )
        self.assertIn(b"Transaction deleted", response.data)
        self.assertEqual(Transaction.query.count(), 1)

    def test_transaction_validation_and_user_ownership(self):
        self.register_and_login()
        response = self.client.post(
            "/transactions/add",
            data={"amount": "-1", "type": "expense", "category": "Food"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"greater than zero", response.data)

        self.client.post(
            "/transactions/add",
            data={"amount": "10", "type": "expense", "category": "Food"},
            follow_redirects=True,
        )
        transaction_id = Transaction.query.first().id
        self.client.get("/logout")

        self.register("sam", "sam@example.com", "secret2")
        self.login("sam@example.com", "secret2")
        response = self.client.get(f"/transactions/{transaction_id}/edit")
        self.assertEqual(response.status_code, 404)

    def test_budget_create_update_delete_and_export(self):
        self.register_and_login()
        self.client.post(
            "/transactions/add",
            data={
                "amount": "25",
                "type": "expense",
                "category": "Food",
                "date": "2026-06-02",
                "description": "Lunch",
            },
            follow_redirects=True,
        )

        response = self.client.post(
            "/budgets",
            data={"month": "2026-06", "category": "Food", "amount": "100"},
            follow_redirects=True,
        )
        self.assertIn(b"Budget created", response.data)
        self.assertEqual(Budget.query.count(), 1)

        response = self.client.post(
            "/budgets",
            data={"month": "2026-06", "category": "Food", "amount": "80"},
            follow_redirects=True,
        )
        self.assertIn(b"Budget updated", response.data)
        self.assertEqual(Budget.query.first().amount, 80)
        self.assertIn(b"$25.00", response.data)

        export = self.client.get("/transactions/export")
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.mimetype, "text/csv")
        self.assertIn(b"date,type,category,description,amount", export.data)
        self.assertIn(b"2026-06-02,expense,Food,Lunch,25.00", export.data)

        budget_id = Budget.query.first().id
        response = self.client.post(f"/budgets/{budget_id}/delete", follow_redirects=True)
        self.assertIn(b"Budget deleted", response.data)
        self.assertEqual(Budget.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
