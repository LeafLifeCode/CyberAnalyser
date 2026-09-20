"""
delivery_model/appeals.py
--------------------------
Appeals & Recourse State Machine Manager.

REQUIREMENT:
Every review queue entry (Authority or Bank route) receives a unique Tracking ID.

STATE MACHINE:
  "pending_review"  ──►  "actioned"   (Manual reviewer approved whitelist/block)
                    ──►  "dismissed"  (Manual reviewer rejected flag as false positive)
                    ──►  "appealed"   (Flagged party submitted dispute) ──► "resolved" (Senior review complete)

DISPUTE ENDPOINT:
  submit_appeal(tracking_id, dispute_reason, advocate_name)
  Transitions status to "appealed" and re-queues item for senior reviewer inspection.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from delivery_model.audit import get_delivery_audit_log

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

VALID_STATUSES = {"pending_review", "actioned", "dismissed", "appealed", "resolved"}


def generate_tracking_id(entity_id: str, recipient_type: str) -> str:
    """Generate a clean, deterministic tracking ID: TRK-XXXXXX."""
    raw = f"{recipient_type}:{entity_id}"
    h = hashlib.md5(raw.encode()).hexdigest()[:6].upper()
    return f"TRK-{h}"


class AppealsManager:
    """
    Manages review queue records, tracking IDs, state transitions, and dispute submissions.
    """

    def __init__(self) -> None:
        # tracking_id → Record Dict
        self._records: Dict[str, Dict[str, Any]] = {}

    def register_item(
        self,
        recipient_type: str,
        entity_id: str,
        entity_type: str,
        risk_level: float,
        region: str,
        signals_triggered: List[Dict[str, Any]],
        recommended_action: str,
        requires_human_review: bool = True,
        bank_name: Optional[str] = None,
        evidence_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create or update a review queue item with a unique tracking ID.
        Preserves existing status ('actioned', 'dismissed', 'appealed', 'resolved') across reruns.
        """
        tracking_id = generate_tracking_id(entity_id, recipient_type)
        now_iso     = datetime.now(IST).isoformat()

        if tracking_id in self._records:
            # Preserve existing lifecycle status, dispute, notes
            existing = self._records[tracking_id]
            existing["risk_level"] = round(risk_level, 3)
            existing["signals_triggered"] = signals_triggered
            existing["recommended_action"] = recommended_action
            existing["evidence_summary"] = evidence_summary or {}
            existing["updated_at"] = now_iso
            return existing

        record = {
            "tracking_id":           tracking_id,
            "recipient_type":        recipient_type,        # "authority" | "bank" | "civilian"
            "entity_id":             entity_id,
            "entity_type":           entity_type,           # "phone" | "ip" | "account"
            "risk_level":            round(risk_level, 3),
            "region":                region,
            "bank_name":             bank_name or "N/A",
            "signals_triggered":     signals_triggered,
            "recommended_action":    recommended_action,
            "requires_human_review": requires_human_review,
            "status":                "pending_review",
            "dispute_reason":        None,
            "advocate_name":         None,
            "created_at":            now_iso,
            "updated_at":            now_iso,
            "evidence_summary":      evidence_summary or {},
        }

        self._records[tracking_id] = record

        # Log creation to audit
        get_delivery_audit_log().append({
            "event":          "REVIEW_ITEM_CREATED",
            "tracking_id":     tracking_id,
            "recipient_type":  recipient_type,
            "entity_id":       entity_id,
            "entity_type":     entity_type,
            "status":          "pending_review",
            "bank_name":       bank_name,
        })

        return record

    def update_status(
        self,
        tracking_id: str,
        new_status: str,
        reviewer_id: str = "OFFICER-001",
        notes: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Transition an item to a new status ("actioned", "dismissed", "resolved").
        """
        if tracking_id not in self._records:
            return None

        if new_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of {VALID_STATUSES}")

        record = self._records[tracking_id]
        old_status = record["status"]
        record["status"]     = new_status
        record["updated_at"] = datetime.now(IST).isoformat()

        get_delivery_audit_log().append({
            "event":       "STATUS_UPDATED",
            "tracking_id":  tracking_id,
            "entity_id":    record["entity_id"],
            "old_status":   old_status,
            "new_status":   new_status,
            "reviewer_id": reviewer_id,
            "notes":       notes,
        })

        return record

    def submit_appeal(
        self,
        tracking_id: str,
        dispute_reason: str,
        advocate_name: str = "Self / Legal Advocate",
    ) -> Optional[Dict[str, Any]]:
        """
        Dispute Endpoint: Submit a recourse appeal for a flagged item.
        Transitions status from current state → "appealed" and re-queues for senior review.
        """
        if tracking_id not in self._records:
            return None

        record = self._records[tracking_id]
        old_status = record["status"]

        record["status"]         = "appealed"
        record["dispute_reason"] = dispute_reason
        record["advocate_name"]  = advocate_name
        record["updated_at"]     = datetime.now(IST).isoformat()

        get_delivery_audit_log().append({
            "event":          "APPEAL_SUBMITTED",
            "tracking_id":     tracking_id,
            "entity_id":       record["entity_id"],
            "recipient_type":  record["recipient_type"],
            "old_status":      old_status,
            "new_status":      "appealed",
            "dispute_reason":  dispute_reason,
            "advocate_name":   advocate_name,
            "action":          "Re-queued for Senior Reviewer inspection.",
        })

        return record

    def get_item(self, tracking_id: str) -> Optional[Dict[str, Any]]:
        return self._records.get(tracking_id)

    def get_by_recipient(self, recipient_type: str) -> List[Dict[str, Any]]:
        return [r for r in self._records.values() if r["recipient_type"] == recipient_type]

    def get_by_bank(self, bank_name: str) -> List[Dict[str, Any]]:
        return [r for r in self._records.values() if r.get("bank_name") == bank_name]

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self._records.values())

    def clear(self) -> None:
        self._records.clear()


# ── Singleton Pattern ─────────────────────────────────────────────────────────

_appeals_manager_instance: Optional[AppealsManager] = None


def get_appeals_manager() -> AppealsManager:
    global _appeals_manager_instance
    if _appeals_manager_instance is None:
        _appeals_manager_instance = AppealsManager()
    return _appeals_manager_instance


def reset_appeals_manager() -> None:
    global _appeals_manager_instance
    _appeals_manager_instance = None
