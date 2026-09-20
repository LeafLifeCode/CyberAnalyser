"""
risk_engine/prediction/drift_detector.py
------------------------------------------
Concept Drift Detector — Trailing-Window Hit-Rate Check.

ALGORITHM:
  Per entity, maintain a circular buffer of the last N=20 prediction outcomes.
  After each actual withdrawal is logged:
    hit_rate = correct_outcomes_in_window / window_size

  If hit_rate < DRIFT_THRESHOLD (0.40):
    → Flag to AuditLog with drift_flag=True
    → Reset the window for that entity (avoids cascading consecutive alerts)

THRESHOLD JUSTIFICATION (0.40):
  - Random baseline over 200 ATMs: P(correct top-1) ≈ 0.5%.
  - Calibrated model with ≥5 events: expected top-1 accuracy 25–60% depending
    on attacker mobility pattern.
  - Below 40%: suggests the attacker has materially shifted their pattern
    (relocated, switched modus operandi, or been redirected by handler) —
    a meaningful concept drift signal warranting human reviewer attention.

IMPORTANT: Drift flags go ONLY to AuditLog, NOT the dashboard UI.
The dashboard shows risk levels based on prediction scores, not hit rates.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Optional

# Window size: 20 predictions per entity before drift check is meaningful.
# Too small → noisy; too large → slow to detect real drift.
_WINDOW_SIZE: int = 20

# Accuracy threshold: below 40% = concept drift flagged.
_DRIFT_THRESHOLD: float = 0.40


class DriftDetector:
    """
    Per-entity trailing-window accuracy tracker.
    Thread-safe for single-process Streamlit usage.
    """

    def __init__(self) -> None:
        # entity_id → circular buffer of bool (True=hit, False=miss)
        self._windows: Dict[str, Deque[bool]] = {}
        # entity_id → cumulative count of drift events detected
        self._drift_counts: Dict[str, int] = {}

    def record_outcome(self, entity_id: str, was_correct: bool) -> bool:
        """
        Record one prediction outcome.
        Returns True if drift was detected (hit_rate < threshold after this event).
        Window is reset after a positive drift detection.
        """
        if entity_id not in self._windows:
            self._windows[entity_id]    = deque(maxlen=_WINDOW_SIZE)
            self._drift_counts[entity_id] = 0

        window = self._windows[entity_id]
        window.append(was_correct)

        # Need a full window before checking
        if len(window) < _WINDOW_SIZE:
            return False

        hit_rate = sum(window) / len(window)
        if hit_rate < _DRIFT_THRESHOLD:
            self._drift_counts[entity_id] += 1
            window.clear()  # Reset to prevent consecutive alert storm
            return True
        return False

    def get_hit_rate(self, entity_id: str) -> Optional[float]:
        """Current hit rate for an entity, or None if < 2 outcomes recorded."""
        window = self._windows.get(entity_id)
        if not window or len(window) < 2:
            return None
        return round(sum(window) / len(window), 3)

    def get_drift_count(self, entity_id: str) -> int:
        """Total number of drift events detected for an entity."""
        return self._drift_counts.get(entity_id, 0)

    def get_all_statuses(self) -> Dict[str, Dict]:
        """Return current status for all tracked entities."""
        result = {}
        for eid, window in self._windows.items():
            if len(window) >= 2:
                rate = sum(window) / len(window)
                result[eid] = {
                    "hit_rate":       round(rate, 3),
                    "window_size":    len(window),
                    "drift_detected": rate < _DRIFT_THRESHOLD,
                    "drift_events":   self._drift_counts.get(eid, 0),
                }
        return result

    def reset_entity(self, entity_id: str) -> None:
        self._windows.pop(entity_id, None)
        self._drift_counts.pop(entity_id, None)


# ── Module-level singleton ─────────────────────────────────────────────────────

_detector_instance: Optional[DriftDetector] = None


def get_drift_detector() -> DriftDetector:
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = DriftDetector()
    return _detector_instance


def reset_drift_detector() -> None:
    global _detector_instance
    _detector_instance = None
