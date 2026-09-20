"""
cyber_portal/config.py
----------------------
Configuration and constants for the Privileged Cyber Portal (Port 8502).
"""

from __future__ import annotations
import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
LEDGER_FILE_PATH = os.environ.get("CYBER_PORTAL_LEDGER_PATH", str(BASE_DIR / "cyber_portal_audit_ledger.jsonl"))

# Network Config
PORTAL_PORT = 8502
ANALYST_PORT = 8501

# JWT Configuration
JWT_SECRET_KEY = os.environ.get("CYBER_PORTAL_JWT_SECRET", "pafcci-privileged-portal-secret-key-2026-sha256")
JWT_ALGORITHM = "HS256"
INGRESS_TOKEN_EXPIRE_MINUTES = 15
ROLE_TOKEN_EXPIRE_MINUTES = 30

# Rate Limiting & CAPTCHA Thresholds
MAX_FAILED_ATTEMPTS_BEFORE_CAPTCHA = 3
MAX_FAILED_ATTEMPTS_BEFORE_LOCKOUT = 5
LOCKOUT_DURATION_SECONDS = 300

# Pre-configured Departmental Users (Step 1 Ingress)
# TOTP secrets must be valid standard Base32 strings
DEPARTMENTAL_USERS = {
    "lea_officer": {
        "username": "lea_officer",
        "badge_id": "I4C-LEA-8901",
        "password_hash": "e10adc3949ba59abbe56e057f20f883e",  # md5('123456') for prototype
        "full_name": "Insp. Vikramaditya Rao",
        "department": "Indian Cyber Crime Coordination Centre (I4C)",
        "allowed_roles": ["LEA_OFFICER"],
        "totp_secret": "JBSWY3DPEHPK3PXP",  # standard base32
    },
    "bank_officer_sbi": {
        "username": "bank_officer_sbi",
        "badge_id": "SBI-FRD-4412",
        "password_hash": "e10adc3949ba59abbe56e057f20f883e",
        "full_name": "R. Ramanathan (Senior Vigilance)",
        "department": "State Bank of India — Fraud Monitoring Cell",
        "institution_id": "State Bank of India",
        "allowed_roles": ["BANK_OFFICER"],
        "totp_secret": "KVKFKRCPNZQUYMLX",
    },
    "bank_officer_hdfc": {
        "username": "bank_officer_hdfc",
        "badge_id": "HDFC-VIG-7731",
        "password_hash": "e10adc3949ba59abbe56e057f20f883e",
        "full_name": "Meera Sengupta (Fraud Risk)",
        "department": "HDFC Bank — Vigilance & Risk Control",
        "institution_id": "HDFC Bank",
        "allowed_roles": ["BANK_OFFICER"],
        "totp_secret": "MZXW6YTBOI2G64TQ",
    },
    "devops_engineer": {
        "username": "devops_engineer",
        "badge_id": "OPS-SYS-1092",
        "password_hash": "e10adc3949ba59abbe56e057f20f883e",
        "full_name": "T. Ananya (Platform SRE)",
        "department": "PAFCCI Platform Engineering & MLOps",
        "allowed_roles": ["DEVOPS"],
        "totp_secret": "NBSWY3DPEHPK3PXP",
    },
}

# Step 2 Role Step-Up Challenge Credentials (e.g. Departmental Security Keys / Warrant Tokens)
ROLE_CHALLENGE_KEYS = {
    "LEA_OFFICER": {
        "challenge_type": "Section 91 CrPC Authorisation Warrant Key",
        "valid_key": "SEC91-I4C-WARRANT-2026",
    },
    "BANK_OFFICER": {
        "challenge_type": "RBI Maker-Checker Dual Key / Branch Vigilance PIN",
        "valid_key": "RBI-VIG-DUALKEY-8877",
    },
    "DEVOPS": {
        "challenge_type": "MLOps Infrastructure Root Hardware Key",
        "valid_key": "SRE-ROOT-INFRA-4499",
    },
}
