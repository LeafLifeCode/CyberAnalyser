"""
generator/tools/alert_tools.py
--------------------------------
Formats enriched attacker data into structured SMS-style prompts
for consumption by the next CrewAI agent (risk management agent).
Also computes a simple heuristic risk score.
"""

import json
import uuid
from datetime import datetime

from crewai.tools import tool


def _compute_risk_score(entry: dict) -> float:
    """
    Heuristic risk scorer (0.0 - 1.0).
    Higher score = faster action required.

    Modus risk weights (NCRP categories):
      +0.10  UPI Fraud / Internet Banking / Debit-Credit Card  — instant digital transfer, ATM cash-out very fast
      +0.07  E-Wallet / Fraud Call / Business Email             — moderate speed to cash-out
      +0.04  Demat / Depository Fraud                          — usually slower, needs demat liquidation
    """
    score = 0.0
    # Large total amount -> higher risk
    total = entry.get("total_amount_inr", 0)
    score += min(total / 200_000.0, 0.30)
    # Short lag from report to withdrawal -> attacker still active
    lag = entry.get("time_from_report_minutes", 60)
    score += max(0, (60 - lag) / 60) * 0.25
    # Deep mule chain -> sophisticated attacker
    depth = entry.get("mule_chain_depth", 3)
    score += min(depth / 7.0, 0.20)
    # More transactions = more aggressive fraud
    txn_count = len(entry.get("transactions", []))
    score += min(txn_count / 10.0, 0.15)
    # Modus operandi risk weight (NCRP official categories)
    modi = entry.get("attacker_profile", {}).get("modus_operandi", "")
    high_risk_modi = {
        "UPI Fraud",
        "Internet Banking Related Fraud",
        "Debit/Credit Card Fraud/Sim Swap Fraud",
    }
    medium_risk_modi = {
        "E-Wallet Related Fraud",
        "Fraud Call/Vishing",
        "Business Email Compromise/Email Takeover",
    }
    if modi in high_risk_modi:
        score += 0.10
    elif modi in medium_risk_modi:
        score += 0.07
    else:                          # Demat/Depository Fraud
        score += 0.04
    return round(min(score, 1.0), 3)


def _risk_label(score: float) -> str:
    if score >= 0.75: return "CRITICAL"
    if score >= 0.50: return "HIGH"
    if score >= 0.25: return "MEDIUM"
    return "LOW"


def _format_sms(entry: dict, score: float, label: str, complaint_id: str) -> str:
    """Build the SMS prompt string that the next agent reads."""
    atm   = entry.get("atm", {})
    prof  = entry.get("attacker_profile", {})
    chain = entry.get("mule_chain", [])
    t     = entry.get("predicted_withdrawal_time", "UNKNOWN")

    try:
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30), name="IST")
        dt_val = datetime.fromisoformat(t.replace("Z", "+00:00"))
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=IST)
        else:
            dt_val = dt_val.astimezone(IST)
        t_fmt = dt_val.strftime("%d-%b-%Y %H:%M IST")
    except Exception:
        t_fmt = t

    hop_states = " ? ".join(h.get("state", "?") for h in chain[:5])

    return (
        f"[SYNTHETIC ALERT | DO NOT USE AS LEGAL EVIDENCE]\n"
        f"{'='*55}\n"
        f"COMPLAINT ID  : {complaint_id}\n"
        f"RISK LEVEL    : {label} ({score:.2f}/1.00)\n"
        f"ATTACKER ID   : {prof.get('attacker_id', 'UNKNOWN')}\n"
        f"MODUS         : {prof.get('modus_operandi', 'Unknown')}\n"
        f"ACTIVE PHONE  : {prof.get('active_phone', 'SPOOFED')}\n"
        f"ACTIVE IP     : {prof.get('active_ip', 'VPN')} ({prof.get('vpn_provider', '?')})\n"
        f"VICTIM STATE  : {entry.get('victim_state', 'Unknown')}\n"
        f"FRAUD AMOUNT  : INR {entry.get('total_amount_inr', 0):,.2f}\n"
        f"FINAL @ ATM   : INR {entry.get('final_amount_inr', 0):,.2f} (after mule fees)\n"
        f"MULE CHAIN    : {entry.get('mule_chain_depth', '?')} hops ({hop_states})\n"
        f"PREDICTED ATM : {atm.get('location_label', atm.get('location', 'UNKNOWN'))}\n"
        f"ATM CITY/STATE: {atm.get('city', '?')}, {atm.get('state', '?')}\n"
        f"ATM COORDS    : {atm.get('latitude', 0):.6f}°N, {atm.get('longitude', 0):.6f}°E\n"
        f"ATM BANK      : {atm.get('bank', '?')} ({atm.get('atm_type', '?')})\n"
        f"WITHDRAWAL    : {t_fmt}\n"
        f"TIME FROM RPT : {entry.get('time_from_report_minutes', '?')} minutes\n"
        f"{'='*55}\n"
    )


@tool("Format Alert SMS Prompts")
def format_alert_prompts(enriched_data_json: str, cycle_timestamp: str) -> str:
    """
    Score each attacker event and format as SMS prompt for the next CrewAI agent.

    Args:
        enriched_data_json: JSON from assign_atm_withdrawal tool.
        cycle_timestamp: ISO datetime string of this generation cycle.

    Returns:
        JSON string — list of finalised ComplaintEvent dicts including sms_prompt.
    """
    events    = json.loads(enriched_data_json)
    finalised = []

    for entry in events:
        complaint_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"
        score  = _compute_risk_score(entry)
        label  = _risk_label(score)
        prompt = _format_sms(entry, score, label, complaint_id)

        finalised.append({
            "complaint_id":   complaint_id,
            "generated_at":   cycle_timestamp,
            "synthetic":      True,
            "attacker":       entry.get("attacker_profile", {}),
            "victim_state":   entry.get("victim_state"),
            "transactions":   entry.get("transactions", []),
            "mule_chain":     entry.get("mule_chain", []),
            "atm":            entry.get("atm", {}),
            "total_amount_inr":          entry.get("total_amount_inr", 0),
            "final_amount_inr":          entry.get("final_amount_inr", 0),
            "mule_chain_depth":          entry.get("mule_chain_depth", 0),
            "predicted_withdrawal_time": entry.get("predicted_withdrawal_time"),
            "time_from_report_minutes":  entry.get("time_from_report_minutes", 0),
            "risk_score":  score,
            "risk_label":  label,
            "sms_prompt":  prompt,
        })

    return json.dumps(finalised)
