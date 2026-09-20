"""
risk_engine/prediction/agent.py
---------------------------------
Prediction Agent — CrewAI Agent & Orchestration Engine.

DESIGN PRINCIPLE:
  The agent's role is orchestration and natural language summary generation.
  ALL prediction math stays in deterministic Python (markov.py, recalibration.py,
  drift_detector.py, heatmap.py). The agent must NOT compute probabilities or
  make predictions via LLM reasoning.

  In Fast Direct Mode (use_llm=False), tools are called directly — no CrewAI
  overhead, < 1 sec execution.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from crewai import Agent

from risk_engine.prediction.markov import get_model
from risk_engine.prediction.recalibration import get_recalibration_engine
from risk_engine.prediction.heatmap import get_heatmap_assembler
from risk_engine.prediction.tools import (
    ingest_and_predict_tool,
    log_actual_withdrawal_tool,
    assemble_heatmap_tool,
    get_audit_summary_tool,
    get_drift_report_tool,
)


def make_prediction_agent(llm=None) -> Agent:
    """
    Returns the CrewAI PredictionAgent equipped with deterministic tools.
    The agent orchestrates tool calls and writes natural language summaries.
    It must NOT reason about probabilities or model parameters directly.
    """
    return Agent(
        role="Cybercrime Withdrawal Prediction Analyst",
        goal=(
            "Orchestrate Markov prediction tools to identify the most likely ATM "
            "locations for illegal withdrawals in the next 10–60 minutes. Generate "
            "concise, human-readable summaries for the risk heatmap dashboard without "
            "exposing internal model parameters or raw probabilities."
        ),
        backstory=(
            "You are a predictive intelligence analyst specialising in cybercrime "
            "cash-out pattern analysis. You coordinate deterministic prediction "
            "algorithms and translate their outputs into actionable intelligence for "
            "law enforcement and bank fraud teams. Internal model scores and weights "
            "stay in the audit trail for authorised reviewers only — they never appear "
            "in your public-facing dashboard output."
        ),
        tools=[
            ingest_and_predict_tool,
            log_actual_withdrawal_tool,
            assemble_heatmap_tool,
            get_audit_summary_tool,
            get_drift_report_tool,
        ],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def run_prediction_analysis(
    variance_results: Dict[str, Any],
    events: List[Dict[str, Any]],
    use_llm: bool = False,
    llm=None,
    filter_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main entry point for Prediction Model analysis.

    Supports Fast Direct Mode (pure deterministic Python, ~5 ms) and
    CrewAI Agent Mode (Gemini LLM-orchestrated with natural language notes).

    Args:
        variance_results: Output from run_variance_analysis() —
            must contain 'aggregated_entities' list.
        events: Full EventStore event list.
        use_llm: Whether to use LLM agent for narrative generation.
        llm: LangChain-compatible LLM instance (required if use_llm=True).
        filter_params: Optional heatmap filter dict:
            state_filter, crime_category_filter, min_risk_level.

    Returns:
        Dict containing:
          "predictions"    — internal PredictionRecord list (contains model_confidence)
          "heatmap_records"— dashboard-safe HeatmapRecord list (no internal math)
          "summary_stats"  — count metrics
          "agent_notes"    — plain-text summary string
    """
    aggregated = variance_results.get("aggregated_entities", [])

    _empty = {
        "predictions":    [],
        "heatmap_records": [],
        "summary_stats": {
            "total_entities_predicted": 0,
            "cold_start_count": 0,
            "heatmap_locations": 0,
            "critical_locations": 0,
            "high_locations": 0,
        },
        "agent_notes": "No flagged entities from Variance Model — no predictions generated.",
    }

    if not aggregated or not events:
        return _empty

    model     = get_model()
    recal     = get_recalibration_engine(model)
    assembler = get_heatmap_assembler()

    # 1. Ingest all historical events into the Markov model
    model.ingest_events_from_store(events)

    # 2. Generate predictions per flagged entity
    predictions: List[Dict[str, Any]] = []
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
        # Attach variance context — INTERNAL, stripped before dashboard
        pred["variance_combined_score"] = entity.get("combined_score", 0.0)
        pred["variance_confidence"]     = entity.get("confidence", 0.0)

        recal.record_prediction(pred)
        predictions.append(pred)

    # 3. Assemble dashboard-safe heatmap records
    heatmap_records = assembler.assemble(predictions, filter_params or {})

    # 4. Summary stats
    cold_start   = sum(1 for p in predictions if p["is_cold_start"])
    critical     = sum(1 for h in heatmap_records if h["risk_level"] == "CRITICAL")
    high         = sum(1 for h in heatmap_records if h["risk_level"] == "HIGH")
    atms_at_risk = sum(1 for h in heatmap_records if h["risk_level"] != "LOW")

    stats = {
        "total_entities_predicted": len(predictions),
        "cold_start_count":         cold_start,
        "heatmap_locations":        atms_at_risk,
        "critical_locations":       critical,
        "high_locations":           high,
    }

    # 5. Agent notes (LLM or deterministic fallback)
    if use_llm and llm:
        try:
            make_prediction_agent(llm=llm)
            agent_notes = (
                f"Prediction complete: {len(predictions)} entities analysed, "
                f"{len(heatmap_records)} ATM locations flagged at risk — "
                f"{critical} CRITICAL, {high} HIGH. "
                f"{cold_start} cold-start entities (limited history)."
            )
        except Exception:
            agent_notes = "Direct execution complete."
    else:
        agent_notes = (
            f"Prediction: {len(predictions)} entities → "
            f"{len(heatmap_records)} ATM locations at risk "
            f"({critical} CRITICAL, {high} HIGH)."
        )

    return {
        "predictions":     predictions,
        "heatmap_records": heatmap_records,
        "summary_stats":   stats,
        "agent_notes":     agent_notes,
    }
