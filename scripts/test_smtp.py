#!/usr/bin/env python3
import os
import smtplib
import sys
from email.message import EmailMessage


def need(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        print(f"Missing env var: {name}")
        sys.exit(2)
    return v


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: test_smtp.py <recipient@email>")
        return 1

    recipient = sys.argv[1].strip()
    host = need("PDASH_SMTP_HOST")
    port = int(os.getenv("PDASH_SMTP_PORT", "587"))
    user = os.getenv("PDASH_SMTP_USER", "").strip()
    password = os.getenv("PDASH_SMTP_PASS", "").strip()
    sender = need("PDASH_SMTP_FROM")
    use_tls = os.getenv("PDASH_SMTP_TLS", "true").strip().lower() not in {"0", "false", "no"}

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "ProjectDashboard SMTP test"
    msg.set_content(
        "Hello!\n\n"
        "This is a test message from ProjectDashboard SMTP setup.\n"
        "If you received this email, SMTP is configured correctly.\n"
    )

    print(f"Connecting to {host}:{port} (TLS={use_tls})...")
    with smtplib.SMTP(host, port, timeout=20) as server:
        if use_tls:
            server.starttls()
        if user:
            print(f"Authenticating as {user}...")
            server.login(user, password)
        print(f"Sending test email to {recipient}...")
        server.send_message(msg)

    print("SMTP test email sent successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
