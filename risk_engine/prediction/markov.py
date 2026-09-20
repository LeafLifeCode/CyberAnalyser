"""
risk_engine/prediction/markov.py
----------------------------------
Markov ATM Transition Probability Model.

WHY FIRST-ORDER MARKOV?
  Attacker ATM visit sequences show geographic clustering: fraudsters re-use
  trusted ATM corridors and rarely pick locations uniformly at random.

  A first-order Markov chain (P(next | current)) is chosen because:
  1. AUDITABLE: every transition probability traces to exact event counts —
     fully reproducible for LEA/academic audit.
  2. COLD-START SAFE: population-level aggregate provides sensible fallback
     when entity history is thin (< 2 events).
  3. COMPUTATIONALLY CHEAP: 200-node sparse matrix fits in memory with
     negligible overhead vs. a dense 200×200 float array.
  4. EMPIRICALLY MOTIVATED: financial crime literature (e.g., Baravalle et al.
     2018, RBI cybercrime reports) shows mule cash-out networks cluster
     geographically — fraudsters prefer trusted corridors over random choice.

  Acknowledged limitation: first-order assumption ignores long-range patterns.
  A higher-order or LSTM model would improve accuracy with richer data but adds
  opacity incompatible with the project's auditability requirement.

TRANSITION PROBABILITY FORMULA:
  P(j | i, entity) =
    0.70 * [ (count_entity[i→j] + α) / (Σ_k count_entity[i→k] + α × N) ]
  + 0.30 * [ (count_pop[i→j]    + α) / (Σ_k count_pop[i→k]    + α × N) ]

  where α = 0.1 (Laplace smoothing) and N = 200 (ATM catalogue size).
  The 70/30 blend gives personal history precedence while stabilising sparse
  entity-level matrices with population-level knowledge.

COLD-START (< 2 entity events):
  Falls back to population-level transition matrix.
  If population is also empty (first cycle): uniform over all 200 ATMs.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from generator.data.atm_locations import ATM_LOCATIONS

# ── Constants ──────────────────────────────────────────────────────────────────

# Laplace smoothing: prevents zero probabilities for unobserved transitions.
_ALPHA: float = 0.1

_ATM_CATALOGUE: Dict[str, Dict[str, Any]] = {
    a["atm_id"]: a for a in ATM_LOCATIONS
}
_N_ATMS: int = len(_ATM_CATALOGUE)       # 200

# Prediction time window relative to now (minutes)
_WINDOW_MIN_MIN: int = 10
_WINDOW_MAX_MIN: int = 60


IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def _now_ist() -> datetime:
    return datetime.now(IST)


# ── MarkovATMModel ─────────────────────────────────────────────────────────────

class MarkovATMModel:
    """
    First-order Markov chain over the 200-ATM synthetic network.

    Maintains:
      - Per-entity ATM visit sequences (chronological).
      - Entity-level transition counts: entity → from_atm → to_atm → float.
      - Population-level aggregate transition counts for cold-start fallback.
    """

    def __init__(self) -> None:
        # entity_id → list of {"atm_id": str, "timestamp": str}
        self._sequences: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # entity_id → {from_atm_id → {to_atm_id → count}}
        self._entity_counts: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )

        # Population aggregate: {from_atm_id → {to_atm_id → count}}
        self._population_counts: Dict[str, Dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def ingest_event(self, entity_id: str, atm_id: str, timestamp: str) -> None:
        """
        Record one ATM visit for an entity.
        Updates entity-level and population-level transition counts.
        Only the PREVIOUS → CURRENT transition is recorded (first-order property).
        """
        if atm_id not in _ATM_CATALOGUE:
            return  # Ignore unknown ATM IDs — data quality guard
        seq = self._sequences[entity_id]
        if seq:
            prev_atm = seq[-1]["atm_id"]
            self._entity_counts[entity_id][prev_atm][atm_id] += 1.0
            self._population_counts[prev_atm][atm_id] += 1.0
        seq.append({"atm_id": atm_id, "timestamp": timestamp})

    def ingest_events_from_store(self, events: List[Dict[str, Any]]) -> None:
        """
        Batch-ingest all EventStore records.
        Groups by attacker_id and ingests ATM visits in timestamp order.
        Idempotent: re-ingesting the same events won't double-count because
        sequences are cleared before a full re-ingest (called by reset_and_ingest).
        """
        records: List[Tuple[str, str, str]] = []
        for ev in events:
            entity_id = ev.get("attacker", {}).get("attacker_id")
            atm = ev.get("atm", {})
            atm_id = atm.get("atm_id")
            ts = ev.get("generated_at") or _now_utc().isoformat()
            if entity_id and atm_id:
                records.append((entity_id, atm_id, ts))

        # Chronological ingestion ensures correct transition order
        records.sort(key=lambda r: r[2])
        for entity_id, atm_id, ts in records:
            self.ingest_event(entity_id, atm_id, ts)

    # ── Prediction ─────────────────────────────────────────────────────────────

    def predict(
        self,
        entity_id: str,
        entity_type: str = "account",
        crime_categories: Optional[List[str]] = None,
        top_k: int = 15,
        reference_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Predict the next ATM withdrawal location(s) for a given entity.

        Returns a full INTERNAL prediction record. The caller MUST strip
        internal fields (probability, model_confidence) before passing
        to the dashboard/heatmap layer.
        """
        seq = self._sequences.get(entity_id, [])
        n = len(seq)
        is_cold_start = n < 2

        ref_ts = reference_time or _now_ist()
        window_start = ref_ts + timedelta(minutes=_WINDOW_MIN_MIN)
        window_end   = ref_ts + timedelta(minutes=_WINDOW_MAX_MIN)

        if is_cold_start:
            probs = self._cold_start_probs(seq)
            # Cold-start confidence: 0.15 with 0 events, 0.25 with 1 event.
            # Deliberately low to reflect dashboard's reduced certainty display.
            confidence = 0.15 + (0.10 * n)
        else:
            last_atm = seq[-1]["atm_id"]
            probs = self._blended_probs(entity_id, last_atm)
            # Confidence scales linearly: 0.40 at 2 events → 0.90 at 10+ events.
            # Cap at 0.90 to acknowledge irreducible uncertainty.
            confidence = round(min(0.90, 0.40 + (n - 2) * 0.06), 3)

        # Build top-K list sorted by probability descending.
        # Use a deterministic hash of (entity_id, atm_id) as secondary sort key so that
        # equal-probability ties (e.g. cold-start) diversify across all cities in India
        # instead of always picking the first N sequential catalogue items (which are in Mumbai).
        def _sort_key(item: Tuple[str, float]) -> Tuple[float, float]:
            atm_id, prob = item
            h = int(hashlib.md5(f"{entity_id}:{atm_id}".encode()).hexdigest(), 16) % 100000 / 100000.0
            return (prob, h)

        top_items = sorted(probs.items(), key=_sort_key, reverse=True)[:top_k]

        predicted_locations = []
        for atm_id, prob in top_items:
            atm = _ATM_CATALOGUE[atm_id]
            predicted_locations.append({
                "atm_id":         atm_id,
                "city":           atm["city"],
                "state":          atm["state"],
                "lat":            atm["latitude"],
                "lon":            atm["longitude"],
                "bank":           atm["bank"],
                "atm_type":       atm["atm_type"],
                "location_label": atm.get("location", ""),
                "probability":    round(prob, 4),   # INTERNAL — strip before dashboard
            })

        return {
            "entity_id":           entity_id,
            "entity_type":         entity_type,
            "predicted_locations": predicted_locations,
            "predicted_window": {
                "start": window_start.isoformat(),
                "end":   window_end.isoformat(),
            },
            "model_confidence": confidence,   # INTERNAL — strip before dashboard
            "based_on_n_events": n,
            "is_cold_start":     is_cold_start,
            "crime_categories":  crime_categories or [],
        }

    # ── Internal probability helpers ───────────────────────────────────────────

    def _blended_probs(self, entity_id: str, from_atm: str) -> Dict[str, float]:
        """
        70% entity-level + 30% population-level blended probability vector.
        Both components use Laplace-smoothed normalisation.
        """
        e_raw = self._entity_counts.get(entity_id, {}).get(from_atm, {})
        p_raw = self._population_counts.get(from_atm, {})

        total_e = sum(e_raw.values())
        total_p = sum(p_raw.values())

        blended: Dict[str, float] = {}
        for atm_id in _ATM_CATALOGUE:
            e_val = (
                (e_raw.get(atm_id, 0.0) + _ALPHA) / (total_e + _ALPHA * _N_ATMS)
                if total_e > 0 else 0.0
            )
            p_val = (
                (p_raw.get(atm_id, 0.0) + _ALPHA) / (total_p + _ALPHA * _N_ATMS)
                if total_p > 0 else 1.0 / _N_ATMS
            )
            blended[atm_id] = 0.70 * e_val + 0.30 * p_val

        total = sum(blended.values()) or 1.0
        return {k: v / total for k, v in blended.items()}

    def _cold_start_probs(self, seq: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Cold-start fallback probability vector:
        - 1 prior event: population transitions from that ATM.
        - 0 prior events: uniform distribution over all 200 ATMs.
        """
        if seq:
            last_atm = seq[-1]["atm_id"]
            p_raw = self._population_counts.get(last_atm, {})
            total = sum(p_raw.values())
            if total > 0:
                return {
                    atm_id: (p_raw.get(atm_id, 0.0) + _ALPHA) / (total + _ALPHA * _N_ATMS)
                    for atm_id in _ATM_CATALOGUE
                }
        uniform = 1.0 / _N_ATMS
        return {atm_id: uniform for atm_id in _ATM_CATALOGUE}

    def get_entity_sequence(self, entity_id: str) -> List[Dict[str, Any]]:
        """Return the recorded ATM visit sequence for an entity (for recalibration)."""
        return list(self._sequences.get(entity_id, []))


# ── Module-level singleton ─────────────────────────────────────────────────────
# Persists across Streamlit reruns within the same Python process.

_model_instance: Optional[MarkovATMModel] = None


def get_model() -> MarkovATMModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = MarkovATMModel()
    return _model_instance


def reset_model() -> None:
    global _model_instance
    _model_instance = None
