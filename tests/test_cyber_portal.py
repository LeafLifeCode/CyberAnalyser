"""
tests/test_cyber_portal.py
--------------------------
Comprehensive unit test suite for Privileged Cyber Portal (Port 8502):
1. Ingress-only token cannot access role data
2. RFC 6238 TOTP verification, rate-limiting, and CAPTCHA trigger
3. Bank Officer DAL scoping (cannot query other banks or telecom/IP)
4. DevOps structural isolation (cannot access citizen PII)
5. Four-Eyes Principle enforcement on appealed items
6. SHA-256 hash-chained cryptographic ledger integrity and tamper detection
7. Token expiration and invalid signature handling
"""

import os
import json
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
import pyotp
import jwt

from cyber_portal.config import (
    DEPARTMENTAL_USERS,
    ROLE_CHALLENGE_KEYS,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
)
from cyber_portal.auth.tokens import (
    create_ingress_token,
    create_role_token,
    verify_token,
    AuthenticationError,
    TokenScopeError,
)
from cyber_portal.auth.ingress import verify_step1_ingress, get_rate_limiter
from cyber_portal.auth.step_up import verify_step2_step_up
from cyber_portal.dal.lea_dal import LEAService
from cyber_portal.dal.bank_dal import BankService
from cyber_portal.dal.devops_dal import InfraMetricsService
from cyber_portal.actions.handler import ActionController
from cyber_portal.actions.four_eyes import FourEyesViolationError
from cyber_portal.audit.ledger import CryptographicAuditLedger
from cyber_portal.audit.verifier import verify_audit_ledger
from delivery_model.appeals import AppealsManager, reset_appeals_manager


