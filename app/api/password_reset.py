import hashlib
import logging
import os
import smtplib
import ssl
import threading
import time
from collections import deque
from email.message import EmailMessage
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)


class PasswordResetRateLimiter:
    def __init__(
        self,
        email_limit: int = 5,
        ip_limit: int = 20,
        window_seconds: int = 3600,
        max_keys: int = 10_000,
    ) -> None:
        self.email_limit = email_limit
        self.ip_limit = ip_limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, email: str, client_ip: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        identities = (
            (
                f"email:{hashlib.sha256(email.encode('utf-8')).hexdigest()}",
                self.email_limit,
            ),
            (
                f"ip:{hashlib.sha256(client_ip.encode('utf-8')).hexdigest()}",
                self.ip_limit,
            ),
        )

        with self._lock:
            for key, events in list(self._events.items()):
                while events and events[0] <= cutoff:
                    events.popleft()
                if not events:
                    del self._events[key]

            if any(
                len(self._events.get(key, ())) >= limit
                for key, limit in identities
            ):
                return False

            missing_keys = sum(key not in self._events for key, _ in identities)
            if len(self._events) + missing_keys > self.max_keys:
                return False

            for key, _ in identities:
                self._events.setdefault(key, deque()).append(now)

        return True


password_reset_rate_limiter = PasswordResetRateLimiter()


def validate_password_reset_configuration() -> tuple[str, int, str, str, str]:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError as error:
        raise ValueError("SMTP_PORT must be a valid port number.") from error

    smtp_email = os.getenv("SMTP_EMAIL", "").strip()
    smtp_app_password = os.getenv("SMTP_APP_PASSWORD", "").strip().replace(" ", "")
    frontend_url = os.getenv("PASSWORD_RESET_FRONTEND_URL", "").strip()

    parsed_url = urlsplit(frontend_url)
    if (
        not smtp_host
        or not 1 <= smtp_port <= 65535
        or not smtp_email
        or not smtp_app_password
        or parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.fragment
    ):
        raise ValueError("Password reset email configuration is incomplete.")

    if parsed_url.scheme != "https" and parsed_url.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("Password reset URLs must use HTTPS outside localhost.")

    return smtp_host, smtp_port, smtp_email, smtp_app_password, frontend_url


def build_password_reset_url(frontend_url: str, token: str) -> str:
    parsed = urlsplit(frontend_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "token"
    ]
    query.append(("token", token))
    return urlunsplit(parsed._replace(query=urlencode(query)))


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    smtp_host, smtp_port, smtp_email, smtp_app_password, _ = (
        validate_password_reset_configuration()
    )
    message = EmailMessage()
    message["Subject"] = "Reset your AI Recognition account password"
    message["From"] = smtp_email
    message["To"] = to_email
    message.set_content(
        "We received a request to reset the password for your AI Recognition "
        "account.\n\n"
        f"Use this link to choose a new password:\n{reset_url}\n\n"
        "This link expires in 30 minutes. If you did not request a password "
        "reset, you can ignore this email; your password will not change."
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(smtp_email, smtp_app_password)
        smtp.send_message(message)
