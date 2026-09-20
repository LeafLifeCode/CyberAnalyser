"""
tests/test_delivery_model.py
------------------------------
Unit tests for Component 4 (Delivery Model & Action Routing Engine).

Tests:
  1. test_civilian_alert_cooldown         — alert fires, then suppresses on repeat within 24h cooldown
  2. test_authority_route_requires_human — phone/IP items ALWAYS have requires_human_review=True, never auto-action
  3. test_bank_route_partitioning        — account items are correctly partitioned by bank name
  4. test_civilian_privacy_no_entity_data — civilian alerts contain NO account, phone, or IP strings
  5. test_appeal_state_machine           — tracking ID created, status moves pending_review → appealed → resolved
  6. test_delivery_audit_logging         — routing actions and status transitions generate audit log entries
"""

import unittest
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from delivery_model.router import DeliveryRouter
from delivery_model.appeals import AppealsManager, get_appeals_manager, reset_appeals_manager
from delivery_model.audit import DeliveryAuditLog, get_delivery_audit_log, reset_delivery_audit_log

_MOCK_VARIANCE_RESULTS = {
    "aggregated_entities": [
        {
            "entity_id":      "9876543210",
            "entity_type":    "phone",
            "combined_score": 0.88,
            "confidence":     0.85,
            "signals_triggered": [
                {
                    "signal_type": "ip_phone_mismatch",
                    "sub_score":   0.88,
                    "evidence":    {"city": "Mumbai", "distinct_ip_count": 4},
                }
            ],
        },
        {
            "entity_id":      "192.168.1.50",
            "entity_type":    "ip",
            "combined_score": 0.92,
            "confidence":     0.90,
            "signals_triggered": [
                {
                    "signal_type": "ip_velocity",
                    "sub_score":   0.92,
                    "evidence":    {"city": "Delhi", "calculated_speed_kmh": 1200.0},
                }
            ],
        },
        {
            "entity_id":      "ACC-998877",
            "entity_type":    "account",
            "combined_score": 0.95,
            "confidence":     0.90,
            "signals_triggered": [
                {
                    "signal_type": "deposit_spike",
                    "sub_score":   0.95,
                    "evidence":    {"bank": "HDFC Bank", "city": "Bangalore"},
                }
            ],
        },
        {
            "entity_id":      "ACC-112233",
            "entity_type":    "account",
            "combined_score": 0.82,
            "confidence":     0.80,
            "signals_triggered": [
                {
                    "signal_type": "deposit_spike",
                    "sub_score":   0.82,
                    "evidence":    {"bank": "State Bank of India", "city": "Mumbai"},
                }
            ],
        },
    ]
}

_MOCK_PREDICTION_RESULTS = {
    "heatmap_records": [
        {
            "atm_id":     "ATM-001",
            "city":       "Mumbai",
            "state":      "Maharashtra",
            "risk_level": "CRITICAL",
            "risk_score": 0.92,
        },
        {
            "atm_id":     "ATM-002",
            "city":       "Delhi",
            "state":      "Delhi",
            "risk_level": "HIGH",
            "risk_score": 0.78,
        },
    ]
}


class TestCivilianAlerts(unittest.TestCase):

    def setUp(self):
        reset_delivery_audit_log()
        reset_appeals_manager()
        self.router = DeliveryRouter(regional_threshold=0.75, cooldown_minutes=1440)

    def test_civilian_alert_cooldown(self):
        """
        Civilian alert must fire on 1st run for regional_risk >= 0.75,
        and MUST be suppressed on 2nd immediate run due to 24h cooldown.
        """
        # Run 1: Should issue alerts for Mumbai (0.92) and Delhi (0.78)
        out1   = self.router.route_all(_MOCK_VARIANCE_RESULTS, _MOCK_PREDICTION_RESULTS)
        alerts1 = out1["civilian_alerts"]
        self.assertGreaterEqual(len(alerts1), 1, "At least 1 civilian alert should fire on first run")

        regions1 = {a["region"] for a in alerts1}
        self.assertIn("Mumbai", regions1)

        # Run 2: Immediately repeat → should suppress all alerts for Mumbai/Delhi
        out2   = self.router.route_all(_MOCK_VARIANCE_RESULTS, _MOCK_PREDICTION_RESULTS)
        alerts2 = out2["civilian_alerts"]
        self.assertEqual(len(alerts2), 0, "Second run within 24h must suppress duplicate civilian alerts")

    def test_civilian_privacy_no_entity_data(self):
        """
        Civilian alert content MUST contain generic regional guidance only.
        MUST NOT contain entity IDs (phone numbers, IP addresses, or account numbers).
        """
        out    = self.router.route_all(_MOCK_VARIANCE_RESULTS, _MOCK_PREDICTION_RESULTS)
        alerts = out["civilian_alerts"]

        for alert in alerts:
            text = alert["alert_text"]
            self.assertNotIn("9876543210", text, "Civilian alert leaked phone number!")
            self.assertNotIn("192.168.1.50", text, "Civilian alert leaked IP address!")
            self.assertNotIn("ACC-998877", text, "Civilian alert leaked account number!")
            self.assertNotIn("ACC-112233", text, "Civilian alert leaked account number!")


