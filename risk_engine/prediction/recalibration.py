"""
risk_engine/prediction/recalibration.py
-----------------------------------------
Incremental Recalibration Engine + Internal Audit Log.

RECALIBRATION MATH (incremental — no full model retrain per event):

  When an actual withdrawal is logged, we compare it to the model's last
  top-1 prediction and adjust transition counts as follows:

  CASE A — Correct (actual == predicted top-1):
    count(from, actual) += LEARNING_RATE          # reinforce the correct path
    population[from, actual] += LEARNING_RATE * 0.5

  CASE B — In top-3 but not top-1:
    count(from, actual)    += LEARNING_RATE * 0.5  # mild reinforcement
    count(from, top1)      *= DECAY                 # mild penalty on wrong top-1

  CASE C — Complete miss (not in top-5):
    count(from, actual)    += LEARNING_RATE * 0.3   # weak reinforcement
    count(from, top1)      *= STRONG_DECAY           # stronger penalty

  Constants:
    LEARNING_RATE = 0.5    — controls recalibration step size
    DECAY         = 0.90   — mild penalty multiplier
    STRONG_DECAY  = 0.75   — strong penalty multiplier
    MIN_COUNT     = 0.01   — floor to prevent zero probabilities

AUDIT LOG:
  Every recalibration event and drift flag is appended to the AuditLog.
  The AuditLog is STRICTLY INTERNAL — it must never be passed to the
  dashboard/heatmap layer. It is intended for the human reviewer / auditor role.

  Each entry includes before/after count deltas so an auditor can trace
  exactly how predictions changed after each actual event was ingested.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ── Constants ──────────────────────────────────────────────────────────────────

_LEARNING_RATE: float = 0.5
_DECAY:         float = 0.90
_STRONG_DECAY:  float = 0.75
_MIN_COUNT:     float = 0.01

_AUDIT_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "audit_log.jsonl",
)


# ── AuditLog ───────────────────────────────────────────────────────────────────

class AuditLog:
    """
    Internal-only chronological log of all recalibration events and drift flags.

    Stored in-memory (for Streamlit UI) and appended to audit_log.jsonl on disk
    (for the human reviewer / auditor role).

    MUST NOT be forwarded to the dashboard layer.
    Deliberately has no method that strips entries — the full delta record
    must be preserved for auditability.
    """

    def __init__(self) -> None:
        self._entries: List[Dict[str, Any]] = []

    def append(self, entry: Dict[str, Any]) -> None:
        entry["logged_at"] = datetime.now(timezone.utc).isoformat()
        self._entries.append(entry)
        # Non-fatal disk write — failure does not break in-memory log
        try:
            with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self._entries)

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        return self._entries[-n:]

    def clear(self) -> None:
        self._entries.clear()


# ── RecalibrationEngine ────────────────────────────────────────────────────────

class RecalibrationEngine:
    """
    Incrementally recalibrates the MarkovATMModel when actual withdrawal events
    are confirmed. All comparison outcomes are written to the AuditLog.
    """

    def __init__(self, model, audit_log: AuditLog) -> None:
        self._model = model
        self._log   = audit_log
        # entity_id → last PredictionRecord (stored for comparison)
        self._last_predictions: Dict[str, Dict[str, Any]] = {}

    def record_prediction(self, prediction: Dict[str, Any]) -> None:
        """Cache the last prediction for an entity for later comparison."""
        self._last_predictions[prediction["entity_id"]] = prediction

    def log_actual_withdrawal(
        self,
        entity_id: str,
        actual_atm_id: str,
        actual_timestamp: str,
        drift_flag: bool = False,
    ) -> Dict[str, Any]:
        """
        Compare an actual withdrawal to the last prediction and update model.
        Returns an internal recalibration result dict (audit record).
        """
        prediction = self._last_predictions.get(entity_id)
        seq        = self._model.get_entity_sequence(entity_id)
        from_atm   = seq[-1]["atm_id"] if seq else None

        result: Dict[str, Any] = {
            "entity_id":          entity_id,
            "actual_atm":         actual_atm_id,
            "predicted_top1_atm": None,
            "was_correct":        False,
            "was_in_top3":        False,
            "delta_predicted_top1": 0.0,
            "delta_actual":         0.0,
            "drift_flag":         drift_flag,
            "notes":              "",
        }

        if prediction and from_atm:
            locs  = prediction.get("predicted_locations", [])
            top5  = [loc["atm_id"] for loc in locs[:5]]
            top3  = top5[:3]
            top1  = top5[0] if top5 else None
            result["predicted_top1_atm"] = top1

            ec = self._model._entity_counts[entity_id]

            if top1 == actual_atm_id:
                # Case A: Correct — reinforce the path
                delta = _LEARNING_RATE
                ec[from_atm][actual_atm_id] = max(
                    _MIN_COUNT,
                    ec[from_atm].get(actual_atm_id, 0.0) + delta,
                )
                self._model._population_counts[from_atm][actual_atm_id] += delta * 0.5
                result.update({
                    "was_correct": True, "was_in_top3": True,
                    "delta_actual": delta,
                    "notes": "Correct top-1 prediction — reinforced path.",
                })

            elif actual_atm_id in top3:
                # Case B: In top-3 — mild correction
                delta_a = _LEARNING_RATE * 0.5
                old_top1 = ec[from_atm].get(top1, 0.0) if top1 else 0.0
                ec[from_atm][actual_atm_id] = max(
                    _MIN_COUNT,
                    ec[from_atm].get(actual_atm_id, 0.0) + delta_a,
                )
                if top1:
                    new_top1 = max(_MIN_COUNT, old_top1 * _DECAY)
                    ec[from_atm][top1] = new_top1
                    result["delta_predicted_top1"] = round(new_top1 - old_top1, 4)
                result.update({
                    "was_in_top3": True, "delta_actual": delta_a,
                    "notes": "Actual in top-3; mild correction applied.",
                })

            else:
                # Case C: Complete miss — stronger correction
                delta_a = _LEARNING_RATE * 0.3
                old_top1 = ec[from_atm].get(top1, 0.0) if top1 else 0.0
                ec[from_atm][actual_atm_id] = max(
                    _MIN_COUNT,
                    ec[from_atm].get(actual_atm_id, 0.0) + delta_a,
                )
                if top1:
                    new_top1 = max(_MIN_COUNT, old_top1 * _STRONG_DECAY)
                    ec[from_atm][top1] = new_top1
                    result["delta_predicted_top1"] = round(new_top1 - old_top1, 4)
                result.update({
                    "delta_actual": delta_a,
                    "notes": "Complete miss — strong correction applied.",
                })
        else:
            result["notes"] = "No prior prediction cached — ingesting withdrawal as first event."

        # Always ingest the actual event into the sequence
        self._model.ingest_event(entity_id, actual_atm_id, actual_timestamp)
        self._log.append(result)
        return result


# ── Module-level singletons ────────────────────────────────────────────────────

_audit_log_instance: Optional[AuditLog] = None
_recal_engine_instance: Optional[RecalibrationEngine] = None


def get_audit_log() -> AuditLog:
    global _audit_log_instance
    if _audit_log_instance is None:
        _audit_log_instance = AuditLog()
    return _audit_log_instance


def get_recalibration_engine(model=None) -> RecalibrationEngine:
    global _recal_engine_instance
    if _recal_engine_instance is None:
        from risk_engine.prediction.markov import get_model
        _recal_engine_instance = RecalibrationEngine(
            model=model or get_model(),
            audit_log=get_audit_log(),
        )
    return _recal_engine_instance


def reset_engines() -> None:
    global _audit_log_instance, _recal_engine_instance
    _audit_log_instance    = None
    _recal_engine_instance = None
