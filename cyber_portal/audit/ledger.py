"""
cyber_portal/audit/ledger.py
----------------------------
Append-only Cryptographic Audit Ledger using SHA-256 Hash Chaining.
Each entry cryptographically binds the previous block's hash, preventing retroactive alteration.
Querying enforces role-segregated visibility.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from cyber_portal.config import LEDGER_FILE_PATH
from cyber_portal.dal.base import require_role

IST = timezone(timedelta(hours=5, minutes=30), name="IST")
GENESIS_PREV_HASH = "0" * 64


def canonical_json(data: Dict[str, Any]) -> str:
    """Serialize dictionary to deterministic, sorted canonical JSON string."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class CryptographicAuditLedger:
    """
    Manages append-only SHA-256 hash-chained records on disk.
    """

    def __init__(self, file_path: Optional[str] = None) -> None:
        self.file_path = Path(file_path or LEDGER_FILE_PATH)
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.touch()

    def get_last_entry(self) -> Optional[Dict[str, Any]]:
        """Read the last record in the ledger to get current chain tip."""
        if not self.file_path.exists() or self.file_path.stat().st_size == 0:
            return None

        last_line = None
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line

        if last_line:
            try:
                return json.loads(last_line)
            except Exception:
                return None
        return None

    def append_entry(
        self,
        actor_id: str,
        actor_role: str,
        action_type: str,
        entity_id: str,
        entity_type: str,
        tracking_id: str,
        justification_text: str,
        institution_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create and append a new block to the hash chain.
        """
        last_entry = self.get_last_entry()
        if last_entry is None:
            new_index = 0
            prev_hash = GENESIS_PREV_HASH
        else:
            new_index = last_entry["index"] + 1
            prev_hash = last_entry["entry_hash"]

        now_iso = datetime.now(IST).isoformat()
        payload = {
            "index": new_index,
            "timestamp": now_iso,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "institution_id": institution_id,
            "action_type": action_type.upper(),
            "tracking_id": tracking_id,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "justification_text": justification_text,
            "metadata": metadata or {},
            "prev_hash": prev_hash,
        }

        # Compute SHA-256 hash of (prev_hash + canonical_json(payload))
        data_str = prev_hash + canonical_json(payload)
        entry_hash = hashlib.sha256(data_str.encode("utf-8")).hexdigest()
        payload["entry_hash"] = entry_hash

        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

        return payload

    def read_all_raw(self) -> List[Dict[str, Any]]:
        """Read all ledger blocks sequentially."""
        if not self.file_path.exists():
            return []
        entries = []
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
        return entries

    def get_scoped_audit_log(self, role_token: str) -> List[Dict[str, Any]]:
        """
        Query ledger records filtered strictly by role:
        - LEA_OFFICER: Authority actions, phone/IP actions, section 91 notices.
        - BANK_OFFICER: Strictly records matching officer's institution_id.
        - DEVOPS: Sanitized logs (timestamps, action types, block hashes; citizen PII masked).
        """
        # Determine caller role
        claims = require_role(role_token, role_token_expected_role(role_token))
        role = claims.get("role")
        user_inst = claims.get("institution_id")

        all_entries = self.read_all_raw()
        filtered = []

        for entry in all_entries:
            if role == "LEA_OFFICER":
                # LEA can see authority, police, and cross-bank actions
                if entry.get("actor_role") == "LEA_OFFICER" or entry.get("entity_type") in {"phone", "ip"}:
                    filtered.append(entry)
            elif role == "BANK_OFFICER":
                # Bank officer strictly sees their own institution's entries
                if entry.get("institution_id") == user_inst:
                    filtered.append(entry)
            elif role == "DEVOPS":
                # DevOps sees sanitized integrity logs with NO citizen entity identifiers
                sanitized = dict(entry)
                sanitized["entity_id"] = "PROTECTED_CITIZEN_PII"
                sanitized["justification_text"] = "[PRIVACY REDACTED - AUDIT INTEGRITY ONLY]"
                filtered.append(sanitized)

        return filtered


def role_token_expected_role(token: str) -> str:
    """Helper to detect claimed role in token without scope check, for routing."""
    import jwt
    from cyber_portal.config import JWT_SECRET_KEY, JWT_ALGORITHM
    try:
        claims = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return claims.get("role", "")
    except Exception:
        return ""


_audit_ledger_instance: Optional[CryptographicAuditLedger] = None


def get_audit_ledger() -> CryptographicAuditLedger:
    global _audit_ledger_instance
    if _audit_ledger_instance is None:
        _audit_ledger_instance = CryptographicAuditLedger()
    return _audit_ledger_instance
