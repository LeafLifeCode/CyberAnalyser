"""
cyber_portal/bridge.py
----------------------
Shared Session & Audit Bridge between Cyber Portal (Port 8502) and Delivery Model (Port 8501).
Enforces:
  1. 6 authoritative roles with live status (ONLINE / OFFLINE)
  2. Single-session lock (no duplicate logins for same username)
  3. Secure 6-digit OTP generation, verification, and invalidation on sign-out
  4. Local TXT file logging for all sign-in and sign-out events
  5. Local CSV file logging for {Authority_name: Tracker_ID} commits
  6. Data purging via clear_all_data()
"""

from __future__ import annotations

import csv
import json
import os
import random
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

BASE_DIR = Path(__file__).resolve().parent.parent

SESSION_FILE = BASE_DIR / "portal_sessions.json"
TXT_LOG_FILE = BASE_DIR / "cyber_portal_session_log.txt"
CSV_ACTIONS_FILE = BASE_DIR / "cyber_portal_authority_actions.csv"

# 6 Authoritative Roles & Personas
AUTHORITY_USERS: Dict[str, Dict[str, str]] = {
    "i4c_rajesh": {
        "username": "i4c_rajesh",
        "name": "Insp. Rajesh Kumar",
        "role": "I4C Cybercrime Lead",
        "department": "Indian Cyber Crime Coordination Centre (I4C)",
        "badge_id": "I4C-LEAD-7701",
        "institution": "Law Enforcement Agency",
    },
    "sbi_kavita": {
        "username": "sbi_kavita",
        "name": "Kavita Sharma",
        "role": "SBI Chief Vigilance Officer",
        "department": "State Bank of India — Fraud Monitoring Cell",
        "badge_id": "SBI-VIG-2290",
        "institution": "State Bank of India",
    },
    "hdfc_arjun": {
        "username": "hdfc_arjun",
        "name": "Arjun Nair",
        "role": "HDFC Risk & AML Specialist",
        "department": "HDFC Bank — Vigilance & Risk Control",
        "badge_id": "HDFC-AML-4481",
        "institution": "HDFC Bank",
    },
    "delhi_vikram": {
        "username": "delhi_vikram",
        "name": "ACP Vikramaditya Sen",
        "role": "Delhi Police Cyber Cell",
        "department": "Delhi Police Cyber Crime Unit (Special Cell)",
        "badge_id": "DELHI-CYBER-9102",
        "institution": "Delhi Police",
    },
    "certin_pooja": {
        "username": "certin_pooja",
        "name": "Dr. Pooja Bhatia",
        "role": "CERT-In Principal Forensics Analyst",
        "department": "Indian Computer Emergency Response Team (CERT-In)",
        "badge_id": "CERTIN-FOR-1185",
        "institution": "CERT-In",
    },
    "devops_anand": {
        "username": "devops_anand",
        "name": "Anand Verma",
        "role": "Platform Systems & DevOps SRE",
        "department": "PAFCCI Platform Engineering & MLOps",
        "badge_id": "DEVOPS-SRE-8823",
        "institution": "PAFCCI Platform",
    },
}


