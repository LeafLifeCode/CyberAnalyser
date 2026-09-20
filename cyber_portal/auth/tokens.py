"""
cyber_portal/auth/tokens.py
---------------------------
Cryptographic JWT token generation and verification for 2-step authentication.
Enforces scope checking (ingress_only vs role-scoped tokens).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import jwt

from cyber_portal.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    INGRESS_TOKEN_EXPIRE_MINUTES,
    ROLE_TOKEN_EXPIRE_MINUTES,
)


class AuthenticationError(Exception):
    """Raised when token validation or authentication fails."""
    pass


class TokenScopeError(PermissionError):
    """Raised when an ingress-only token attempts to perform role-scoped operations."""
    pass


def create_ingress_token(user_profile: Dict[str, Any]) -> str:
    """
    Issue a short-lived Step 1 Ingress Token.
    Scope: ['ingress_only'].
    Cannot access citizen PII, account data, or trigger actions.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_profile["username"],
        "badge_id": user_profile.get("badge_id", ""),
        "full_name": user_profile.get("full_name", ""),
        "department": user_profile.get("department", ""),
        "institution_id": user_profile.get("institution_id", None),
        "allowed_roles": user_profile.get("allowed_roles", []),
        "scope": ["ingress_only"],
        "step": 1,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=INGRESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_role_token(
    user_profile: Dict[str, Any],
    role: str,
    institution_id: Optional[str] = None,
) -> str:
    """
    Issue a Step 2 Role-Scoped Token.
    Scope: [role].
    """
    if role not in user_profile.get("allowed_roles", []):
        raise AuthenticationError(f"User {user_profile.get('username')} is not authorized for role {role}")

    now = datetime.now(timezone.utc)
    inst_id = institution_id or user_profile.get("institution_id")

    payload = {
        "sub": user_profile["username"],
        "badge_id": user_profile.get("badge_id", ""),
        "full_name": user_profile.get("full_name", ""),
        "department": user_profile.get("department", ""),
        "role": role,
        "institution_id": inst_id,
        "scope": [role],
        "step": 2,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ROLE_TOKEN_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str, required_scope: Optional[str] = None) -> Dict[str, Any]:
    """
    Decode and strictly validate a JWT token.
    Checks signature, expiration, and optional required scope.
    """
    if not token or not isinstance(token, str):
        raise AuthenticationError("Missing or invalid token string.")

    try:
        claims = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired. Please re-authenticate.")
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(f"Invalid token signature or payload: {exc}")

    scopes = claims.get("scope", [])
    if "ingress_only" in scopes and required_scope and required_scope != "ingress_only":
        raise TokenScopeError(
            f"Ingress-only token cannot access role-scoped resource (requires '{required_scope}'). "
            "Please complete Step 2 Role Step-Up authentication."
        )

    if required_scope and required_scope not in scopes:
        raise TokenScopeError(f"Token lacks required scope '{required_scope}'. Current scopes: {scopes}")

    return claims