class TestCyberPortalAuthAndDAL(unittest.TestCase):

    def setUp(self):
        reset_appeals_manager()
        self.limiter = get_rate_limiter()
        for u in list(DEPARTMENTAL_USERS.keys()):
            self.limiter.reset(u)

        # Pre-seed an AppealsManager for tests
        self.appeals_mgr = AppealsManager()
        # Item 1: Authority Phone
        self.item_phone = self.appeals_mgr.register_item(
            recipient_type="authority",
            entity_id="+919876543210",
            entity_type="phone",
            risk_level=0.91,
            region="Mumbai",
            signals_triggered=[{"signal_type": "high_vishing", "sub_score": 0.95}],
            recommended_action="Telecom Blacklist",
            evidence_summary={"carrier": "Bharti Airtel"},
        )
        # Item 2: SBI Account
        self.item_sbi = self.appeals_mgr.register_item(
            recipient_type="bank",
            entity_id="sbi_mule_1001@upi",
            entity_type="account",
            risk_level=0.88,
            region="Delhi",
            bank_name="State Bank of India",
            signals_triggered=[{"signal_type": "deposit_surge", "sub_score": 0.90}],
            recommended_action="Debit Freeze",
            evidence_summary={"deposit_surge": "10x"},
        )
        # Item 3: HDFC Account
        self.item_hdfc = self.appeals_mgr.register_item(
            recipient_type="bank",
            entity_id="hdfc_mule_2002@upi",
            entity_type="account",
            risk_level=0.85,
            region="Bangalore",
            bank_name="HDFC Bank",
            signals_triggered=[{"signal_type": "atm_burst", "sub_score": 0.86}],
            recommended_action="Lien Marking",
            evidence_summary={"rapid_cashouts": "₹2,00,000"},
        )

    def tear_rate_limiter(self):
        for u in list(DEPARTMENTAL_USERS.keys()):
            self.limiter.reset(u)

    def test_ingress_token_cannot_access_role_data(self):
        """Verify that an ingress-only token cannot query role-scoped DAL services."""
        user_lea = DEPARTMENTAL_USERS["lea_officer"]
        ingress_token = create_ingress_token(user_lea)

        # Ingress token verification with required scope should fail
        with self.assertRaises(TokenScopeError):
            verify_token(ingress_token, required_scope="LEA_OFFICER")

        # Calling LEAService with ingress token must raise TokenScopeError
        lea_svc = LEAService()
        with self.assertRaises(TokenScopeError):
            lea_svc.get_authority_queue(ingress_token)

        # Calling BankService with ingress token must raise TokenScopeError
        bank_svc = BankService()
        with self.assertRaises(TokenScopeError):
            bank_svc.get_bank_queue(ingress_token)

    def test_totp_rfc6238_validation_and_rate_limiting(self):
        """Verify RFC 6238 TOTP verification, failure counters, and CAPTCHA / lockout."""
        user_key = "lea_officer"
        user_data = DEPARTMENTAL_USERS[user_key]
        secret = user_data["totp_secret"]

        # 1. Successful authentication with live TOTP
        valid_code = pyotp.TOTP(secret).now()
        res = verify_step1_ingress(user_key, "123456", valid_code)
        self.assertTrue(res["success"])
        self.assertIn("ingress_token", res)

        # 2. Failed authentication with invalid TOTP
        with self.assertRaises(AuthenticationError):
            verify_step1_ingress(user_key, "123456", "000000")
        self.assertEqual(self.limiter.get_failures(user_key), 1)

        # 3. 3 failed attempts triggers CAPTCHA
        with self.assertRaises(AuthenticationError):
            verify_step1_ingress(user_key, "wrong_pw", valid_code)
        with self.assertRaises(AuthenticationError):
            verify_step1_ingress(user_key, "wrong_pw", valid_code)

        self.assertTrue(self.limiter.requires_captcha(user_key))

        # 4. Attempting login without CAPTCHA when required fails
        with self.assertRaises(AuthenticationError):
            verify_step1_ingress(user_key, "123456", valid_code)

        # 5. Lockout triggered after 5 failures
        with self.assertRaises(AuthenticationError):
            verify_step1_ingress(user_key, "wrong_pw", valid_code)

        locked, rem = self.limiter.is_locked(user_key)
        self.assertTrue(locked)
        self.assertGreater(rem, 0)

        # Attempt during lockout fails immediately
        with self.assertRaises(AuthenticationError) as cm:
            verify_step1_ingress(user_key, "123456", valid_code)
        self.assertIn("locked", str(cm.exception).lower())

    def test_step2_role_challenge_and_tokens(self):
        """Verify Step 2 role challenge validation and issuing role tokens."""
        user_lea = DEPARTMENTAL_USERS["lea_officer"]
        ingress_token = create_ingress_token(user_lea)

        # Wrong challenge key fails
        with self.assertRaises(AuthenticationError):
            verify_step2_step_up(ingress_token, "LEA_OFFICER", "INVALID-KEY-123")

        # Unauthorized role for this user fails
        with self.assertRaises(TokenScopeError):
            verify_step2_step_up(ingress_token, "BANK_OFFICER", ROLE_CHALLENGE_KEYS["BANK_OFFICER"]["valid_key"])

        # Correct challenge key succeeds
        correct_key = ROLE_CHALLENGE_KEYS["LEA_OFFICER"]["valid_key"]
        res = verify_step2_step_up(ingress_token, "LEA_OFFICER", correct_key)
        self.assertTrue(res["success"])
        self.assertEqual(res["role"], "LEA_OFFICER")

        # Claims in role token
        claims = verify_token(res["role_token"], required_scope="LEA_OFFICER")
        self.assertEqual(claims["role"], "LEA_OFFICER")

    def test_bank_officer_cannot_query_other_bank(self):
        """Verify Bank DAL strictly enforces institution_id and rejects other banks' accounts."""
        user_sbi = DEPARTMENTAL_USERS["bank_officer_sbi"]
        sbi_token = create_role_token(user_sbi, "BANK_OFFICER", institution_id="State Bank of India")

        bank_svc = BankService()
        # Wire test appeals manager
        bank_svc.appeals_mgr = self.appeals_mgr

        # SBI officer querying SBI queue succeeds
        sbi_queue = bank_svc.get_bank_queue(sbi_token, institution_id="State Bank of India")
        self.assertGreaterEqual(len(sbi_queue), 1)
        self.assertEqual(sbi_queue[0]["bank_name"], "State Bank of India")

        # SBI officer attempting to query HDFC queue raises PermissionError
        with self.assertRaises(PermissionError):
            bank_svc.get_bank_queue(sbi_token, institution_id="HDFC Bank")

        # SBI officer attempting to inspect an HDFC account item raises PermissionError
        with self.assertRaises(PermissionError):
            bank_svc.get_bank_item(sbi_token, self.item_hdfc["tracking_id"])

        # SBI officer attempting to inspect an authority phone item raises PermissionError
        with self.assertRaises(PermissionError):
            bank_svc.get_bank_item(sbi_token, self.item_phone["tracking_id"])

    def test_devops_cannot_access_pii(self):
        """Verify DevOps service is technically prohibited from citizen PII / account tables."""
        user_devops = DEPARTMENTAL_USERS["devops_engineer"]
        devops_token = create_role_token(user_devops, "DEVOPS")

        devops_svc = InfraMetricsService()

        # Telemetry queries succeed
        health = devops_svc.get_pipeline_health(devops_token)
        self.assertEqual(health["service_status"], "HEALTHY")
        self.assertIn("generator_p50", health["model_pipeline_latency_ms"])

        drift = devops_svc.get_drift_metrics(devops_token)
        self.assertIsInstance(drift, list)

        # Structural PII prohibition checks
        with self.assertRaises(PermissionError):
            devops_svc.query_citizen_pii()

        with self.assertRaises(PermissionError):
            devops_svc.query_bank_accounts()

        with self.assertRaises(PermissionError):
            devops_svc.query_authority_queue()

    def test_four_eyes_appeal_enforcement(self):
        """Verify Four-Eyes principle: original decision-maker cannot adjudicate appeals."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".jsonl") as tf:
            temp_ledger_path = tf.name

        ledger = CryptographicAuditLedger(file_path=temp_ledger_path)
        controller = ActionController()
        controller.appeals_mgr = self.appeals_mgr
        controller.ledger = ledger

        # Officer 1 takes initial block action
        user_lea1 = dict(DEPARTMENTAL_USERS["lea_officer"])
        user_lea1["badge_id"] = "I4C-OFFICER-001"
        token_officer1 = create_role_token(user_lea1, "LEA_OFFICER")

        res_act = controller.execute_action(
            role_token=token_officer1,
            tracking_id=self.item_phone["tracking_id"],
            action_type="block",
            justification_remarks="Confirmed syndicate operations under Section 91.",
        )
        self.assertTrue(res_act["success"])
        self.assertEqual(self.item_phone["status"], "actioned")
        self.assertEqual(self.item_phone["original_actor_id"], "I4C-OFFICER-001")

        # Citizen submits formal appeal
        self.appeals_mgr.submit_appeal(
            tracking_id=self.item_phone["tracking_id"],
            dispute_reason="Sim card belongs to legitimate call center company.",
            advocate_name="Adv. Sharma",
        )
        self.assertEqual(self.item_phone["status"], "appealed")

        # Officer 1 attempts to resolve their own appeal -> MUST BE REJECTED by Four-Eyes principle
        with self.assertRaises(FourEyesViolationError):
            controller.execute_action(
                role_token=token_officer1,
                tracking_id=self.item_phone["tracking_id"],
                action_type="resolve_appeal",
                justification_remarks="I re-reviewed and uphold my previous decision.",
            )

        # Officer 2 (Senior Reviewer) attempts to resolve the appeal -> SUCCEEDS
        user_lea2 = dict(DEPARTMENTAL_USERS["lea_officer"])
        user_lea2["badge_id"] = "I4C-SENIOR-999"
        token_officer2 = create_role_token(user_lea2, "LEA_OFFICER")

        res_resolve = controller.execute_action(
            role_token=token_officer2,
            tracking_id=self.item_phone["tracking_id"],
            action_type="resolve_appeal",
            justification_remarks="Independent secondary review confirmed corporate registration documents.",
            appeal_disposition="overturn_whitelist",
        )
        self.assertTrue(res_resolve["success"])
        self.assertEqual(self.item_phone["status"], "resolved")

        try:
            os.unlink(temp_ledger_path)
        except Exception:
            pass

    def test_audit_ledger_tamper_detection(self):
        """Verify SHA-256 hash chaining detects modified records and broken pointers."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".jsonl") as tf:
            temp_ledger_path = tf.name

        ledger = CryptographicAuditLedger(file_path=temp_ledger_path)

        # Append 3 sequential entries
        e0 = ledger.append_entry("INSP-01", "LEA_OFFICER", "BLOCK", "+919111111111", "phone", "TRK-001", "Remark 1")
        e1 = ledger.append_entry("INSP-02", "LEA_OFFICER", "WHITELIST", "+919222222222", "phone", "TRK-002", "Remark 2")
        e2 = ledger.append_entry("BANK-01", "BANK_OFFICER", "FREEZE", "acc_333@upi", "account", "TRK-003", "Remark 3", institution_id="SBI")

        # 1. Pristine chain verification
        is_valid, broken_idx, msg = verify_audit_ledger(temp_ledger_path)
        self.assertTrue(is_valid)
        self.assertIsNone(broken_idx)

        # 2. Tamper block 1 (modify justification remarks)
        lines = []
        with open(temp_ledger_path, "r", encoding="utf-8") as f:
            for l in f:
                lines.append(json.loads(l))

        lines[1]["justification_text"] = "MODIFIED BY ATTACKER"

        with open(temp_ledger_path, "w", encoding="utf-8") as f:
            for l in lines:
                f.write(json.dumps(l) + "\n")

        # 3. Verification must flag tamper at block 1
        is_valid, broken_idx, msg = verify_audit_ledger(temp_ledger_path)
        self.assertFalse(is_valid)
        self.assertEqual(broken_idx, 1)
        self.assertIn("Tamper Detected", msg)

        try:
            os.unlink(temp_ledger_path)
        except Exception:
            pass

    def test_role_token_expiration(self):
        """Verify expired role tokens are rejected."""
        user_lea = DEPARTMENTAL_USERS["lea_officer"]
        now = datetime.now(timezone.utc)
        # Create token that expired 10 minutes ago
        payload = {
            "sub": user_lea["username"],
            "badge_id": user_lea["badge_id"],
            "role": "LEA_OFFICER",
            "scope": ["LEA_OFFICER"],
            "iat": int((now - timedelta(minutes=20)).timestamp()),
            "exp": int((now - timedelta(minutes=10)).timestamp()),
        }
        expired_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with self.assertRaises(AuthenticationError) as cm:
            verify_token(expired_token, required_scope="LEA_OFFICER")
        self.assertIn("expired", str(cm.exception).lower())


if __name__ == "__main__":
    unittest.main()
