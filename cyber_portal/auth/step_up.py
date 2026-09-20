"""
cyber_portal/auth/step_up.py
----------------------------
Step 2 Role Step-Up Authentication:
- Validates Ingress Token
- Checks secondary challenge key / departmental warrant / dual-control PIN
- Emits role-scoped JWT token (e.g. 'LEA_OFFICER', 'BANK_OFFICER', 'DEVOPS')
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from cyber_portal.config import DEPARTMENTAL_USERS, ROLE_CHALLENGE_KEYS
from cyber_portal.auth.tokens import (
    verify_token,
    create_role_token,
    AuthenticationError,
    TokenScopeError,
)


def verify_step2_step_up(
    ingress_token: str,
    target_role: str,
    challenge_key: str,
) -> Dict[str, Any]:
    """
    Authenticate Step 2: Role Step-Up Challenge.
    Requires a valid Ingress Token from Step 1.

    Returns:
        Dict with 'role_token', 'role', 'institution_id', and 'user_profile'.
    """
    # 1. Verify Ingress Token
    claims = verify_token(ingress_token, required_scope="ingress_only")
    username = claims.get("sub")
    allowed_roles = claims.get("allowed_roles", [])

    if target_role not in allowed_roles:
        raise TokenScopeError(f"User '{username}' is not permitted to assume role '{target_role}'.")

    # 2. Verify Role Challenge Key
    challenge_config = ROLE_CHALLENGE_KEYS.get(target_role)
    if not challenge_config:
        raise AuthenticationError(f"No challenge configuration found for role '{target_role}'.")

    expected_key = challenge_config["valid_key"]
    if not challenge_key or challenge_key.strip() != expected_key:
        raise AuthenticationError(f"Invalid {challenge_config['challenge_type']}. Step-up denied.")

    # 3. Retrieve user profile
    user_profile = DEPARTMENTAL_USERS.get(username)
    if not user_profile:
        raise AuthenticationError(f"User profile '{username}' not found.")

    institution_id = user_profile.get("institution_id")
    if target_role == "BANK_OFFICER" and not institution_id:
        raise AuthenticationError("Bank officer missing required institution_id binding.")

    # 4. Issue Role-Scoped Token
    role_token = create_role_token(user_profile, target_role, institution_id=institution_id)

    return {
        "success": True,
        "role_token": role_token,
        "role": target_role,
        "username": username,
        "badge_id": user_profile.get("badge_id"),
        "full_name": user_profile.get("full_name"),
        "department": user_profile.get("department"),
        "institution_id": institution_id,
        "scope": [target_role],
    }
