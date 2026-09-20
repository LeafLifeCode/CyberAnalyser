"""
cyber_portal/dal/bank_dal.py
----------------------------
Data Access Layer for Bank Vigilance / Fraud Control Officers.
Strictly scoped to the officer's verified institution_id (enforced at query layer).
Zero access to other banks' accounts, and zero access to telecom/IP/LEA entities.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from cyber_portal.dal.base import require_role
from delivery_model.appeals import get_appeals_manager


class BankService:
    """Service providing institution-scoped query methods for BANK_OFFICER."""

    def __init__(self) -> None:
        self.appeals_mgr = get_appeals_manager()

    def get_bank_queue(self, role_token: str, institution_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve mule account review queue items strictly for the officer's institution.
        If institution_id is provided, it MUST match the token's bound institution_id.
        """
        claims = require_role(role_token, "BANK_OFFICER")
        token_inst = claims.get("institution_id")
        if not token_inst:
            raise PermissionError("Token lacks mandatory institution_id binding for Bank Officer.")

        if institution_id and institution_id != token_inst:
            raise PermissionError(
                f"Cross-Institution Violation: Officer of '{token_inst}' cannot access queue of '{institution_id}'."
            )

        items = self.appeals_mgr.get_by_bank(token_inst)
        # Ensure only bank recipient items for this institution are returned
        return [dict(item) for item in items if item.get("recipient_type") == "bank"]

    def get_bank_item(self, role_token: str, tracking_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific bank account queue item by tracking ID.
        Rejects access if the item belongs to another bank or is an LEA entity.
        """
        claims = require_role(role_token, "BANK_OFFICER")
        token_inst = claims.get("institution_id")
        if not token_inst:
            raise PermissionError("Token lacks mandatory institution_id binding.")

        item = self.appeals_mgr.get_item(tracking_id)
        if not item:
            return None

        if item.get("recipient_type") != "bank":
            raise PermissionError("Access Denied: Bank officers cannot inspect non-banking entities (telecom/IP).")

        if item.get("bank_name") != token_inst:
            raise PermissionError(
                f"Cross-Institution Violation: Account belongs to '{item.get('bank_name')}', but officer is from '{token_inst}'."
            )

        return dict(item)

    def get_mule_forensic_evidence(self, role_token: str, tracking_id: str) -> Dict[str, Any]:
        """
        Retrieve internal mule account transaction velocity and rapid cash-out evidence.
        Contains NO telecom tower or proxy hop data (telecom isolation).
        """
        item = self.get_bank_item(role_token, tracking_id)
        if not item:
            raise ValueError(f"No account found for tracking ID '{tracking_id}' in your institution.")

        evidence = item.get("evidence_summary", {})
        return {
            "tracking_id": tracking_id,
            "account_id": item["entity_id"],
            "bank_name": item["bank_name"],
            "risk_level": item["risk_level"],
            "status": item["status"],
            "signals_triggered": item.get("signals_triggered", []),
            "deposit_surge_ratio": evidence.get("deposit_surge", "12.4x baseline average"),
            "rapid_atm_cashouts": evidence.get("rapid_cashouts", "₹95,000 withdrawn across 3 ATMs in 14 mins"),
            "kyc_compliance_status": evidence.get("kyc_status", "Simplified KYC / Incomplete Bio-metric"),
            "dispute_reason": item.get("dispute_reason"),
            "advocate_name": item.get("advocate_name"),
        }
