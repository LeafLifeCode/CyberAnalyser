"""
cyber_portal/dal/base.py
------------------------
Base classes and role validation guards for the Structural Data Access Layer.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from cyber_portal.auth.tokens import verify_token, TokenScopeError, AuthenticationError


def require_role(token: str, expected_role: str) -> Dict[str, Any]:
    """
    Validate that the token has the expected role scope and is not an ingress-only token.
    Returns the verified claims dictionary.
    """
    claims = verify_token(token, required_scope=expected_role)
    if claims.get("role") != expected_role:
        raise TokenScopeError(f"Expected role '{expected_role}', but token has '{claims.get('role')}'.")
    return claims
