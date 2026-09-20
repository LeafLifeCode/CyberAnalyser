"""
tests/test_cyber_portal_bridge.py
---------------------------------
Unit tests for Cyber Portal OTP Dispatcher, Cross-Process Session Bridge,
6 Authoritative Roles, Single-Session Lock, TXT/CSV Logging, and Data Purge.
"""

import os
import unittest
from pathlib import Path

from cyber_portal.bridge import (
    AUTHORITY_USERS,
    generate_otp_for_user,
    verify_and_claim_otp,
    commit_authority_actions,
    sign_out_user,
    get_user_status,
    get_all_user_statuses,
    get_authority_actions,
    get_recent_session_logs,
    clear_all_data,
    TXT_LOG_FILE,
    CSV_ACTIONS_FILE,
)


class TestCyberPortalBridge(unittest.TestCase):

    def setUp(self):
        clear_all_data()

    def tearDown(self):
        clear_all_data()

    def test_6_roles_defined(self):
        """Verify all 6 authoritative roles and personas are properly configured."""
        self.assertEqual(len(AUTHORITY_USERS), 6)
        expected_keys = {
            "i4c_rajesh",
            "sbi_kavita",
            "hdfc_arjun",
            "delhi_vikram",
            "certin_pooja",
            "devops_anand",
        }
        self.assertEqual(set(AUTHORITY_USERS.keys()), expected_keys)

        # Check fields in each persona
        for k, u in AUTHORITY_USERS.items():
            self.assertIn("username", u)
            self.assertIn("name", u)
            self.assertIn("role", u)
            self.assertIn("badge_id", u)
            self.assertIn("department", u)

    def test_default_status_is_offline(self):
        """Verify that all users default to OFFLINE before any OTP is generated."""
        statuses = get_all_user_statuses()
        for k, u in statuses.items():
            self.assertEqual(u["status"], "OFFLINE")
            self.assertEqual(get_user_status(k), "OFFLINE")

    def test_otp_generation_and_status_online(self):
        """Verify OTP generation transitions user to ONLINE and logs SIGN-IN to TXT."""
        username = "i4c_rajesh"
        otp, sess = generate_otp_for_user(username)

        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())
        self.assertEqual(get_user_status(username), "ONLINE")

        statuses = get_all_user_statuses()
        self.assertEqual(statuses[username]["status"], "ONLINE")
        self.assertEqual(statuses[username]["active_session"]["otp"], otp)

        # Check TXT log has recorded SIGN-IN
        logs = get_recent_session_logs(10)
        self.assertTrue(any("SIGN-IN" in l and username in l and otp in l for l in logs))

    def test_single_session_lock(self):
        """Rule: No more than one user can be logged into same username."""
        username = "sbi_kavita"
        generate_otp_for_user(username)

        # Second attempt while still online must raise ValueError
        with self.assertRaises(ValueError) as cm:
            generate_otp_for_user(username)
        self.assertIn("Active Session Conflict", str(cm.exception))

    def test_verify_otp_valid_and_invalid(self):
        """Verify OTP validation in Delivery Model."""
        username = "hdfc_arjun"
        otp, _ = generate_otp_for_user(username)

        # 1. Invalid OTP fails
        with self.assertRaises(ValueError) as cm:
            verify_and_claim_otp(username, "000000")
        self.assertIn("Invalid OTP", str(cm.exception))

        # 2. Valid OTP succeeds
        res = verify_and_claim_otp(username, otp)
        self.assertTrue(res["authenticated"])
        self.assertEqual(res["username"], username)
        self.assertEqual(res["name"], AUTHORITY_USERS[username]["name"])

    def test_commit_actions_writes_csv(self):
        """Verify actions are logged into local CSV as {Authority_name: Tracker_ID}."""
        officer_name = "ACP Vikramaditya Sen"
        staged = [
            {"tracking_id": "TRK-A11111", "action_type": "BLOCK", "entity_id": "+919876543210"},
            {"tracking_id": "TRK-B22222", "action_type": "WHITELIST", "entity_id": "103.21.244.15"},
        ]

        count = commit_authority_actions(officer_name, staged)
        self.assertEqual(count, 2)

        # Read back from CSV
        actions = get_authority_actions(authority_name=officer_name)
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["Authority_name"], officer_name)
        self.assertEqual(actions[0]["Tracker_ID"], "TRK-A11111")
        self.assertEqual(actions[0]["Action_Type"], "BLOCK")
        self.assertEqual(actions[1]["Tracker_ID"], "TRK-B22222")

    def test_sign_out_user_with_commit_and_without(self):
        """Verify sign out invalidates OTP, updates status to OFFLINE, and logs to TXT."""
        username = "certin_pooja"
        otp, _ = generate_otp_for_user(username)
        self.assertEqual(get_user_status(username), "ONLINE")

        staged = [
            {"tracking_id": "TRK-C33333", "action_type": "DEBIT_FREEZE", "entity_id": "mule@upi"}
        ]

        # Sign out with commit_staged=True
        res = sign_out_user(username, commit_staged=True, staged_actions=staged)
        self.assertTrue(res["success"])
        self.assertEqual(res["committed_count"], 1)
        self.assertEqual(get_user_status(username), "OFFLINE")

        # OTP is now invalid
        with self.assertRaises(ValueError):
            verify_and_claim_otp(username, otp)

        # Check CSV has the committed action
        acts = get_authority_actions(authority_name=AUTHORITY_USERS[username]["name"])
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0]["Tracker_ID"], "TRK-C33333")

        # Check TXT log has SIGN-OUT
        logs = get_recent_session_logs(10)
        self.assertTrue(any("SIGN-OUT" in l and username in l for l in logs))

    def test_clear_all_data(self):
        """Verify clear_all_data purges TXT and CSV logs and resets sessions."""
        username = "devops_anand"
        generate_otp_for_user(username)
        commit_authority_actions("Anand Verma", [{"tracking_id": "TRK-D44444", "action_type": "DISMISS"}])

        self.assertEqual(get_user_status(username), "ONLINE")
        self.assertGreater(len(get_authority_actions()), 0)

        # Call clear_all_data
        res = clear_all_data()
        self.assertTrue(res["success"])

        # Check status is OFFLINE
        self.assertEqual(get_user_status(username), "OFFLINE")
        # Check CSV is empty
        self.assertEqual(len(get_authority_actions()), 0)
        # Check TXT is cleared
        logs = get_recent_session_logs()
        self.assertEqual(len(logs), 0)


if __name__ == "__main__":
    unittest.main()
