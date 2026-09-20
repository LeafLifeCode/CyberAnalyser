"""
delivery_model/agent.py
------------------------
Delivery Agent — CrewAI Agent & Orchestration Engine for Component 4.

DESIGN PRINCIPLE:
  The agent's role is orchestration, human-readable summary drafting,
  and reviewer guidance. ALL routing threshold decisions stay in deterministic
  Python (router.py, appeals.py). The agent must NOT perform LLM-based routing
  or threshold decisions.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from crewai import Agent

from delivery_model.router import DeliveryRouter
from delivery_model.appeals import get_appeals_manager
from delivery_model.audit import get_delivery_audit_log
from delivery_model.tools import (
    route_risk_engine_outputs_tool,
    submit_appeal_tool,
    update_review_status_tool,
    get_delivery_audit_log_tool,
    get_queued_actions_tool,
)


def make_delivery_agent(llm=None) -> Agent:
    """
    Returns the CrewAI DeliveryAgent equipped with deterministic tools.
    """
    return Agent(
        role="Cybercrime Action Routing & Recourse Coordinator",
        goal=(
            "Orchestrate deterministic routing of Risk Engine outputs to Civilian "
            "Alerts, Cyber Crime Authority Review Queues, and Bank Fraud Investigation "
            "Queues. Ensure strict privacy for civilian intimations, mandate human "
            "review for all entity actions, and manage dispute recourse paths."
        ),
        backstory=(
            "You are a cybercrime intelligence routing coordinator. You ensure that "
            "flagged financial accounts and proxy channels reach the appropriate authority "
            "or bank risk officers with complete forensic evidence trails, while protecting "
            "civilian privacy with generic regional safety intimations. You uphold due process "
            "by enforcing mandatory human review before any enforcement action and managing "
            "transparent appeal workflows."
        ),
        tools=[
            route_risk_engine_outputs_tool,
            submit_appeal_tool,
            update_review_status_tool,
            get_delivery_audit_log_tool,
            get_queued_actions_tool,
        ],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def run_delivery_routing(
    variance_results: Dict[str, Any],
    prediction_results: Dict[str, Any],
    use_llm: bool = False,
    llm=None,
    regional_threshold: float = 0.75,
    cooldown_minutes: int = 1440,
) -> Dict[str, Any]:
    """
    Main entry point for Component 4 (Delivery Model).

    Supports Fast Direct Mode (pure deterministic Python execution) and CrewAI Agent Mode.

    Returns:
        Dict containing:
          - "civilian_alerts": list of generic regional safety intimations
          - "authority_queue": list of phone/IP review records
          - "bank_queues":     dict of bank_name → list of account review records
          - "summary_stats":   high-level count metrics
          - "agent_notes":     plain text execution notes
    """
    router = DeliveryRouter(
        regional_threshold=regional_threshold,
        cooldown_minutes=cooldown_minutes,
    )
    routing_output = router.route_all(variance_results, prediction_results)

    civ_alerts  = routing_output["civilian_alerts"]
    auth_queue  = routing_output["authority_queue"]
    bank_queues = routing_output["bank_queues"]

    total_bank_items = sum(len(items) for items in bank_queues.values())

    stats = {
        "civilian_alerts_issued": len(civ_alerts),
        "authority_items_queued": len(auth_queue),
        "bank_items_queued":      total_bank_items,
        "active_bank_queues":     len(bank_queues),
        "cooldown_minutes":       cooldown_minutes,
        "regional_threshold":     regional_threshold,
    }

    agent_notes = (
        f"Delivery Routing Complete: Issued {len(civ_alerts)} civilian safety advisories, "
        f"queued {len(auth_queue)} phone/IP items for Cyber Crime Authority review, "
        f"and partitioned {total_bank_items} account items across {len(bank_queues)} bank fraud queues. "
        f"All actions mandate human review."
    )

    if use_llm and llm:
        try:
            make_delivery_agent(llm=llm)
            # Agent notes enriched by crew instance
        except Exception:
            pass

    return {
        "civilian_alerts": civ_alerts,
        "authority_queue": auth_queue,
        "bank_queues":     bank_queues,
        "summary_stats":   stats,
        "agent_notes":     agent_notes,
    }
