"""
delivery_model/audit.py
-------------------------
Internal Audit Log for Component 4 — Delivery Model.

Stores all routing decisions, status updates, and appeal submissions.
Maintains in-memory log for Streamlit UI and appends entries to
delivery_audit_log.jsonl on disk for human reviewer auditability.

STRICT SEPARATION:
This log is intended for system administrators, bank risk officers,
and law enforcement auditors. It MUST NOT be shown to civilians.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

_AUDIT_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "delivery_audit_log.jsonl",
)


class DeliveryAuditLog:
    """
    Internal audit log for all Delivery Model routing actions and recourse events.
    """

    def __init__(self) -> None:
        self._entries: List[Dict[str, Any]] = []

    def append(self, entry: Dict[str, Any]) -> None:
        if "timestamp" not in entry:
            entry["timestamp"] = datetime.now(IST).isoformat()
        self._entries.append(entry)

        # Write to disk log (non-fatal if file write fails)
        try:
            with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self._entries)

    def get_recent(self, n: int = 30) -> List[Dict[str, Any]]:
        return self._entries[-n:]

    def clear(self) -> None:
        self._entries.clear()


# ── Singleton Pattern ─────────────────────────────────────────────────────────

_audit_log_instance: Optional[DeliveryAuditLog] = None


def get_delivery_audit_log() -> DeliveryAuditLog:
    global _audit_log_instance
    if _audit_log_instance is None:
        _audit_log_instance = DeliveryAuditLog()
    return _audit_log_instance


def reset_delivery_audit_log() -> None:
    global _audit_log_instance
    _audit_log_instance = None
