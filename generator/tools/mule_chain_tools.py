"""
generator/tools/mule_chain_tools.py
-------------------------------------
Simulates money-mule layering: funds pass through N intermediary accounts
before reaching the ATM withdrawal account.
"""

import json
import random
import uuid
from crewai.tools import tool

_BANKS = [
    "SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "PNB",
    "Bank of Baroda", "Canara Bank", "Kotak Mahindra", "Yes Bank",
    "Union Bank of India", "IndusInd Bank", "IDBI Bank", "Paytm Payments Bank",
]
_TRANSFER_TYPES = ["UPI", "IMPS", "NEFT", "RTGS"]
_STATES = [
    "Uttar Pradesh", "Rajasthan", "Jharkhand", "Bihar", "Haryana",
    "Madhya Pradesh", "Delhi", "Maharashtra", "West Bengal", "Gujarat",
    "Punjab", "Tamil Nadu", "Karnataka", "Telangana", "Odisha",
]
_IFSC_PREFIXES = ["SBIN", "HDFC", "ICIC", "UTIB", "PUNB", "BARB", "CNRB", "KKBK", "YESB", "UBIN"]


def _gen_ifsc() -> str:
    return f"{random.choice(_IFSC_PREFIXES)}0{random.randint(100000, 999999)}"


def _gen_account() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(12))


@tool("Build Money Mule Chain")
def build_mule_chain(transaction_data_json: str, mule_chain_depth: int) -> str:
    """
    Simulate layering: each attacker's fraud funds pass through a randomly chosen
    number of intermediate mule accounts (1 to mule_chain_depth) before the final
    ATM withdrawal. Different attackers in the same cycle can have different chain lengths.

    Args:
        transaction_data_json: JSON from generate_transactions tool.
        mule_chain_depth: Maximum number of hop accounts allowed (1-7). Each attacker
                          independently draws a random depth from 1 to this max.

    Returns:
        JSON string — original data enriched with mule_chain[] per attacker.
    """
    tx_data = json.loads(transaction_data_json)
    max_depth = min(max(1, mule_chain_depth), 7)   # upper bound from slider
    results = []

    for entry in tx_data:
        # Each attacker independently picks a random chain length from 1 to max_depth
        depth = random.randint(1, max_depth)
        total = entry["total_amount_inr"]
        remaining = total
        chain = []

        for hop in range(1, depth + 1):
            # Each hop skims a small percentage (commission to mule)
            skim_pct = random.uniform(0.02, 0.08)
            hop_amount = round(remaining * (1 - skim_pct), 2)
            delay_min = random.randint(5, 360)  # 5 min – 6 hours per hop

            chain.append({
                "hop_number":    hop,
                "account_id":    _gen_account(),
                "bank_name":     random.choice(_BANKS),
                "bank_ifsc":     _gen_ifsc(),
                "state":         random.choice(_STATES),
                "amount_inr":    hop_amount,
                "transfer_type": random.choice(_TRANSFER_TYPES),
                "delay_minutes": delay_min,
            })
            remaining = hop_amount

        entry["mule_chain"]          = chain
        entry["final_amount_inr"]    = round(remaining, 2)  # amount reaching ATM
        entry["mule_chain_depth"]    = depth
        entry["total_hop_delay_min"] = sum(h["delay_minutes"] for h in chain)
        results.append(entry)

    return json.dumps(results)
