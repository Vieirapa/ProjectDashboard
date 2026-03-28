from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime
from http import cookies


def hash_password(password: str, salt_hex: str | None = None) -> str:
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split('$', 1)
        return hmac.compare_digest(hash_password(password, salt_hex), f"{salt_hex}${digest_hex}")
    except Exception:
        return False


def create_session(sessions: dict[str, dict], session_ttl_seconds: int, username: str, role: str) -> str:
    token = secrets.token_hex(24)
    sessions[token] = {
        'username': username,
        'role': role,
        'exp': datetime.utcnow().timestamp() + session_ttl_seconds,
    }
    return token


def parse_cookie(raw: str | None) -> dict:
    if not raw:
        return {}
    jar = cookies.SimpleCookie()
    jar.load(raw)
    return {k: v.value for k, v in jar.items()}


def current_user_from_cookie(sessions: dict[str, dict], session_cookie: str, raw_cookie: str | None) -> dict | None:
    tok = parse_cookie(raw_cookie).get(session_cookie)
    if not tok or tok not in sessions:
        return None
    s = sessions[tok]
    if datetime.utcnow().timestamp() > s['exp']:
        sessions.pop(tok, None)
        return None
    return {'username': s['username'], 'role': s['role'], 'token': tok}
