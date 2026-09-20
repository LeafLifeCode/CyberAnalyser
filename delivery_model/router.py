"""
delivery_model/router.py
-------------------------
Core Deterministic Routing Engine for Component 4 (Delivery Model).

ROUTING RULES (Strict Deterministic Python — NOT LLM Reasoned):

  1. CIVILIAN ALERTS (recipient_type = "civilian"):
     - Fired ONLY when regional aggregate risk (from Heatmap region/city) exceeds threshold (default 0.75 / HIGH or CRITICAL).
     - Cooldown / Rate-limiting: 24-hour cooldown per region to avoid alert fatigue.
     - STRICT PRIVACY: Generic regional safety advice ONLY. NO entity-identifying details (no phone, IP, account numbers).

  2. AUTHORITY QUEUE (recipient_type = "authority"):
     - For "phone" and "ip" entities.
     - ALWAYS requires human review (requires_human_review = True). NEVER auto-actioned even if confidence = 1.0.
     - Full evidence trail included (signals_triggered, sub-scores, haversine speed) for LEA officer audit.

  3. BANK QUEUE (recipient_type = "bank"):
     - For "account" entities.
     - Partitioned by Bank Name (e.g. "HDFC Bank", "SBI"). Each bank only receives accounts relevant to it.
     - REQUIRES human review (requires_human_review = True).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from delivery_model.appeals import get_appeals_manager
from delivery_model.audit import get_delivery_audit_log

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

# Default regional threshold: 0.75 (CRITICAL or HIGH regional risk level)
DEFAULT_REGIONAL_THRESHOLD: float = 0.75

# Default civilian alert cooldown per region: 24 hours (1440 minutes)
DEFAULT_COOLDOWN_MINUTES: int = 1440


# Generic safety templates per region (STRICT PRIVACY — NO ENTITY DATA)
_CIVILIAN_SAFETY_TEMPLATES = {
    "Mumbai": (
        "⚠️ PUBLIC SAFETY ADVISORY — MUMBAI METRO REGION\n"
        "Heightened cyber fraud activity detected targeting banking channels in Mumbai.\n"
        "Do not share OTPs, PINs, or netbanking passwords with callers claiming to be bank officials.\n"
        "Report suspicious cybercrime complaints immediately to Helpline 1930 or cybercrime.gov.in."
    ),
    "Delhi": (
        "⚠️ PUBLIC SAFETY ADVISORY — DELHI NCR REGION\n"
        "Elevated Vishing and SIM swap scam activity reported across Delhi NCR.\n"
        "Never approve unknown UPI collect requests or click links in unsolicited SMS alerts.\n"
        "Report fraudulent transactions immediately to Helpline 1930."
    ),
    "Bangalore": (
        "⚠️ PUBLIC SAFETY ADVISORY — BANGALORE METRO\n"
        "Increased Tech Support & Job Scam activity detected targeting residents in Bangalore.\n"
        "Verify identity before transferring funds to unknown accounts. Helpline: 1930."
    ),
    "DEFAULT": (
        "⚠️ REGIONAL CYBER SAFETY ADVISORY\n"
        "Elevated cybercrime activity flagged in your region by intelligence models.\n"
        "Exercise caution during online financial transactions. Never disclose OTPs to anyone.\n"
        "Official Helpline: 1930 | National Cyber Crime Reporting Portal: cybercrime.gov.in"
    ),
}


class DeliveryRouter:
    """
    Consumes Variance Model aggregated entities + Prediction Model heatmap records
    and executes deterministic multi-channel routing.
    """

    def __init__(
        self,
        regional_threshold: float = DEFAULT_REGIONAL_THRESHOLD,
        cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES,
    ) -> None:
        self.regional_threshold = regional_threshold
        self.cooldown_minutes   = cooldown_minutes

        # region_name → last alert timestamp (ISO string)
        self._region_alert_history: Dict[str, str] = {}

    def route_all(
        self,
        variance_results: Dict[str, Any],
        prediction_results: Dict[str, Any],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Main entry point: execute deterministic routing across all 3 recipient channels.

        Returns:
            Dict containing:
              - "civilian_alerts": list of regional alert records
              - "authority_queue": list of phone/IP review queue items
              - "bank_queues":     dict of bank_name → list of account review queue items
        """
        variance_results    = variance_results or {}
        prediction_results  = prediction_results or {}
        aggregated_entities = variance_results.get("aggregated_entities", [])
        heatmap_records     = prediction_results.get("heatmap_records", [])

        appeals_mgr = get_appeals_manager()
        audit_log   = get_delivery_audit_log()

        civilian_alerts: List[Dict[str, Any]] = []
        authority_items: List[Dict[str, Any]] = []
        bank_items:      List[Dict[str, Any]] = []

        # ── 1. CIVILIAN ROUTING (Regional Risk Threshold + 24h Cooldown + Privacy)
        region_scores: Dict[str, float] = {}
        for h in heatmap_records:
            city  = h.get("city", "Unknown")
            score = h.get("risk_score", 0.0)
            region_scores[city] = max(region_scores.get(city, 0.0), score)

        now_dt = datetime.now(IST)

        for region, score in region_scores.items():
            if score >= self.regional_threshold:
                # Check cooldown
                last_alert_str = self._region_alert_history.get(region)
                is_cooldown_active = False

                if last_alert_str:
                    try:
                        last_dt = datetime.fromisoformat(last_alert_str)
                        mins_elapsed = (now_dt - last_dt).total_seconds() / 60.0
                        if mins_elapsed < self.cooldown_minutes:
                            is_cooldown_active = True
                    except Exception:
                        pass

                if is_cooldown_active:
                    # Log cooldown suppression to audit
                    audit_log.append({
                        "event":              "CIVILIAN_ALERT_SUPPRESSED",
                        "region":             region,
                        "regional_risk_score": score,
                        "threshold":          self.regional_threshold,
                        "reason":             f"Cooldown active ({self.cooldown_minutes}m window). Avoid alert fatigue.",
                    })
                else:
                    # Issue civilian alert (STRICT PRIVACY — NO ENTITY DATA)
                    alert_text = _CIVILIAN_SAFETY_TEMPLATES.get(
                        region, _CIVILIAN_SAFETY_TEMPLATES["DEFAULT"]
                    )
                    alert_rec = {
                        "recipient_type":        "civilian",
                        "region":                region,
                        "regional_risk_score":   round(score, 3),
                        "alert_text":            alert_text,
                        "cooldown_minutes":      self.cooldown_minutes,
                        "requires_human_review": False,
                        "issued_at":             now_dt.isoformat(),
                    }
                    self._region_alert_history[region] = now_dt.isoformat()
                    civilian_alerts.append(alert_rec)

                    audit_log.append({
                        "event":              "CIVILIAN_ALERT_ISSUED",
                        "region":             region,
                        "regional_risk_score": score,
                        "alert_text":         alert_text[:100] + "...",
                    })

        # ── 2. AUTHORITY ROUTING (Phone / IP → Manual Review Queue) ────────────
        # ── 3. BANK ROUTING (Account → Partitioned Bank Fraud Queue) ───────────

        for entity in aggregated_entities:
            entity_id   = entity["entity_id"]
            entity_type = entity["entity_type"]   # "phone" | "ip" | "account"
            score       = entity.get("combined_score", 0.0)
            signals     = entity.get("signals_triggered", [])

            # Extract location/region context
            region = "India Nationwide"
            for sig in signals:
                ev = sig.get("evidence", {})
                if ev.get("city"):
                    region = ev["city"]
                    break

            if entity_type in ("phone", "ip"):
                # Authority Route: ALWAYS requires human review
                rec_action = (
                    f"Manual Review Queue: Flagged {entity_type.upper()} with combined risk {score:.2f}. "
                    f"Investigate proxy rotation / SIM swap patterns before whitelist or block decision."
                )
                item = appeals_mgr.register_item(
                    recipient_type="authority",
                    entity_id=entity_id,
                    entity_type=entity_type,
                    risk_level=score,
                    region=region,
                    signals_triggered=signals,
                    recommended_action=rec_action,
                    requires_human_review=True,    # MANDATORY
                    evidence_summary={
                        "combined_score":    score,
                        "signals_count":     len(signals),
                        "signal_types":      [s.get("signal_type") for s in signals],
                    },
                )
                authority_items.append(item)

            elif entity_type == "account":
                # Bank Route: Partitioned by institution/bank name
                # Infer bank name from event context or default to Bank Fraud Dept
                bank_name = "State Bank of India"
                for sig in signals:
                    ev = sig.get("evidence", {})
                    if ev.get("bank"):
                        bank_name = ev["bank"]
                        break

                rec_action = (
                    f"Bank Fraud Review: Account {entity_id} flagged for deposit surge / mule chain activity. "
                    f"Freeze credits, review 30-day transaction history, and contact account holder."
                )
                item = appeals_mgr.register_item(
                    recipient_type="bank",
                    entity_id=entity_id,
                    entity_type=entity_type,
                    risk_level=score,
                    region=region,
                    signals_triggered=signals,
                    recommended_action=rec_action,
                    requires_human_review=True,    # MANDATORY
                    bank_name=bank_name,
                    evidence_summary={
                        "combined_score": score,
                        "bank_name":      bank_name,
                        "signals_count":  len(signals),
                    },
                )
                bank_items.append(item)

        # Partition bank items by bank name
        bank_queues: Dict[str, List[Dict[str, Any]]] = {}
        for item in bank_items:
            bname = item["bank_name"]
            if bname not in bank_queues:
                bank_queues[bname] = []
            bank_queues[bname].append(item)

        return {
            "civilian_alerts": civilian_alerts,
            "authority_queue": authority_items,
            "bank_queues":     bank_queues,
        }