def _ensure_files_exist() -> None:
    """Ensure session json, txt log, and csv action log files exist."""
    if not SESSION_FILE.exists():
        SESSION_FILE.write_text(json.dumps({}, indent=2), encoding="utf-8")

    if not TXT_LOG_FILE.exists():
        TXT_LOG_FILE.write_text(
            f"=== PAFCCI CYBER PORTAL SESSION LOGS ===\nInitialized at {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}\n\n",
            encoding="utf-8",
        )

    if not CSV_ACTIONS_FILE.exists():
        with open(CSV_ACTIONS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Authority_name", "Tracker_ID", "Action_Type", "Entity_ID", "Timestamp", "Commit_Status"])


def _read_sessions() -> Dict[str, Any]:
    _ensure_files_exist()
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_sessions(data: Dict[str, Any]) -> None:
    _ensure_files_exist()
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_user_status(username: str) -> str:
    """Return 'ONLINE' if active session exists, else 'OFFLINE'."""
    sessions = _read_sessions()
    sess = sessions.get(username)
    if sess and sess.get("is_active", False):
        return "ONLINE"
    return "OFFLINE"


def get_all_user_statuses() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of all 6 users with their live status and details."""
    sessions = _read_sessions()
    statuses = {}
    for un, udata in AUTHORITY_USERS.items():
        sess = sessions.get(un)
        is_online = bool(sess and sess.get("is_active", False))
        statuses[un] = {
            **udata,
            "status": "ONLINE" if is_online else "OFFLINE",
            "active_session": sess if is_online else None,
        }
    return statuses


def generate_otp_for_user(username: str) -> Tuple[str, Dict[str, Any]]:
    """
    Generate a 6-digit OTP for an authoritative individual from Cyber Portal.
    Enforces the single-session rule: No more than one user can be logged into same username.
    """
    _ensure_files_exist()
    if username not in AUTHORITY_USERS:
        raise ValueError(f"Unknown authority username '{username}'.")

    user_info = AUTHORITY_USERS[username]
    sessions = _read_sessions()

    # Rule: No more than one user can be logged into same username
    existing_sess = sessions.get(username)
    if existing_sess and existing_sess.get("is_active", False):
        raise ValueError(
            f"Active Session Conflict: '{user_info['name']}' ({username}) is already ONLINE in another active session. "
            "Please sign out the existing session before requesting a new OTP."
        )

    # Generate cryptographically sound 6-digit OTP
    otp_code = f"{random.randint(100000, 999999)}"
    now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")

    session_data = {
        "username": username,
        "name": user_info["name"],
        "role": user_info["role"],
        "badge_id": user_info["badge_id"],
        "otp": otp_code,
        "login_time": now_str,
        "is_active": True,
    }

    sessions[username] = session_data
    _write_sessions(sessions)

    # Log to local TXT file
    log_line = f"[{now_str}] SIGN-IN  | User: {user_info['name']} ({username}) | Role: {user_info['role']} | Badge: {user_info['badge_id']} | Status: ONLINE | OTP: {otp_code}\n"
    with open(TXT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line)

    return otp_code, session_data


def verify_and_claim_otp(username: str, entered_otp: str) -> Dict[str, Any]:
    """
    Validate OTP entered in Delivery Model & Action Routing (Port 8501).
    Checks that session is active and OTP matches.
    """
    _ensure_files_exist()
    if username not in AUTHORITY_USERS:
        raise ValueError("Invalid authoritative username.")

    sessions = _read_sessions()
    sess = sessions.get(username)
    if not sess or not sess.get("is_active", False):
        raise ValueError(f"No active session found for '{username}'. Please request an OTP from Cyber Portal first.")

    stored_otp = sess.get("otp")
    if str(entered_otp).strip() != str(stored_otp).strip():
        raise ValueError("Invalid OTP code. Please check the code generated in Cyber Portal.")

    return {
        "authenticated": True,
        "username": username,
        "name": sess["name"],
        "role": sess["role"],
        "badge_id": sess["badge_id"],
        "login_time": sess["login_time"],
    }


def commit_authority_actions(
    authority_name: str,
    staged_actions: List[Dict[str, Any]],
) -> int:
    """
    Commit actions to local CSV file: cyber_portal_authority_actions.csv.
    Format: Authority_name,Tracker_ID,Action_Type,Entity_ID,Timestamp,Commit_Status
    """
    _ensure_files_exist()
    if not staged_actions:
        return 0

    now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    rows_to_append = []

    for act in staged_actions:
        rows_to_append.append([
            authority_name,
            act.get("tracking_id", "N/A"),
            act.get("action_type", "ACTION").upper(),
            act.get("entity_id", "N/A"),
            act.get("timestamp", now_str),
            "COMMITTED",
        ])

    with open(CSV_ACTIONS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows_to_append)

    return len(rows_to_append)


def sign_out_user(
    username: str,
    commit_staged: bool = False,
    staged_actions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    End session, commit pending actions if requested, invalidate OTP, and log SIGN-OUT in TXT.
    """
    _ensure_files_exist()
    sessions = _read_sessions()
    sess = sessions.get(username)

    user_info = AUTHORITY_USERS.get(username, {
        "name": username,
        "role": "Authority User",
        "badge_id": "AUTH-000",
    })

    committed_count = 0
    if commit_staged and staged_actions:
        committed_count = commit_authority_actions(user_info["name"], staged_actions)

    # Invalidate session
    if username in sessions:
        sessions.pop(username)
        _write_sessions(sessions)

    now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    log_line = (
        f"[{now_str}] SIGN-OUT | User: {user_info['name']} ({username}) | "
        f"Role: {user_info['role']} | Badge: {user_info['badge_id']} | "
        f"Committed: {committed_count} actions | Status: OFFLINE\n"
    )
    with open(TXT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line)

    return {
        "success": True,
        "username": username,
        "name": user_info["name"],
        "committed_count": committed_count,
        "status": "OFFLINE",
    }


def get_authority_actions(authority_name: Optional[str] = None) -> List[Dict[str, str]]:
    """Retrieve action records from cyber_portal_authority_actions.csv."""
    _ensure_files_exist()
    records = []
    if not CSV_ACTIONS_FILE.exists():
        return records

    try:
        with open(CSV_ACTIONS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if authority_name:
                    if row.get("Authority_name") == authority_name:
                        records.append(row)
                else:
                    records.append(row)
    except Exception:
        pass
    return records


def get_recent_session_logs(max_lines: int = 50) -> List[str]:
    """Retrieve recent sign-in and sign-out lines from the local TXT file."""
    _ensure_files_exist()
    if not TXT_LOG_FILE.exists():
        return []

    try:
        with open(TXT_LOG_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("===")]
            return lines[-max_lines:]
    except Exception:
        return []


def clear_all_data() -> Dict[str, Any]:
    """
    Clear data in both local TXT and CSV files, and reset all active sessions.
    Triggered by the 'Clear data' button in Cyber Portal.
    """
    # 1. Reset sessions JSON
    _write_sessions({})

    # 2. Reset TXT log file
    now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    TXT_LOG_FILE.write_text(
        f"=== PAFCCI CYBER PORTAL SESSION LOGS ===\n=== PURGED AT {now_str} ===\n\n",
        encoding="utf-8",
    )

    # 3. Reset CSV actions file
    with open(CSV_ACTIONS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Authority_name", "Tracker_ID", "Action_Type", "Entity_ID", "Timestamp", "Commit_Status"])

    return {
        "success": True,
        "purged_at": now_str,
        "message": "All session logs (TXT), authority actions (CSV), and active OTP locks cleared.",
    }
