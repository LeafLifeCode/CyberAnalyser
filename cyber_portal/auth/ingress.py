"""
cyber_portal/auth/ingress.py
----------------------------
Step 1 Ingress Authentication:
- Departmental credentials check (Badge / Username + Password)
- RFC 6238 TOTP verification via `pyotp`
- Rate-limiting tracker with CAPTCHA requirement after 3 failures and lockout after 5
- Emits short-lived Ingress Token (scope: ['ingress_only'])
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional, Tuple
import pyotp

from cyber_portal.config import (
    DEPARTMENTAL_USERS,
    MAX_FAILED_ATTEMPTS_BEFORE_CAPTCHA,
    MAX_FAILED_ATTEMPTS_BEFORE_LOCKOUT,
    LOCKOUT_DURATION_SECONDS,
)
from cyber_portal.auth.tokens import create_ingress_token, AuthenticationError


class RateLimiter:
    """In-memory rate limiter tracking failed attempts and lockouts per user/subject."""

    def __init__(self) -> None:
        self._attempts: Dict[str, int] = {}
        self._lockout_until: Dict[str, float] = {}

    def is_locked(self, identifier: str) -> Tuple[bool, int]:
        now = time.time()
        lock_end = self._lockout_until.get(identifier, 0)
        if now < lock_end:
            remaining = int(lock_end - now)
            return True, remaining
        return False, 0

    def requires_captcha(self, identifier: str) -> bool:
        return self._attempts.get(identifier, 0) >= MAX_FAILED_ATTEMPTS_BEFORE_CAPTCHA

    def record_failure(self, identifier: str) -> int:
        count = self._attempts.get(identifier, 0) + 1
        self._attempts[identifier] = count
        if count >= MAX_FAILED_ATTEMPTS_BEFORE_LOCKOUT:
            self._lockout_until[identifier] = time.time() + LOCKOUT_DURATION_SECONDS
        return count

    def reset(self, identifier: str) -> None:
        self._attempts.pop(identifier, None)
        self._lockout_until.pop(identifier, None)

    def get_failures(self, identifier: str) -> int:
        return self._attempts.get(identifier, 0)


_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter


def verify_step1_ingress(
    username: str,
    password_raw: str,
    totp_code: str,
    captcha_response: Optional[str] = None,
    expected_captcha: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Authenticate Step 1: Departmental Ingress.
    Validates password, checks rate limiting / CAPTCHA, and verifies RFC 6238 TOTP.

    Returns:
        Dict with "ingress_token", "user_profile", and "claims".
    """
    user_key = (username or "").strip().lower()
    limiter = get_rate_limiter()

    # 1. Check lockout
    locked, remaining_sec = limiter.is_locked(user_key)
    if locked:
        raise AuthenticationError(
            f"Account temporarily locked due to excessive failed attempts. Try again in {remaining_sec} seconds."
        )

    # 2. Check CAPTCHA if required
    if limiter.requires_captcha(user_key):
        if not captcha_response or not expected_captcha or captcha_response.strip().upper() != expected_captcha.strip().upper():
            limiter.record_failure(user_key)
            raise AuthenticationError("Security challenge (CAPTCHA) failed or was not provided.")

    # 3. Find user
    user_profile = DEPARTMENTAL_USERS.get(user_key)
    if not user_profile:
        limiter.record_failure(user_key)
        raise AuthenticationError("Invalid departmental credentials.")

    # 4. Verify password hash
    pw_hash = hashlib.md5(password_raw.encode("utf-8")).hexdigest()
    if pw_hash != user_profile["password_hash"]:
        limiter.record_failure(user_key)
        raise AuthenticationError("Invalid departmental credentials.")

    # 5. Verify RFC 6238 TOTP using pyotp
    secret = user_profile.get("totp_secret")
    if not secret:
        limiter.record_failure(user_key)
        raise AuthenticationError("User lacks registered TOTP authenticator.")

    totp = pyotp.TOTP(secret)
    # valid_window=1 allows +-30s clock drift
    if not totp.verify(str(totp_code).strip(), valid_window=1):
        limiter.record_failure(user_key)
        raise AuthenticationError("Invalid or expired 6-digit TOTP code. Synchronize authenticator clock.")

    # 6. Success -> Reset rate limit counter
    limiter.reset(user_key)

    # 7. Generate Step 1 Ingress Token
    ingress_token = create_ingress_token(user_profile)

    return {
        "success": True,
        "ingress_token": ingress_token,
        "username": user_key,
        "badge_id": user_profile["badge_id"],
        "full_name": user_profile["full_name"],
        "department": user_profile["department"],
        "institution_id": user_profile.get("institution_id"),
        "allowed_roles": user_profile["allowed_roles"],
    }
