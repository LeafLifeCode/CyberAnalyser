"""
tests/test_variance_engine.py
------------------------------
Unit Test Suite for the Risk Engine Variance Model.

Tests synthetic edge cases including:
  1. Legitimate flight traveler vs impossible proxy hop
  2. Legitimate regional VPN buffer (spatial tolerance)
  3. Genuine regular deposits vs massive cyber fraud deposit spike
  4. Stable SIM/IP binding vs rapid SIM swap / proxy rotation
  5. Multi-signal aggregation & evidence preservation
  6. Weekly time-series spike bucketing
"""

import unittest
from datetime import datetime, timezone, timedelta

from risk_engine.variance.signals import (
    haversine_distance_km,
    detect_ip_phone_mismatch,
    detect_deposit_spike,
    detect_ip_velocity,
)
from risk_engine.variance.aggregator import (
    aggregate_variance_signals,
    aggregate_weekly_spikes,
)
from risk_engine.variance.agent import run_variance_analysis


class TestVarianceEngineSignals(unittest.TestCase):

    def setUp(self):
        self.base_time = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)

    # ── 1. IP Velocity Tests ──────────────────────────────────────────────────

    def test_legitimate_traveler_flight(self):
        """
        Edge Case: Legitimate traveler taking a domestic flight from Delhi to Mumbai.
        Distance: ~1,150 km. Elapsed time: 3.0 hours.
        Speed: ~383 km/h (well below 900 km/h flight upper bound).
        Expected: NOT FLAGGED.
        """
        delhi_lat, delhi_lon = 28.6139, 77.2090
        mumbai_lat, mumbai_lon = 19.0760, 72.8777

        events = [
            {
                "attacker": {"active_ip": "184.100.1.1"},
                "atm": {"latitude": delhi_lat, "longitude": delhi_lon, "city": "Delhi", "state": "Delhi"},
                "generated_at": self.base_time.isoformat(),
            },
            {
                "attacker": {"active_ip": "184.100.1.1"},
                "atm": {"latitude": mumbai_lat, "longitude": mumbai_lon, "city": "Mumbai", "state": "Maharashtra"},
                "generated_at": (self.base_time + timedelta(hours=3.0)).isoformat(),
            },
        ]

        signals = detect_ip_velocity(events, max_speed_kmh=900.0, vpn_buffer_km=200.0)
        self.assertEqual(len(signals), 0, "Legitimate flight traveler should NOT be flagged.")

    def test_impossible_travel_proxy_hop(self):
        """
        Edge Case: Proxy hop from Delhi to Mumbai in 5 minutes (0.0833 hours).
        Distance: ~1,150 km.
        Speed: ~13,800 km/h (physically impossible).
        Expected: FLAGGED as ip_velocity anomaly.
        """
        delhi_lat, delhi_lon = 28.6139, 77.2090
        mumbai_lat, mumbai_lon = 19.0760, 72.8777

        events = [
            {
                "attacker": {"active_ip": "184.200.99.1"},
                "atm": {"latitude": delhi_lat, "longitude": delhi_lon, "city": "Delhi", "state": "Delhi"},
                "generated_at": self.base_time.isoformat(),
            },
            {
                "attacker": {"active_ip": "184.200.99.1"},
                "atm": {"latitude": mumbai_lat, "longitude": mumbai_lon, "city": "Mumbai", "state": "Maharashtra"},
                "generated_at": (self.base_time + timedelta(minutes=5)).isoformat(),
            },
        ]

        signals = detect_ip_velocity(events, max_speed_kmh=900.0, vpn_buffer_km=200.0)
        self.assertEqual(len(signals), 1, "Impossible proxy hop MUST be flagged.")

        sig = signals[0]
        self.assertEqual(sig["entity_id"], "184.200.99.1")
        self.assertEqual(sig["signal_type"], "ip_velocity")
        self.assertGreaterEqual(sig["sub_score"], 0.50)
        self.assertIn("calculated_speed_kmh", sig["evidence"])
        self.assertGreater(sig["evidence"]["calculated_speed_kmh"], 900.0)

    def test_legitimate_vpn_spatial_buffer(self):
        """
        Edge Case: Legitimate corporate VPN server switch between Mumbai and Pune (150 km) in 1 minute.
        Distance: 150 km (within the 200 km VPN buffer).
        Speed: 9,000 km/h (high due to 1-min time, but distance is within spatial buffer).
        Expected: NOT FLAGGED due to vpn_buffer_km=200.0 spatial tolerance.
        """
        mumbai_lat, mumbai_lon = 19.0760, 72.8777
        pune_lat, pune_lon = 18.5204, 73.8567

        events = [
            {
                "attacker": {"active_ip": "103.50.1.1"},
                "atm": {"latitude": mumbai_lat, "longitude": mumbai_lon, "city": "Mumbai", "state": "Maharashtra"},
                "generated_at": self.base_time.isoformat(),
            },
            {
                "attacker": {"active_ip": "103.50.1.1"},
                "atm": {"latitude": pune_lat, "longitude": pune_lon, "city": "Pune", "state": "Maharashtra"},
                "generated_at": (self.base_time + timedelta(minutes=1)).isoformat(),
            },
        ]

        signals = detect_ip_velocity(events, max_speed_kmh=900.0, vpn_buffer_km=200.0)
        self.assertEqual(len(signals), 0, "Spatial jump within VPN buffer (<=200km) should NOT be flagged.")

    # ── 2. Deposit Spike Tests ────────────────────────────────────────────────

    def test_genuine_regular_deposits(self):
        """
        Edge Case: Genuine account with steady salary/utility deposits around ₹10,000.
        Expected: NOT FLAGGED (z-score stays < 2.5).
        """
        events = []
        for i in range(5):
            t = self.base_time - timedelta(days=5 - i)
            events.append({
                "generated_at": t.isoformat(),
                "transactions": [
                    {
                        "txn_id": f"TXN-{i}",
                        "timestamp": t.isoformat(),
                        "txn_type": "UPI",
                        "sender_id": "VICTIM-1",
                        "receiver_id": "ACC-LEGIT-100",
                        "amount_inr": 10000.0 + (i * 200),
                        "bank_ifsc": "SBIN0001234",
                    }
                ],
                "mule_chain": [],
            })

        signals = detect_deposit_spike(events, baseline_days=7, z_threshold=2.5)
        self.assertEqual(len(signals), 0, "Regular steady deposits must NOT be flagged.")

    def test_cyber_fraud_deposit_spike(self):
        """
        Edge Case: Mule account with low ₹2,000 baseline transfers receives sudden ₹250,000 scam proceeds.
        Expected: FLAGGED as deposit_spike with z_score > 2.5.
        """
        events = []
        # Low baseline transfers
        for i in range(4):
            t = self.base_time - timedelta(days=4 - i)
            events.append({
                "generated_at": t.isoformat(),
                "transactions": [
                    {
                        "txn_id": f"TXN-BASE-{i}",
                        "timestamp": t.isoformat(),
                        "txn_type": "UPI",
                        "sender_id": "MULE-PREV",
                        "receiver_id": "ACC-MULE-999",
                        "amount_inr": 2000.0,
                        "bank_ifsc": "HDFC0009999",
                    }
                ],
                "mule_chain": [],
            })

        # Sudden massive scam deposit
        events.append({
            "generated_at": self.base_time.isoformat(),
            "transactions": [
                {
                    "txn_id": "TXN-SCAM-SPIKE",
                    "timestamp": self.base_time.isoformat(),
                    "txn_type": "IMPS",
                    "sender_id": "VICTIM-SCAMMED",
                    "receiver_id": "ACC-MULE-999",
                    "amount_inr": 250000.0,
                    "bank_ifsc": "HDFC0009999",
                }
            ],
            "mule_chain": [],
        })

        signals = detect_deposit_spike(events, baseline_days=7, z_threshold=2.5)
        self.assertEqual(len(signals), 1, "Massive fraud deposit spike MUST be flagged.")

        sig = signals[0]
        self.assertEqual(sig["entity_id"], "ACC-MULE-999")
        self.assertEqual(sig["signal_type"], "deposit_spike")
        self.assertGreaterEqual(sig["evidence"]["z_score"], 2.5)
        self.assertEqual(sig["evidence"]["max_single_deposit_inr"], 250000.0)

    # ── 3. IP-Phone Mismatch Tests ────────────────────────────────────────────

    def test_legitimate_single_phone_stable_ips(self):
        """
        Edge Case: Legitimate phone operating across 2 IPs over 24h (home Wi-Fi and 5G cellular).
        Expected: NOT FLAGGED (threshold is > 2).
        """
        events = [
            {
                "generated_at": self.base_time.isoformat(),
                "attacker": {"active_phone": "+91-9876543210", "active_ip": "49.200.1.1", "vpn_provider": "Unknown"},
            },
            {
                "generated_at": (self.base_time + timedelta(hours=4)).isoformat(),
                "attacker": {"active_phone": "+91-9876543210", "active_ip": "49.200.1.2", "vpn_provider": "Unknown"},
            },
        ]

        signals = detect_ip_phone_mismatch(events, time_window_hours=24.0, max_allowed_ips_per_phone=2)
        self.assertEqual(len(signals), 0, "Stable 2-IP usage for a phone must NOT be flagged.")

    def test_sim_swap_proxy_rotation(self):
        """
        Edge Case: Cybercrime syndicate phone rotating across 5 distinct VPN IPs in 24 hours.
        Expected: FLAGGED as ip_phone_mismatch.
        """
        events = []
        for i in range(5):
            t = self.base_time + timedelta(hours=i * 2)
            events.append({
                "generated_at": t.isoformat(),
                "attacker": {
                    "active_phone": "+91-9999900000",
                    "active_ip": f"103.10.{i}.50",
                    "vpn_provider": "ExpressVPN",
                },
            })

        signals = detect_ip_phone_mismatch(events, time_window_hours=24.0, max_allowed_ips_per_phone=2)
        self.assertGreaterEqual(len(signals), 1, "Phone with 5 rotating IPs MUST be flagged.")

        phone_sig = next(s for s in signals if s["entity_id"] == "+91-9999900000")
        self.assertEqual(phone_sig["entity_type"], "phone")
        self.assertEqual(phone_sig["evidence"]["distinct_ip_count"], 5)

    # ── 4. Multi-Signal Aggregation & Evidence Tests ──────────────────────────

    def test_multi_signal_aggregation_preserves_evidence(self):
        """
        Tests combining multiple independent signals for the same entity.
        Ensures evidence dicts and signal_names are fully preserved.
        """
        raw_signals = [
            {
                "entity_id": "184.200.99.1",
                "entity_type": "ip",
                "signal_type": "ip_velocity",
                "sub_score": 0.80,
                "window_start": self.base_time.isoformat(),
                "window_end": (self.base_time + timedelta(hours=1)).isoformat(),
                "evidence": {
                    "reason": "Impossible travel speed",
                    "calculated_speed_kmh": 5000.0,
                    "max_allowed_speed_kmh": 900.0,
                },
            },
            {
                "entity_id": "184.200.99.1",
                "entity_type": "ip",
                "signal_type": "ip_phone_mismatch",
                "sub_score": 0.70,
                "window_start": self.base_time.isoformat(),
                "window_end": (self.base_time + timedelta(hours=1)).isoformat(),
                "evidence": {
                    "reason": "IP bound to 4 distinct phones",
                    "distinct_ip_count": 4,
                    "max_allowed_ips": 3,
                },
            },
        ]

        aggregated = aggregate_variance_signals(raw_signals)
        self.assertEqual(len(aggregated), 1)

        rec = aggregated[0]
        self.assertEqual(rec["entity_id"], "184.200.99.1")
        self.assertEqual(rec["distinct_signals_count"], 2)
        # Combined score: 1 - (1 - 0.80)*(1 - 0.70) = 1 - 0.20*0.30 = 0.94
        self.assertEqual(rec["combined_score"], 0.94)
        # Confidence: evidence-strength-based (not flat 0.88).
        # ip_velocity at 5000 km/h: 0.60 + (5000-900)/9100 * 0.38 ≈ 0.771
        # ip_phone_mismatch with 4 IPs: 0.60 + (4-2)/8 * 0.38 ≈ 0.695
        # base_conf = max(0.771, 0.695) = 0.771; 2-signal boost +0.04 → 0.811
        self.assertGreater(rec["confidence"], 0.70, "Multi-signal confidence should exceed single-signal 0.70")
        self.assertLess(rec["confidence"], 1.0, "Confidence must not exceed 1.0")
        self.assertEqual(len(rec["signals_triggered"]), 2)
        # Assert evidence preserved
        sig_types = [s["signal_type"] for s in rec["signals_triggered"]]
        self.assertIn("ip_velocity", sig_types)
        self.assertIn("ip_phone_mismatch", sig_types)

    # ── 5. Time-Series Weekly Bucketing Tests ─────────────────────────────────

    def test_weekly_spikes_bucketing(self):
        """
        Tests grouping flagged entity events into ISO calendar weeks for time-series charting.
        """
        week1_date = "2026-09-07T10:00:00+00:00"  # ISO Week 37
        week2_date = "2026-09-14T10:00:00+00:00"  # ISO Week 38

        flagged_records = [
            {
                "entity_id": "ACC-MULE-1",
                "entity_type": "account",
                "combined_score": 0.85,
                "timestamp": week1_date,
                "signal_names": ["deposit_spike"],
            },
            {
                "entity_id": "ACC-MULE-1",
                "entity_type": "account",
                "combined_score": 0.92,
                "timestamp": week1_date,
                "signal_names": ["ip_phone_mismatch"],
            },
            {
                "entity_id": "ACC-MULE-1",
                "entity_type": "account",
                "combined_score": 0.75,
                "timestamp": week2_date,
                "signal_names": ["deposit_spike"],
            },
        ]

        weekly = aggregate_weekly_spikes(flagged_records)
        self.assertEqual(len(weekly), 2, "Should create 2 weekly buckets.")

        w1_bucket = next(b for b in weekly if b["entity_id"] == "ACC-MULE-1" and "2026-09-07" in b["monday_date"])
        self.assertEqual(w1_bucket["flag_count"], 2)
        self.assertEqual(w1_bucket["max_score"], 0.92)
        self.assertIn("deposit_spike", w1_bucket["signals_triggered"])
        self.assertIn("ip_phone_mismatch", w1_bucket["signals_triggered"])

    # ── 6. Full Variance Engine Pipeline Test ──────────────────────────────────

    def test_full_variance_analysis_pipeline(self):
        """
        Tests high-level run_variance_analysis function on synthetic complaint events.
        """
        events = [
            {
                "generated_at": self.base_time.isoformat(),
                "attacker": {
                    "active_phone": "+91-9988776655",
                    "active_ip": "203.0.113.5",
                    "vpn_provider": "Tor Exit",
                },
                "transactions": [
                    {
                        "txn_id": "TXN-TEST-1",
                        "timestamp": self.base_time.isoformat(),
                        "txn_type": "UPI",
                        "sender_id": "VICTIM-101",
                        "receiver_id": "ACC-SUSPECT-77",
                        "amount_inr": 180000.0,
                        "bank_ifsc": "SBIN0001111",
                    }
                ],
                "mule_chain": [],
                "atm": {"latitude": 28.6139, "longitude": 77.2090, "city": "Delhi", "state": "Delhi"},
            }
        ]

        result = run_variance_analysis(events, use_llm=False)
        self.assertIn("summary_stats", result)
        self.assertIn("aggregated_entities", result)
        self.assertIn("weekly_spikes", result)
        self.assertEqual(result["summary_stats"]["total_events_analyzed"], 1)


if __name__ == "__main__":
    unittest.main()