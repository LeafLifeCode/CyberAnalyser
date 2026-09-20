"""
generator/tools/transaction_tools.py
--------------------------------------
CrewAI @tool functions for simulating victim-to-attacker transactions.
"""

import json
import random
import uuid
from datetime import datetime, timedelta

from crewai.tools import tool

_TXN_TYPES = ["UPI", "IMPS", "NEFT", "RTGS", "Card"]
_IFSC_PREFIXES = ["SBIN", "HDFC", "ICIC", "UTIB", "PUNB", "BARB", "CNRB", "KKBK"]
_VICTIM_STATES = [
    "Maharashtra", "Tamil Nadu", "Karnataka", "Gujarat", "West Bengal",
    "Andhra Pradesh", "Telangana", "Kerala", "Punjab", "Haryana",
    "Delhi", "Rajasthan", "Uttar Pradesh", "Odisha", "Assam",
]


def _gen_vpa() -> str:
    name = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=6))
    bank = random.choice(["okaxis", "paytm", "ybl", "okicici", "upi"])
    return f"{name}@{bank}"


def _gen_ifsc() -> str:
    prefix = random.choice(_IFSC_PREFIXES)
    return f"{prefix}0{random.randint(100000, 999999)}"


def _gen_amount(mean: float, variance: float) -> float:
    std = mean * variance
    amount = random.gauss(mean, std)
    return round(max(500.0, amount), 2)


@tool("Generate Victim Transactions")
def generate_transactions(
    attacker_profiles_json: str,
    amount_mean_inr: float,
    amount_variance: float,
    frequency_before_atm: int,
    reference_timestamp: str,
) -> str:
    """
    Generate synthetic transaction sequences from victims to attacker accounts.

    Args:
        attacker_profiles_json: JSON list of attacker profiles (from generate_attacker_profile).
        amount_mean_inr: Mean transaction amount in INR.
        amount_variance: Std-dev fraction of mean (e.g. 0.30).
        frequency_before_atm: Number of transactions before final ATM withdrawal.
        reference_timestamp: ISO-format datetime string representing cycle start time.

    Returns:
        JSON string — list of {attacker_id, victim_state, transactions[]}.
    """
    profiles = json.loads(attacker_profiles_json)
    ref_dt = datetime.fromisoformat(reference_timestamp)
    results = []

    for profile in profiles:
        victim_state = random.choice(_VICTIM_STATES)
        victim_vpa   = _gen_vpa()
        attacker_vpa = _gen_vpa()

        txns = []
        t = ref_dt - timedelta(minutes=random.randint(20, 180))   # fraud happened before report

        for k in range(frequency_before_atm):
            amount = _gen_amount(amount_mean_inr / frequency_before_atm, amount_variance)
            txns.append({
                "txn_id":      f"TXN-{uuid.uuid4().hex[:8].upper()}",
                "timestamp":   (t + timedelta(minutes=k * random.randint(1, 15))).isoformat(),
                "txn_type":    random.choice(_TXN_TYPES),
                "sender_id":   victim_vpa,
                "receiver_id": attacker_vpa,
                "amount_inr":  amount,
                "bank_ifsc":   _gen_ifsc(),
            })

        results.append({
            "attacker_id":  profile["attacker_id"],
            "victim_state": victim_state,
            "transactions": txns,
            "total_amount_inr": round(sum(t["amount_inr"] for t in txns), 2),
        })

    return json.dumps(results)
