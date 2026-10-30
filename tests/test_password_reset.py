import copy
import hashlib
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient

from app.database import run_query as database_run_query
from app.api.password_reset import (
    PasswordResetRateLimiter,
    send_password_reset_email,
)
from app.api.routes import auth as auth_routes
from app.main import app
from app.security import hash_password, verify_password


class FakeConnection:
    def __init__(self, database):
        self.database = database

    def execute(self, statement, parameters=()):
        sql = " ".join(statement.split())
        db = self.database

        if sql.startswith("DELETE FROM public.password_reset_tokens WHERE expires_at"):
            db.tokens = {
                token_hash: token
                for token_hash, token in db.tokens.items()
                if token["expires_at"] > db.now
            }
            return self

        if sql.startswith("SELECT id, email FROM public.app_users WHERE email"):
            user = db.users.get(parameters[0])
            self.row = (
                {"id": user["id"], "email": user["email"]}
                if user
                else None
            )
            return self

        if sql.startswith("SELECT id, email, full_name, password_hash"):
            user = db.users.get(parameters[0])
            self.row = copy.deepcopy(user) if user else None
            return self

        if sql.startswith("DELETE FROM public.password_reset_tokens WHERE user_id"):
            if db.fail_on_delete_user_tokens:
                raise psycopg.DatabaseError("Simulated transactional failure.")
            user_id = str(parameters[0])
            db.tokens = {
                token_hash: token
                for token_hash, token in db.tokens.items()
                if token["user_id"] != user_id
            }
            return self

        if sql.startswith("INSERT INTO public.password_reset_tokens"):
            token_hash, user_id, expires_at = parameters
            db.tokens[token_hash] = {
                "user_id": str(user_id),
                "expires_at": expires_at,
                "created_at": db.now,
            }
            return self

        if sql.startswith("SELECT user_id FROM public.password_reset_tokens"):
            token = db.tokens.get(parameters[0])
            self.row = (
                {"user_id": token["user_id"]}
                if token and token["expires_at"] > db.now
                else None
            )
            return self

        if sql.startswith("UPDATE public.app_users SET password_hash"):
            password_digest, user_id = parameters
            user = next(
                (record for record in db.users.values() if record["id"] == str(user_id)),
                None,
            )
            if user:
                user["password_hash"] = password_digest
            self.row = {"id": user["id"]} if user else None
            return self

        if sql.startswith("DELETE FROM public.password_reset_tokens WHERE token_hash"):
            db.tokens.pop(parameters[0], None)
            return self

        if sql.startswith("INSERT INTO public.app_users"):
            user_id, email, password_digest, full_name = parameters
            if email in db.users:
                raise psycopg.errors.UniqueViolation("Duplicate email.")
            user = {
                "id": str(user_id),
                "email": email,
                "password_hash": password_digest,
                "full_name": full_name,
            }
            db.users[email] = user
            self.row = {
                "id": user["id"],
                "email": email,
                "full_name": full_name,
            }
            return self

        raise AssertionError(f"Unexpected SQL in test: {sql}")

    def fetchone(self):
        return getattr(self, "row", None)


class PasswordResetApiTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.user_id = str(uuid4())
        self.old_password = "old-password-123"
        self.users = {
            "registered@example.com": {
                "id": self.user_id,
                "email": "registered@example.com",
                "full_name": "Test User",
                "password_hash": hash_password(self.old_password),
            }
        }
        self.tokens = {}
        self.fail_database = False
        self.fail_on_delete_user_tokens = False
        self.rate_limiter = auth_routes.password_reset_rate_limiter
        with self.rate_limiter._lock:
            self.rate_limiter._events.clear()

        self.environment = patch.dict(
            os.environ,
            {
                "AUTH_SECRET": "test-auth-secret-that-is-at-least-32-characters",
                "SMTP_HOST": "smtp.gmail.com",
                "SMTP_PORT": "587",
                "SMTP_EMAIL": "sender@example.com",
                "SMTP_APP_PASSWORD": "fake-app-password",
                "PASSWORD_RESET_FRONTEND_URL": "http://localhost:5173/reset-password",
            },
        )
        self.environment.start()
        self.run_query_patch = patch(
            "app.api.routes.auth.run_query",
            side_effect=self.run_query,
        )
        self.run_query_patch.start()
        self.send_email_patch = patch(
            "app.api.routes.auth.send_password_reset_email",
        )
        self.mock_send_email = self.send_email_patch.start()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.addCleanup(self.send_email_patch.stop)
        self.addCleanup(self.run_query_patch.stop)
        self.addCleanup(self.environment.stop)

    def run_query(self, operation):
        if self.fail_database:
            raise psycopg.OperationalError("Simulated database outage.")

        previous_users = copy.deepcopy(self.users)
        previous_tokens = copy.deepcopy(self.tokens)
        connection = FakeConnection(self)
        try:
            return operation(connection)
        except Exception:
            self.users = previous_users
            self.tokens = previous_tokens
            raise

    def issue_token(self, raw_token="test-reset-token-value-that-is-long-enough"):
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        self.tokens[token_hash] = {
            "user_id": self.user_id,
            "expires_at": self.now + timedelta(minutes=30),
            "created_at": self.now,
        }
        return raw_token, token_hash

    def reset_request(self, token, password="new-password-123", confirmation=None):
        return self.client.post(
            "/api/auth/reset-password",
            json={
                "token": token,
                "new_password": password,
                "confirmPassword": confirmation or password,
            },
        )

    def test_forgot_password_registered_email_stores_only_token_hash(self):
        response = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "REGISTERED@example.com"},
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            response.json()["message"],
            auth_routes.PASSWORD_RESET_GENERIC_MESSAGE,
        )
        self.mock_send_email.assert_called_once()
        raw_token = parse_qs(urlsplit(self.mock_send_email.call_args.args[1]).query)["token"][0]
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        self.assertIn(token_hash, self.tokens)
        self.assertNotIn(raw_token, self.tokens)
        token_lifetime = self.tokens[token_hash]["expires_at"] - self.now
        self.assertGreaterEqual(token_lifetime, timedelta(minutes=30))
        self.assertLessEqual(token_lifetime, timedelta(minutes=30, seconds=1))

    def test_unknown_email_returns_same_generic_response_without_sending_email(self):
        registered = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "registered@example.com"},
        )
        self.mock_send_email.reset_mock()
        unknown = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "unknown@example.com"},
        )

        self.assertEqual(unknown.status_code, registered.status_code)
        self.assertEqual(unknown.json(), registered.json())
        self.mock_send_email.assert_not_called()

    def test_email_sender_uses_mocked_gmail_smtp_with_starttls(self):
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp

        with patch("app.api.password_reset.smtplib.SMTP", return_value=smtp) as smtp_factory:
            send_password_reset_email(
                "registered@example.com",
                "http://localhost:5173/reset-password?token=sample",
            )

        smtp_factory.assert_called_once_with("smtp.gmail.com", 587, timeout=15)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("sender@example.com", "fake-app-password")
        smtp.send_message.assert_called_once()
        message = smtp.send_message.call_args.args[0]
        self.assertIn("expires in 30 minutes", message.get_content())
        self.assertIn("http://localhost:5173/reset-password?token=sample", message.get_content())

    def test_invalid_forgot_password_email_is_rejected(self):
        response = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "not-an-email"},
        )

        self.assertEqual(response.status_code, 422)
        self.mock_send_email.assert_not_called()

    def test_successful_password_reset_updates_hash_and_consumes_tokens(self):
        raw_token, token_hash = self.issue_token()
        response = self.reset_request(raw_token)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(token_hash, self.tokens)
        self.assertTrue(
            verify_password(
                "new-password-123",
                self.users["registered@example.com"]["password_hash"],
            )
        )

    def test_invalid_token_is_rejected_generically(self):
        response = self.reset_request("unknown-reset-token-value-is-long-enough")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("unknown-reset-token", response.text)

    def test_expired_token_is_rejected(self):
        raw_token, token_hash = self.issue_token()
        self.tokens[token_hash]["expires_at"] = self.now - timedelta(seconds=1)

        response = self.reset_request(raw_token)

        self.assertEqual(response.status_code, 400)
        self.assertIn(token_hash, self.tokens)

    def test_reset_token_cannot_be_reused(self):
        raw_token, _ = self.issue_token()
        first = self.reset_request(raw_token)
        second = self.reset_request(raw_token)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)

    def test_password_confirmation_mismatch_is_rejected_without_echoing_secrets(self):
        raw_token, _ = self.issue_token()
        response = self.reset_request(
            raw_token,
            password="new-password-123",
            confirmation="different-password-456",
        )

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(raw_token, response.text)
        self.assertNotIn("new-password-123", response.text)
        self.assertNotIn("different-password-456", response.text)

    def test_password_shorter_than_minimum_is_rejected_without_echoing_value(self):
        raw_token, _ = self.issue_token()
        response = self.reset_request(
            raw_token,
            password="x1",
            confirmation="x1",
        )

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(raw_token, response.text)
        self.assertNotIn('"x1"', response.text)

    def test_database_failure_returns_safe_error(self):
        self.fail_database = True
        response = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "registered@example.com"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("registered@example.com", response.text)
        self.assertNotIn("Simulated database outage", response.text)

    def test_failed_password_update_rolls_back_and_keeps_token_usable(self):
        raw_token, token_hash = self.issue_token()
        old_hash = self.users["registered@example.com"]["password_hash"]
        self.fail_on_delete_user_tokens = True

        response = self.reset_request(raw_token)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.users["registered@example.com"]["password_hash"], old_hash)
        self.assertIn(token_hash, self.tokens)

    def test_database_transaction_context_rolls_back_callback_errors(self):
        class FakeTransaction:
            rolled_back = False

            def __enter__(self):
                return self

            def __exit__(self, error_type, error, traceback):
                self.rolled_back = error_type is not None
                return False

        class FakeDatabaseConnection:
            def __init__(self):
                self.transaction_context = FakeTransaction()

            def __enter__(self):
                return self

            def __exit__(self, error_type, error, traceback):
                return False

            def transaction(self):
                return self.transaction_context

            def execute(self, statement):
                return None

        connection = FakeDatabaseConnection()

        def fail_operation(active_connection):
            active_connection.execute("UPDATE public.app_users")
            raise psycopg.DatabaseError("test rollback")

        with (
            patch("app.database.get_database_url", return_value="postgresql://test"),
            patch("app.database.psycopg.connect", return_value=connection),
            self.assertRaises(psycopg.DatabaseError),
        ):
            database_run_query(fail_operation)

        self.assertTrue(connection.transaction_context.rolled_back)

    def test_email_delivery_failure_is_generic_and_removes_token(self):
        self.mock_send_email.side_effect = OSError("Simulated SMTP failure.")

        response = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "registered@example.com"},
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            response.json()["message"],
            auth_routes.PASSWORD_RESET_GENERIC_MESSAGE,
        )
        self.assertEqual(self.tokens, {})
        self.assertNotIn("Simulated SMTP failure", response.text)

    def test_login_accepts_new_password_and_rejects_old_password_after_reset(self):
        raw_token, _ = self.issue_token()
        reset_response = self.reset_request(raw_token)
        self.assertEqual(reset_response.status_code, 200)

        new_login = self.client.post(
            "/api/auth/login",
            json={"email": "registered@example.com", "password": "new-password-123"},
        )
        old_login = self.client.post(
            "/api/auth/login",
            json={"email": "registered@example.com", "password": self.old_password},
        )

        self.assertEqual(new_login.status_code, 200)
        self.assertEqual(old_login.status_code, 401)

    def test_existing_signup_and_google_redirect_still_work(self):
        signup = self.client.post(
            "/api/auth/signup",
            json={
                "fullname": "New User",
                "email": "new@example.com",
                "password": "signup-password-123",
                "confirmPassword": "signup-password-123",
            },
        )
        self.assertEqual(signup.status_code, 201)

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-client-id",
                "GOOGLE_CLIENT_SECRET": "test-client-secret",
                "GOOGLE_REDIRECT_URI": "http://localhost:8001/api/auth/google/callback",
                "GOOGLE_FRONTEND_REDIRECT_URI": "http://localhost:5173/",
            },
        ):
            google = self.client.get("/api/auth/google", follow_redirects=False)

        self.assertEqual(google.status_code, 302)
        self.assertIn("prompt=select_account", google.headers["location"])

    def test_rate_limiter_applies_email_and_ip_quotas(self):
        limiter = PasswordResetRateLimiter(
            email_limit=2,
            ip_limit=3,
            window_seconds=3600,
        )

        self.assertTrue(limiter.allow("a@example.com", "192.0.2.1"))
        self.assertTrue(limiter.allow("a@example.com", "192.0.2.1"))
        self.assertFalse(limiter.allow("a@example.com", "192.0.2.1"))
        self.assertTrue(limiter.allow("b@example.com", "192.0.2.1"))
        self.assertFalse(limiter.allow("c@example.com", "192.0.2.1"))


if __name__ == "__main__":
    unittest.main()
