"""
delivery_model/tools.py
------------------------
CrewAI @tool wrappers for Component 4 (Delivery Model).

TOOLS:
  1. route_risk_engine_outputs_tool — executes deterministic routing across channels
  2. submit_appeal_tool             — dispute endpoint (tracking_id → appealed status)
  3. update_review_status_tool      — manual decision endpoint (actioned/dismissed/resolved)
  4. get_delivery_audit_log_tool    — internal audit trail
  5. get_queued_actions_tool        — inspect items in authority or bank queues
"""

import json

from crewai.tools import tool

from delivery_model.router import DeliveryRouter
from delivery_model.appeals import get_appeals_manager
from delivery_model.audit import get_delivery_audit_log


@tool("Route Risk Engine Outputs to Downstream Channels")
def route_risk_engine_outputs_tool(
    variance_results_json: str,
    prediction_results_json: str,
    regional_threshold: float = 0.75,
    cooldown_minutes: int = 1440,
) -> str:
    """
    Consumes Variance Model aggregated entities + Prediction Model heatmap records
    and routes each item to Civilian Alerts, Authority Review Queue, or Bank Fraud Queues.

    Args:
        variance_results_json:   JSON string of variance model results.
        prediction_results_json: JSON string of prediction model results.
        regional_threshold:      Minimum regional risk score to trigger civilian alert (default 0.75).
        cooldown_minutes:        Cooldown window in minutes for civilian alerts per region (default 1440 = 24h).

    Returns:
        JSON string containing civilian_alerts, authority_queue, and bank_queues.
    """
    var_res  = json.loads(variance_results_json)
    pred_res = json.loads(prediction_results_json)

    router = DeliveryRouter(
        regional_threshold=regional_threshold,
        cooldown_minutes=cooldown_minutes,
    )
    result = router.route_all(var_res, pred_res)
    return json.dumps(result)


@tool("Submit Dispute Appeal for Review Item")
def submit_appeal_tool(
    tracking_id: str,
    dispute_reason: str,
    advocate_name: str = "Self / Legal Advocate",
) -> str:
    """
    Recourse Path Endpoint: Submit a formal dispute for a flagged phone, IP, or bank account.
    Transitions status to 'appealed' and re-queues item for senior reviewer inspection.

    Args:
        tracking_id:    Unique tracking ID (e.g. TRK-A8F31C).
        dispute_reason: Detailed statement explaining why the flag is disputed.
        advocate_name:  Name of person or legal advocate submitting the appeal.

    Returns:
        JSON string — updated review queue record.
    """
    appeals_mgr = get_appeals_manager()
    record = appeals_mgr.submit_appeal(
        tracking_id=tracking_id,
        dispute_reason=dispute_reason,
        advocate_name=advocate_name,
    )
    if not record:
        return json.dumps({"error": f"Tracking ID '{tracking_id}' not found."})
    return json.dumps(record)


@tool("Update Review Status by Manual Reviewer")
def update_review_status_tool(
    tracking_id: str,
    new_status: str,
    reviewer_id: str = "OFFICER-001",
    notes: str = "",
) -> str:
    """
    Manual Decision Endpoint: Update status of a queue item ('actioned', 'dismissed', 'resolved').

    Args:
        tracking_id: Unique tracking ID.
        new_status:  Target status ('actioned', 'dismissed', or 'resolved').
        reviewer_id: ID of the reviewing officer or bank analyst.
        notes:       Explanation for decision.

    Returns:
        JSON string — updated record.
    """
    appeals_mgr = get_appeals_manager()
    try:
        record = appeals_mgr.update_status(
            tracking_id=tracking_id,
            new_status=new_status,
            reviewer_id=reviewer_id,
            notes=notes,
        )
        if not record:
            return json.dumps({"error": f"Tracking ID '{tracking_id}' not found."})
        return json.dumps(record)
    except Exception as err:
        return json.dumps({"error": str(err)})


@tool("Get Delivery Audit Log Trail")
def get_delivery_audit_log_tool(last_n: int = 30) -> str:
    """
    Return recent entries from the delivery audit trail.
    FOR AUTHORISED REVIEWERS / AUDITORS ONLY.

    Args:
        last_n: Number of recent audit entries to return.

    Returns:
        JSON string list of audit entries.
    """
    audit = get_delivery_audit_log()
    return json.dumps(audit.get_recent(last_n))


@tool("Get Queued Actions by Channel")
def get_queued_actions_tool(recipient_type: str = "authority", bank_name: str = "") -> str:
    """
    Inspect pending review queue items for Cyber Crime Authority or a specific Bank.

    Args:
        recipient_type: 'authority', 'bank', or 'civilian'.
        bank_name: Optional bank filter (e.g. 'State Bank of India') when recipient_type='bank'.

    Returns:
        JSON string list of items.
    """
    appeals_mgr = get_appeals_manager()
    if recipient_type == "bank" and bank_name:
        items = appeals_mgr.get_by_bank(bank_name)
    else:
        items = appeals_mgr.get_by_recipient(recipient_type)
    return json.dumps(items)
