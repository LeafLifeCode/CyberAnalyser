"""
cyber_portal/audit/verifier.py
------------------------------
Tamper Verification Engine for the Cryptographic Audit Ledger.
Traverses every record from genesis to chain tip, recomputing SHA-256 hashes
and checking prev_hash continuity.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cyber_portal.audit.ledger import (
    canonical_json,
    GENESIS_PREV_HASH,
    get_audit_ledger,
)


def verify_audit_ledger(ledger_path: Optional[str] = None) -> Tuple[bool, Optional[int], str]:
    """
    Traverse the ledger file from genesis to tip.
    Recompute SHA-256 hash at each block and verify backward pointers.

    Returns:
        (is_valid: bool, broken_index: Optional[int], detail_message: str)
    """
    if ledger_path:
        p = Path(ledger_path)
        if not p.exists() or p.stat().st_size == 0:
            return True, None, "Ledger is empty. Genesis integrity intact."
        entries = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    else:
        ledger = get_audit_ledger()
        entries = ledger.read_all_raw()

    if not entries:
        return True, None, "Ledger is empty. Genesis integrity intact."

    expected_prev_hash = GENESIS_PREV_HASH

    for idx, record in enumerate(entries):
        # 1. Verify sequence index
        recorded_index = record.get("index")
        if recorded_index != idx:
            return (
                False,
                idx,
                f"Sequence Anomaly at record #{idx}: Recorded index is {recorded_index}, expected {idx}.",
            )

        # 2. Verify backward hash pointer
        actual_prev_hash = record.get("prev_hash")
        if actual_prev_hash != expected_prev_hash:
            return (
                False,
                idx,
                f"Broken Hash Chain at block #{idx}: prev_hash '{actual_prev_hash}' does not match "
                f"preceding block hash '{expected_prev_hash}'. Possible record deletion or insertion.",
            )

        # 3. Recompute hash
        payload = dict(record)
        stored_hash = payload.pop("entry_hash", None)
        data_str = actual_prev_hash + canonical_json(payload)
        recomputed_hash = hashlib.sha256(data_str.encode("utf-8")).hexdigest()

        if recomputed_hash != stored_hash:
            return (
                False,
                idx,
                f"Tamper Detected at block #{idx}: Stored entry_hash '{stored_hash}' does not match "
                f"cryptographic payload digest '{recomputed_hash}'. Record content has been modified.",
            )

        # Update expectation for next block
        expected_prev_hash = stored_hash

    return (
        True,
        None,
        f"Cryptographic Ledger Verified: All {len(entries)} blocks successfully validated from genesis to tip. "
        "Zero tampering or sequence anomalies detected.",
    )
