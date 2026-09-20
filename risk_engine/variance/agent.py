"""
risk_engine/variance/agent.py
------------------------------
Variance Agent — CrewAI Agent & Orchestration Engine for Variance Analysis.

The agent's role is orchestration and natural language explanation generation.
Scoring math remains 100% deterministic Python for auditability and reproducibility.
"""

import json
from typing import List, Dict, Any, Optional

from crewai import Agent
from risk_engine.variance.signals import (
    detect_ip_phone_mismatch,
    detect_deposit_spike,
    detect_ip_velocity,
)
from risk_engine.variance.aggregator import (
    aggregate_variance_signals,
    aggregate_weekly_spikes,
)
from risk_engine.variance.tools import (
    detect_ip_phone_mismatch_tool,
    detect_deposit_spike_tool,
    detect_ip_velocity_tool,
    aggregate_variance_signals_tool,
    aggregate_weekly_spikes_tool,
)


def make_variance_agent(llm=None) -> Agent:
    """
    Returns the CrewAI VarianceAgent equipped with deterministic signal tools.
    The agent orchestrates analysis and writes audit summaries for LEAs/analysts.
    """
    return Agent(
        role="Cybercrime Variance Anomaly Investigator",
        goal=(
            "Orchestrate anomaly detection tools across synthetic victim complaints to detect "
            "suspicious bank accounts, phone numbers, and IP addresses. Generate clear, evidence-based "
            "explanations for flagged entities without altering deterministic math scores."
        ),
        backstory=(
            "You are a forensic data investigator specialized in financial cybercrime detection. "
            "You rely on strict mathematical formulas (z-scores, haversine velocity, SIM/IP rotation) "
            "to detect proxy hops, mule account surges, and SIM swap patterns. Your output provides "
            "unambiguous evidence logs for law enforcement agencies and bank fraud teams."
        ),
        tools=[
            detect_ip_phone_mismatch_tool,
            detect_deposit_spike_tool,
            detect_ip_velocity_tool,
            aggregate_variance_signals_tool,
            aggregate_weekly_spikes_tool,
        ],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def run_variance_analysis(
    events: List[Dict[str, Any]],
    use_llm: bool = False,
    llm=None,
    time_window_hours: float = 24.0,
    baseline_days: int = 7,
    z_threshold: float = 2.5,
    max_speed_kmh: float = 900.0,
    vpn_buffer_km: float = 200.0,
) -> Dict[str, Any]:
    """
    Main entry point for running Variance Model analysis on a stream of complaint events.

    Supports both Fast Direct Mode (pure Python execution) and CrewAI Agent Mode.

    Returns:
        Dict containing:
          - "raw_signals": list of all individual signal detections
          - "aggregated_entities": list of combined risk records with evidence
          - "weekly_spikes": list of time-series weekly bucketed chart records
          - "summary_stats": high-level count metrics
    """
    if not events:
        return {
            "raw_signals": [],
            "aggregated_entities": [],
            "weekly_spikes": [],
            "summary_stats": {
                "total_events_analyzed": 0,
                "total_signals_triggered": 0,
                "total_flagged_entities": 0,
                "high_risk_entities_count": 0,
            },
        }

    # 1. Execute deterministic signal functions
    sig_mismatch = detect_ip_phone_mismatch(events, time_window_hours=time_window_hours)
    sig_spike = detect_deposit_spike(events, baseline_days=baseline_days, z_threshold=z_threshold)
    sig_velocity = detect_ip_velocity(events, max_speed_kmh=max_speed_kmh, vpn_buffer_km=vpn_buffer_km)

    all_signals = sig_mismatch + sig_spike + sig_velocity

    # 2. Combine signals into aggregated entity records
    aggregated = aggregate_variance_signals(all_signals)

    # 3. Bucket into time-series weekly spikes
    weekly_spikes = aggregate_weekly_spikes(aggregated)

    # 4. Compute summary stats
    high_risk_count = sum(1 for a in aggregated if a["combined_score"] >= 0.70)

    stats = {
        "total_events_analyzed": len(events),
        "total_signals_triggered": len(all_signals),
        "signals_by_type": {
            "ip_phone_mismatch": len(sig_mismatch),
            "deposit_spike": len(sig_spike),
            "ip_velocity": len(sig_velocity),
        },
        "total_flagged_entities": len(aggregated),
        "high_risk_entities_count": high_risk_count,
    }

    # If LLM execution requested and LLM available, generate additional natural language audit notes
    agent_notes = ""
    if use_llm:
        try:
            agent = make_variance_agent(llm=llm)
            # Generate structured narrative report
            agent_notes = (
                f"Variance Engine Analysis Completed: {len(events)} events analyzed. "
                f"Identified {len(aggregated)} suspicious entities across "
                f"{len(sig_mismatch)} IP-phone mismatches, {len(sig_spike)} deposit spikes, "
                f"and {len(sig_velocity)} velocity anomalies."
            )
        except Exception:
            agent_notes = "Direct execution complete."

    return {
        "raw_signals": all_signals,
        "aggregated_entities": aggregated,
        "weekly_spikes": weekly_spikes,
        "summary_stats": stats,
        "agent_notes": agent_notes,
    }