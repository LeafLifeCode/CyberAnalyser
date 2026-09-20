"""
risk_engine/prediction/tools.py
---------------------------------
CrewAI @tool wrappers for the Prediction Model.

TOOL SEPARATION PRINCIPLE:
  ingest_and_predict_tool  → internal predictions (has model_confidence, probability)
  assemble_heatmap_tool    → dashboard-safe records (strips all internal fields)
  log_actual_withdrawal_tool → recalibration → AuditLog only
  get_audit_summary_tool   → INTERNAL ONLY (human reviewer / auditor)
  get_drift_report_tool    → INTERNAL ONLY (human reviewer / auditor)

The dashboard tab in app.py must ONLY consume the output of assemble_heatmap_tool.
"""

import json

from crewai.tools import tool

from risk_engine.prediction.markov import get_model
from risk_engine.prediction.recalibration import get_recalibration_engine, get_audit_log
from risk_engine.prediction.drift_detector import get_drift_detector
from risk_engine.prediction.heatmap import get_heatmap_assembler


@tool("Ingest Variance Signals and Generate ATM Predictions")
def ingest_and_predict_tool(variance_results_json: str, events_json: str) -> str:
    """
    Ingest flagged entities from the Variance Model and historical events into
    the Markov ATM model, then generate next-withdrawal predictions per entity.

    Args:
        variance_results_json: JSON from run_variance_analysis() — must contain
            'aggregated_entities' list.
        events_json: JSON list of EventStore records (full historical stream).

    Returns:
        JSON string — list of internal PredictionRecord dicts.
        CONTAINS internal fields (probability, model_confidence).
        Pass to assemble_heatmap_tool for dashboard-safe output.
    """
    variance_results = json.loads(variance_results_json)
    events           = json.loads(events_json)

    model = get_model()
    recal = get_recalibration_engine(model)
    model.ingest_events_from_store(events)

    aggregated   = variance_results.get("aggregated_entities", [])
    predictions  = []

    for entity in aggregated:
        entity_id   = entity["entity_id"]
        entity_type = entity["entity_type"]
        crime_cats  = list({s["signal_type"] for s in entity.get("signals_triggered", [])})

        pred = model.predict(
            entity_id=entity_id,
            entity_type=entity_type,
            crime_categories=crime_cats,
            top_k=15,
        )
        # Attach variance context (INTERNAL — stripped before dashboard)
        pred["variance_combined_score"] = entity.get("combined_score", 0.0)
        pred["variance_confidence"]     = entity.get("confidence", 0.0)

        recal.record_prediction(pred)
        predictions.append(pred)

    return json.dumps(predictions)


@tool("Log Actual Withdrawal for Recalibration")
def log_actual_withdrawal_tool(
    entity_id: str,
    actual_atm_id: str,
    actual_timestamp: str,
) -> str:
    """
    Log an actual confirmed withdrawal to trigger incremental model recalibration.
    Compares actual vs. predicted, updates Markov transition counts, writes to audit.

    INTERNAL USE ONLY — output is an AuditLog entry, not a dashboard record.

    Args:
        entity_id:        Entity ID matching the Variance Model record.
        actual_atm_id:    ATM-XXX ID where the actual withdrawal occurred.
        actual_timestamp: ISO datetime of the confirmed withdrawal.

    Returns:
        JSON string — internal recalibration audit entry.
    """
    model    = get_model()
    recal    = get_recalibration_engine(model)
    detector = get_drift_detector()

    result = recal.log_actual_withdrawal(entity_id, actual_atm_id, actual_timestamp)

    # Drift detection: record outcome and flag if accuracy drops below 40%
    drift_triggered = detector.record_outcome(entity_id, result["was_correct"])
    if drift_triggered:
        get_audit_log().append({
            "entity_id":  entity_id,
            "event":      "CONCEPT_DRIFT_DETECTED",
            "hit_rate":   detector.get_hit_rate(entity_id),
            "threshold":  0.40,
            "action":     "Trailing window reset. Human reviewer notified via audit log.",
            "notes":      "Hit rate dropped below 40% over last 20 predictions.",
        })
        result["drift_flag"] = True

    return json.dumps(result)


@tool("Assemble Risk Heatmap Dashboard Data")
def assemble_heatmap_tool(
    predictions_json: str,
    filter_params_json: str = "{}",
) -> str:
    """
    Convert internal prediction records into dashboard-safe GIS heatmap records.
    Strips ALL internal model fields — output is safe for display.

    Args:
        predictions_json:   JSON list of PredictionRecords (from ingest_and_predict_tool).
        filter_params_json: JSON dict with optional keys:
            state_filter, crime_category_filter, min_risk_level.

    Returns:
        JSON string — list of HeatmapRecord dicts (dashboard-safe, no internal math).
    """
    predictions   = json.loads(predictions_json)
    filter_params = json.loads(filter_params_json)
    assembler     = get_heatmap_assembler()
    records       = assembler.assemble(predictions, filter_params)
    return json.dumps(records)


@tool("Get Internal Audit Log Summary")
def get_audit_summary_tool(last_n: int = 20) -> str:
    """
    Return the most recent N entries from the internal recalibration audit log.

    FOR HUMAN REVIEWER / AUDITOR ROLE ONLY.
    Must NOT be rendered in the public-facing dashboard UI.

    Args:
        last_n: Number of most recent entries to return (default 20).

    Returns:
        JSON string — list of audit entries including recalibration deltas.
    """
    return json.dumps(get_audit_log().get_recent(last_n))


@tool("Get Concept Drift Report")
def get_drift_report_tool(entity_id: str = "") -> str:
    """
    Return current drift detection status for a specific entity or all entities.

    FOR HUMAN REVIEWER / AUDITOR ROLE ONLY.
    Must NOT be rendered in the public-facing dashboard UI.

    Args:
        entity_id: Specific entity ID to check. Empty string = return all entities.

    Returns:
        JSON string — drift status dict.
    """
    detector = get_drift_detector()
    if entity_id.strip():
        rate = detector.get_hit_rate(entity_id)
        return json.dumps({
            "entity_id":    entity_id,
            "hit_rate":     rate,
            "drift_events": detector.get_drift_count(entity_id),
            "drift_detected": rate is not None and rate < 0.40,
        })
    return json.dumps(detector.get_all_statuses())
