"""
cyber_portal/tools.py
---------------------
CrewAI @tool wrappers for privileged Cyber Portal services.
Strictly wraps deterministic Python routines: zero LLM inference in the security or auth path.
"""

from __future__ import annotations
import json
from typing import Any, Dict, Optional
from crewai.tools import tool

from cyber_portal.auth.ingress import verify_step1_ingress
from cyber_portal.auth.step_up import verify_step2_step_up
from cyber_portal.audit.verifier import verify_audit_ledger
from cyber_portal.actions.handler import get_action_controller
from cyber_portal.dal.lea_dal import LEAService
from cyber_portal.dal.bank_dal import BankService
from cyber_portal.dal.devops_dal import InfraMetricsService


@tool("verify_cryptographic_ledger_tool")
def verify_cryptographic_ledger_tool(dummy: str = "") -> str:
    """
    Verify the cryptographic integrity of the Cyber Portal SHA-256 hash-chained audit ledger.
    Traverses from genesis to tip to detect tampering or broken hash links.
    """
    valid, broken_idx, message = verify_audit_ledger()
    return json.dumps({
        "valid": valid,
        "broken_block_index": broken_idx,
        "detail": message,
    }, indent=2)


@tool("get_devops_infra_metrics_tool")
def get_devops_infra_metrics_tool(devops_role_token: str) -> str:
    """
    Query infrastructure telemetry (pipeline latency, model recalibration drift logs, system memory).
    Restricted strictly to the DEVOPS role. Structurally isolated from citizen PII.
    """
    service = InfraMetricsService()
    try:
        health = service.get_pipeline_health(devops_role_token)
        quotas = service.get_api_quota_metrics(devops_role_token)
        return json.dumps({"health": health, "quotas": quotas}, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, indent=2)


@tool("execute_privileged_action_tool")
def execute_privileged_action_tool(
    role_token: str,
    tracking_id: str,
    action_type: str,
    justification_remarks: str,
    appeal_disposition: str = "",
) -> str:
    """
    Execute a privileged action (block, whitelist, debit_freeze, resolve_appeal) on a review item.
    Enforces RBAC, Four-Eyes principle, and commits block to the cryptographic ledger.
    """
    controller = get_action_controller()
    try:
        res = controller.execute_action(
            role_token=role_token,
            tracking_id=tracking_id,
            action_type=action_type,
            justification_remarks=justification_remarks,
            appeal_disposition=appeal_disposition if appeal_disposition else None,
        )
        return json.dumps(res, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, indent=2)