class TestAuthorityRouting(unittest.TestCase):

    def setUp(self):
        reset_delivery_audit_log()
        reset_appeals_manager()
        self.router = DeliveryRouter(regional_threshold=0.75)

    def test_authority_route_requires_human(self):
        """
        Phone and IP entities routed to Authority Queue MUST ALWAYS have:
          - recipient_type = "authority"
          - requires_human_review = True (never auto-actioned)
          - status = "pending_review"
          - tracking_id assigned
        """
        out   = self.router.route_all(_MOCK_VARIANCE_RESULTS, _MOCK_PREDICTION_RESULTS)
        queue = out["authority_queue"]

        self.assertEqual(len(queue), 2, "Expected 2 authority items (1 phone, 1 IP)")

        for item in queue:
            self.assertEqual(item["recipient_type"], "authority")
            self.assertTrue(item["requires_human_review"], "Authority items must mandate human review!")
            self.assertEqual(item["status"], "pending_review")
            self.assertTrue(item["tracking_id"].startswith("TRK-"))
            self.assertIn("signals_triggered", item)
            self.assertGreater(len(item["signals_triggered"]), 0)


class TestBankRouting(unittest.TestCase):

    def setUp(self):
        reset_delivery_audit_log()
        reset_appeals_manager()
        self.router = DeliveryRouter(regional_threshold=0.75)

    def test_bank_route_partitioning(self):
        """
        Bank Fraud Queue items MUST be cleanly partitioned by bank/institution name.
        HDFC Bank queue must ONLY contain HDFC accounts.
        State Bank of India queue must ONLY contain SBI accounts.
        """
        out   = self.router.route_all(_MOCK_VARIANCE_RESULTS, _MOCK_PREDICTION_RESULTS)
        bqueues = out["bank_queues"]

        self.assertIn("HDFC Bank", bqueues)
        self.assertIn("State Bank of India", bqueues)

        hdfc_items = bqueues["HDFC Bank"]
        self.assertEqual(len(hdfc_items), 1)
        self.assertEqual(hdfc_items[0]["entity_id"], "ACC-998877")

        sbi_items = bqueues["State Bank of India"]
        self.assertEqual(len(sbi_items), 1)
        self.assertEqual(sbi_items[0]["entity_id"], "ACC-112233")


class TestAppealsStateMachine(unittest.TestCase):

    def setUp(self):
        reset_delivery_audit_log()
        reset_appeals_manager()
        self.appeals_mgr = get_appeals_manager()

    def test_appeal_state_machine(self):
        """
        Register item → initial status 'pending_review'
        submit_appeal() → status transitions to 'appealed', dispute_reason recorded
        update_status('resolved') → status transitions to 'resolved'
        """
        item = self.appeals_mgr.register_item(
            recipient_type="authority",
            entity_id="9998887770",
            entity_type="phone",
            risk_level=0.89,
            region="Mumbai",
            signals_triggered=[],
            recommended_action="Manual Review Queue",
            requires_human_review=True,
        )

        tr_id = item["tracking_id"]
        self.assertEqual(item["status"], "pending_review")

        # Submit appeal / dispute
        updated = self.appeals_mgr.submit_appeal(
            tracking_id=tr_id,
            dispute_reason="Phone number belongs to legitimate corporate hotline.",
            advocate_name="Law Firm LLC",
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "appealed")
        self.assertEqual(updated["dispute_reason"], "Phone number belongs to legitimate corporate hotline.")

        # Senior reviewer resolves dispute
        resolved = self.appeals_mgr.update_status(
            tracking_id=tr_id,
            new_status="resolved",
            reviewer_id="SENIOR-INSPECTOR-01",
            notes="Appeal accepted — whitelisted corporate phone number.",
        )

        self.assertEqual(resolved["status"], "resolved")


class TestDeliveryAuditLogging(unittest.TestCase):

    def setUp(self):
        reset_delivery_audit_log()
        reset_appeals_manager()
        self.audit = get_delivery_audit_log()
        self.router = DeliveryRouter(regional_threshold=0.75)

    def test_delivery_audit_logging(self):
        """
        Routing actions and status updates must write structured log entries to DeliveryAuditLog.
        """
        self.router.route_all(_MOCK_VARIANCE_RESULTS, _MOCK_PREDICTION_RESULTS)
        entries = self.audit.get_all()

        self.assertGreater(len(entries), 0, "Audit log must contain routing entries")

        events_logged = {e["event"] for e in entries}
        self.assertIn("CIVILIAN_ALERT_ISSUED", events_logged)
        self.assertIn("REVIEW_ITEM_CREATED", events_logged)


class TestStatusPreservationAcrossRouting(unittest.TestCase):

    def setUp(self):
        reset_delivery_audit_log()
        reset_appeals_manager()
        self.appeals_mgr = get_appeals_manager()
        self.router = DeliveryRouter(regional_threshold=0.75)

    def test_status_preserved_across_multiple_routing_runs(self):
        """
        Verify that re-running router.route_all does not wipe out officer decisions
        or dispute filings (crucial for Streamlit UI reruns).
        """
        # Run 1: initial routing
        res1 = self.router.route_all(_MOCK_VARIANCE_RESULTS, _MOCK_PREDICTION_RESULTS)
        auth_items = res1["authority_queue"]
        self.assertGreater(len(auth_items), 0)

        target_trk = auth_items[0]["tracking_id"]
        self.assertEqual(auth_items[0]["status"], "pending_review")

        # Officer takes action on target_trk
        self.appeals_mgr.update_status(target_trk, "actioned", reviewer_id="OFFICER-1", notes="Blocked")
        self.assertEqual(self.appeals_mgr.get_item(target_trk)["status"], "actioned")

        # Run 2: repeat routing (as happens on Streamlit rerun)
        res2 = self.router.route_all(_MOCK_VARIANCE_RESULTS, _MOCK_PREDICTION_RESULTS)
        item_after_rerun = self.appeals_mgr.get_item(target_trk)

        # Status MUST still be "actioned", NOT reset to "pending_review"
        self.assertEqual(item_after_rerun["status"], "actioned")
        self.assertEqual(item_after_rerun["tracking_id"], target_trk)


if __name__ == "__main__":
    unittest.main()
