"""
cyber_portal/actions/handler.py
-------------------------------
Privileged Action Controller:
- Validates Role Tokens and RBAC permissions
- Enforces Four-Eyes Principle on appeals
- Enforces Mandatory Justification Remarks
- Transitions entity state in AppealsManager
- Cryptographically commits action to Audit Ledger
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from cyber_portal.auth.tokens import verify_token, TokenScopeError, AuthenticationError
from cyber_portal.auth.rbac import check_permission
from cyber_portal.actions.four_eyes import validate_four_eyes, FourEyesViolationError
from cyber_portal.audit.ledger import get_audit_ledger
from delivery_model.appeals import get_appeals_manager


class ActionController:
    """Controller for privileged authority actions and dispute resolutions."""

    def __init__(self) -> None:
        self.appeals_mgr = get_appeals_manager()
        self.ledger = get_audit_ledger()

    def execute_action(
        self,
        role_token: str,
        tracking_id: str,
        action_type: str,
        justification_remarks: str,
        appeal_disposition: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a privileged action on a review queue item.

        Args:
            role_token: Verified Step 2 role JWT token.
            tracking_id: Unique TRK-XXXXXX queue tracking identifier.
            action_type: Action to perform (e.g. 'block', 'whitelist', 'debit_freeze', 'resolve_appeal').
            justification_remarks: Mandatory justification text (>= 5 chars).
            appeal_disposition: For appeals, 'uphold_action' or 'overturn_whitelist'.
        """
        # 1. Validate justification remarks
        justification = (justification_remarks or "").strip()
        if len(justification) < 5:
            raise ValueError("Privileged actions require mandatory justification remarks (minimum 5 characters).")

        # 2. Verify token and decode claims
        claims = verify_token(role_token)
        role = claims.get("role")
        actor_id = claims.get("badge_id") or claims.get("sub")
        institution_id = claims.get("institution_id")

        if not role:
            raise TokenScopeError("Action requires a role-scoped token. Ingress-only tokens are prohibited.")

        # 3. Fetch item from queue
        item = self.appeals_mgr.get_item(tracking_id)
        if not item:
            raise ValueError(f"Review queue item '{tracking_id}' not found.")

        # 4. Scope & RBAC verification
        norm_action = action_type.lower()
        if role == "LEA_OFFICER":
            if item.get("recipient_type") != "authority":
                raise PermissionError("LEA Officers can only action Authority Queue items (phones/IPs).")
            # Permission check
            if norm_action in {"block", "whitelist", "section91_notice"}:
                if not check_permission(role, f"action:{norm_action}"):
                    raise PermissionError(f"Role LEA_OFFICER lacks permission for action '{norm_action}'.")
            elif norm_action == "resolve_appeal":
                if not check_permission(role, "action:resolve_appeal"):
                    raise PermissionError("Role LEA_OFFICER lacks permission to resolve appeals.")
            else:
                raise ValueError(f"Unsupported LEA action '{action_type}'.")

        elif role == "BANK_OFFICER":
            if item.get("recipient_type") != "bank":
                raise PermissionError("Bank Officers can only action Bank Queue accounts.")
            if item.get("bank_name") != institution_id:
                raise PermissionError(
                    f"Institution Mismatch: Officer from '{institution_id}' cannot action account belonging to '{item.get('bank_name')}'."
                )
            # Permission check
            if norm_action in {"freeze", "debit_freeze"}:
                if not check_permission(role, "action:freeze:scoped"):
                    raise PermissionError("Bank Officer lacks permission for debit freeze.")
            elif norm_action in {"lien", "lien_mark"}:
                if not check_permission(role, "action:lien:scoped"):
                    raise PermissionError("Bank Officer lacks permission for lien marking.")
            elif norm_action in {"kyc_demand"}:
                if not check_permission(role, "action:kyc_demand:scoped"):
                    raise PermissionError("Bank Officer lacks permission for KYC demand.")
            elif norm_action in {"dismiss"}:
                if not check_permission(role, "action:dismiss:scoped"):
                    raise PermissionError("Bank Officer lacks permission to dismiss flags.")
            elif norm_action == "resolve_appeal":
                if not check_permission(role, "action:resolve_appeal:scoped"):
                    raise PermissionError("Bank Officer lacks permission to resolve appeals.")
            else:
                raise ValueError(f"Unsupported Bank action '{action_type}'.")
        else:
            raise PermissionError(f"Role '{role}' is not authorized to execute actions.")

        # 5. Enforce Four-Eyes Principle if item is in 'appealed' status or action is 'resolve_appeal'
        validate_four_eyes(item, actor_id, norm_action)

        # 6. Determine new status
        if norm_action == "resolve_appeal":
            new_status = "resolved"
        elif norm_action in {"dismiss"}:
            new_status = "dismissed"
        else:
            new_status = "actioned"

        # Record original actor if not already recorded
        if "original_actor_id" not in item:
            item["original_actor_id"] = actor_id

        # Update item in appeals manager
        self.appeals_mgr.update_status(
            tracking_id=tracking_id,
            new_status=new_status,
            reviewer_id=actor_id,
            notes=f"[{norm_action.upper()}] {justification} (Disposition: {appeal_disposition or 'N/A'})",
        )

        # 7. Commit entry to Cryptographic Audit Ledger
        ledger_entry = self.ledger.append_entry(
            actor_id=actor_id,
            actor_role=role,
            action_type=action_type,
            entity_id=item["entity_id"],
            entity_type=item["entity_type"],
            tracking_id=tracking_id,
            justification_text=justification,
            institution_id=institution_id,
            metadata={
                "appeal_disposition": appeal_disposition,
                "previous_status": item.get("status"),
                "new_status": new_status,
                "region": item.get("region"),
            },
        )

        return {
            "success": True,
            "tracking_id": tracking_id,
            "entity_id": item["entity_id"],
            "action_type": action_type,
            "new_status": new_status,
            "actor_id": actor_id,
            "ledger_block_index": ledger_entry["index"],
            "block_hash": ledger_entry["entry_hash"],
        }


_action_controller_instance: Optional[ActionController] = None


def get_action_controller() -> ActionController:
    global _action_controller_instance
    if _action_controller_instance is None:
        _action_controller_instance = ActionController()
    return _action_controller_instance
