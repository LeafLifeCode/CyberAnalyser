"""
cyber_portal/auth/rbac.py
-------------------------
Role-Based Access Control (RBAC) permission definitions and checkers.
"""

from __future__ import annotations
from typing import Dict, List, Set

PERMISSIONS: Dict[str, Set[str]] = {
    "LEA_OFFICER": {
        "read:authority_queue",
        "action:block",
        "action:whitelist",
        "action:section91_notice",
        "action:resolve_appeal",
        "read:lea_audit",
    },
    "BANK_OFFICER": {
        "read:bank_queue:scoped",
        "action:freeze:scoped",
        "action:lien:scoped",
        "action:kyc_demand:scoped",
        "action:dismiss:scoped",
        "action:resolve_appeal:scoped",
        "read:bank_audit:scoped",
    },
    "DEVOPS": {
        "read:infra_metrics",
        "read:model_latency",
        "read:drift_logs",
        "read:devops_audit",
        "action:verify_ledger",
    },
}


def get_role_permissions(role: str) -> Set[str]:
    return PERMISSIONS.get(role, set())


def check_permission(role: str, required_permission: str) -> bool:
    role_perms = get_role_permissions(role)
    return required_permission in role_perms
