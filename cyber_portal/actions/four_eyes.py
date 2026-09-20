"""
cyber_portal/actions/four_eyes.py
---------------------------------
Four-Eyes Principle Enforcement.
Mandates that formal appeals and disputes CANNOT be adjudicated by the officer
who initiated the original enforcement action.
"""

from __future__ import annotations
from typing import Any, Dict, Optional


class FourEyesViolationError(PermissionError):
    """Raised when an officer attempts to self-adjudicate an appeal on their own decision."""
    pass


def validate_four_eyes(
    item_record: Dict[str, Any],
    current_actor_id: str,
    action_type: str,
) -> None:
    """
    Verify that an appealed item is not being resolved or actioned by the original reviewer.

    Args:
        item_record: The review queue item dictionary.
        current_actor_id: Badge ID or username of the reviewer attempting the action.
        action_type: The proposed action (e.g. 'resolve_appeal', 'uphold', 'overturn').

    Raises:
        FourEyesViolationError: If current_actor_id matches the original reviewer.
    """
    status = item_record.get("status")
    original_actor = item_record.get("original_actor_id") or item_record.get("reviewer_id")

    # If the item has been appealed or is in appeal resolution
    if status == "appealed" or action_type in {"resolve_appeal", "uphold_appeal", "overturn_appeal"}:
        if original_actor and current_actor_id.strip().lower() == original_actor.strip().lower():
            raise FourEyesViolationError(
                f"Four-Eyes Principle Violation: Officer '{current_actor_id}' initiated the original action "
                f"on entity '{item_record.get('entity_id')}' and is legally disqualified from adjudicating this appeal. "
                "A secondary senior reviewer must inspect and resolve this dispute."
            )
