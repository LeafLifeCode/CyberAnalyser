"""
risk_engine/prediction/heatmap.py
-----------------------------------
GIS-style Risk Heatmap Data Assembler — Dashboard-Facing Layer.

INTERNAL / EXTERNAL DATA SEPARATION (enforced by this module):
  This module is the strict boundary between internal prediction math and
  the dashboard UI. It ingests full internal PredictionRecord dicts and
  outputs HeatmapRecord dicts STRIPPED of all internal fields.

  Fields explicitly FORBIDDEN in dashboard output:
    probability, model_confidence, transition_probs,
    delta_predicted_top1, delta_actual, weight_delta,
    entity_counts, variance_combined_score, variance_confidence

  The "why_flagged" field uses a human-readable template — no numeric weights.
  "risk_score" is normalised from rank (position in prediction list), NOT from
  the raw Markov probability. This prevents reverse-engineering of model internals.

RISK SCORE DERIVATION (rank-based, not probability-based):
  rank_score(atm, entity) = 1 / (rank + 1)
    rank 1 → 1.00  (top prediction for this entity)
    rank 2 → 0.50
    rank 3 → 0.33
    rank 4 → 0.25
    rank 5 → 0.20

  aggregate_score(atm) = Σ rank_score across all entities / max_aggregate_score
  This gives a 0–1 normalised score for each ATM location.

COLOR MAP (for pydeck ScatterplotLayer):
  CRITICAL ≥ 0.75 → [220, 38, 38, 210]    Red
  HIGH     ≥ 0.55 → [234, 88, 12, 210]    Orange
  MEDIUM   ≥ 0.35 → [234, 179, 8, 210]    Yellow
  LOW      ≥ 0.00 → [34, 197, 94, 210]    Green

HOVER TOOLTIP: "{bank}, {city}"   (pydeck tooltip field)
CLICK DETAIL:  full console panel rendered by app.py from the HeatmapRecord fields.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from generator.data.atm_locations import ATM_LOCATIONS

# ── Internal field guard ───────────────────────────────────────────────────────
# These fields MUST NOT appear in any dashboard-facing output.
INTERNAL_FIELDS = frozenset({
    "probability",
    "model_confidence",
    "transition_probs",
    "delta_predicted_top1",
    "delta_actual",
    "weight_delta",
    "entity_counts",
    "variance_combined_score",
    "variance_confidence",
})

# ── Risk level thresholds ──────────────────────────────────────────────────────
_RISK_THRESHOLDS = [
    (0.75, "CRITICAL"),
    (0.55, "HIGH"),
    (0.35, "MEDIUM"),
    (0.00, "LOW"),
]

# ── pydeck RGBA colours ────────────────────────────────────────────────────────
RISK_COLORS: Dict[str, List[int]] = {
    "CRITICAL": [220,  38,  38, 210],   # Red
    "HIGH":     [234,  88,  12, 210],   # Orange
    "MEDIUM":   [234, 179,   8, 210],   # Yellow
    "LOW":      [ 34, 197,  94, 210],   # Green
}

_ATM_CATALOGUE: Dict[str, Dict] = {a["atm_id"]: a for a in ATM_LOCATIONS}
_LEVEL_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _risk_level(score: float) -> str:
    for threshold, level in _RISK_THRESHOLDS:
        if score >= threshold:
            return level
    return "LOW"


def _fmt_window(start: str, end: str) -> str:
    try:
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30), name="IST")
        s = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(IST)
        e = datetime.fromisoformat(end.replace("Z", "+00:00")).astimezone(IST)
        return f"{s.strftime('%Y-%m-%d %H:%M')} – {e.strftime('%H:%M')} IST"
    except Exception:
        return f"{start[:16]} – {end[11:16]}" if start and end else "Unknown window"


def _why_flagged(entity_count: int, region_count: int, crime_categories: List[str]) -> str:
    """
    Human-readable 'why flagged' summary.
    Contains NO probabilities, weights, or model parameter values.
    """
    cats = ", ".join(sorted(set(crime_categories)))[:80] if crime_categories else "multiple fraud types"
    entity_str = "1 flagged entity" if entity_count == 1 else f"{entity_count} flagged entities"
    region_str = f", {region_count} prior incident(s) in region" if region_count else ""
    return (
        f"Elevated activity pattern — {entity_str} linked to this ATM area"
        f"{region_str}. Fraud type(s): {cats}."
    )


# ── HeatmapAssembler ───────────────────────────────────────────────────────────

class HeatmapAssembler:
    """
    Converts internal PredictionRecords → dashboard-safe HeatmapRecords.
    Enforces strict internal/external data separation.
    """

    def assemble(
        self,
        predictions: List[Dict[str, Any]],
        filter_params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Args:
            predictions:   List of internal PredictionRecord dicts.
            filter_params: Optional dict with keys:
                state_filter (str), crime_category_filter (str),
                min_risk_level ("LOW"|"MEDIUM"|"HIGH"|"CRITICAL"),
                time_range_hours (int, unused — window already set in prediction).

        Returns:
            List of HeatmapRecord dicts safe for dashboard display.
            Sorted by risk_score descending.
        """
        fp             = filter_params or {}
        state_filter   = fp.get("state_filter") or None
        cat_filter     = fp.get("crime_category_filter") or None
        min_level      = fp.get("min_risk_level", "LOW")
        min_level_int  = _LEVEL_ORDER.get(min_level, 0)

        # Per-ATM aggregation bucket
        agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "rank_score_sum":   0.0,
            "entity_ids":       [],
            "crime_categories": [],
            "windows_start":    [],
            "windows_end":      [],
            "is_cold_start_any": False,
            "loc_meta":         None,
        })

        for pred in predictions:
            entity_id   = pred["entity_id"]
            cats        = pred.get("crime_categories", [])
            window      = pred.get("predicted_window", {})
            is_cold     = pred.get("is_cold_start", True)
            locs        = pred.get("predicted_locations", [])

            # Crime category filter
            if cat_filter and cat_filter not in cats:
                continue

            for rank, loc in enumerate(locs[:15]):
                atm_id = loc["atm_id"]
                state  = loc.get("state", "")

                # State filter
                if state_filter and state != state_filter:
                    continue

                # Rank-based score (not probability — internal/external separation)
                rank_score = 1.0 / (rank + 1)

                bucket = agg[atm_id]
                bucket["rank_score_sum"] += rank_score
                if entity_id not in bucket["entity_ids"]:
                    bucket["entity_ids"].append(entity_id)
                bucket["crime_categories"].extend(cats)
                if window.get("start"):
                    bucket["windows_start"].append(window["start"])
                if window.get("end"):
                    bucket["windows_end"].append(window["end"])
                bucket["is_cold_start_any"] = bucket["is_cold_start_any"] or is_cold
                if bucket["loc_meta"] is None:
                    bucket["loc_meta"] = loc

        max_score = max((b["rank_score_sum"] for b in agg.values()), default=1.0) or 1.0

        records: List[Dict[str, Any]] = []
        for atm_id, atm in _ATM_CATALOGUE.items():
            state = atm.get("state", "")

            # State filter
            if state_filter and state != state_filter:
                continue

            bucket = agg.get(atm_id)
            if bucket:
                risk_score = round(bucket["rank_score_sum"] / max_score, 3)
                risk_level = _risk_level(risk_score)

                # Cold-start entities reduce confidence: cap HIGH → MEDIUM
                if bucket["is_cold_start_any"] and risk_level == "HIGH":
                    risk_level = "MEDIUM"
                    risk_score = min(risk_score, 0.54)

                entity_count = len(set(bucket["entity_ids"]))
                crime_cats   = sorted(set(bucket["crime_categories"]))
                region_count = sum(
                    1 for oid, ob in agg.items()
                    if oid != atm_id and (ob["loc_meta"] or {}).get("city") == atm.get("city")
                )
                win_start   = sorted(bucket["windows_start"])[0] if bucket["windows_start"] else ""
                win_end     = sorted(bucket["windows_end"])[-1]  if bucket["windows_end"]   else ""
                time_bucket = _fmt_window(win_start, win_end)
                why         = _why_flagged(entity_count, region_count, crime_cats)
                entity_ids  = bucket["entity_ids"]
                is_cold     = bucket["is_cold_start_any"]
            else:
                risk_score   = 0.000
                risk_level   = "LOW"
                entity_count = 0
                crime_cats   = []
                win_start    = ""
                win_end      = ""
                time_bucket  = "Baseline / Unflagged"
                why          = "Baseline location — no anomalous target patterns detected."
                entity_ids   = []
                is_cold      = True

            # Apply min risk level filter
            if _LEVEL_ORDER.get(risk_level, 0) < min_level_int:
                continue

            record = {
                # ── Location (visible on map) ─────────────────────────────────
                "atm_id":         atm_id,
                "city":           atm.get("city", "?"),
                "state":          atm.get("state", "?"),
                "lat":            float(atm.get("latitude", atm.get("lat", 0.0))),
                "lon":            float(atm.get("longitude", atm.get("lon", 0.0))),
                "bank":           atm.get("bank", "?"),
                "atm_type":       atm.get("atm_type", "?"),
                "location_label": atm.get("location", atm.get("location_label", "?")),
                # ── Risk classification (visible on dashboard) ─────────────────
                "risk_level":     risk_level,
                "risk_score":     risk_score,
                "color":          RISK_COLORS[risk_level],
                # ── Human-readable summary (visible on click) ──────────────────
                "time_bucket":        time_bucket,
                "entity_count":       entity_count,
                "crime_categories":   crime_cats,
                "why_flagged":        why,
                "entity_ids":         entity_ids,
                "predicted_window_start": win_start,
                "predicted_window_end":   win_end,
                "is_cold_start":      is_cold,
                # pydeck tooltip field — rendered on hover
                "tooltip_label":      f"{atm.get('bank', '?')}, {atm.get('city', '?')}",
            }

            # ── Safety assertion: no internal fields leaked ────────────────────
            for field in INTERNAL_FIELDS:
                assert field not in record, f"INTERNAL FIELD LEAK: '{field}' in HeatmapRecord"

            records.append(record)

        records.sort(key=lambda r: r["risk_score"], reverse=True)
        return records


# ── Module-level singleton ─────────────────────────────────────────────────────

_assembler_instance: Optional[HeatmapAssembler] = None


def get_heatmap_assembler() -> HeatmapAssembler:
    global _assembler_instance
    if _assembler_instance is None:
        _assembler_instance = HeatmapAssembler()
    return _assembler_instance
