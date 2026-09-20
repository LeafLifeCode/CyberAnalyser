"""
generator/tools/atm_tools.py
------------------------------
Selects ATM withdrawal targets from the 200 fixed synthetic ATMs.
Computes predicted withdrawal time based on mule chain delay.
"""

import json
import random
from datetime import datetime, timedelta

from crewai.tools import tool
from generator.data.atm_locations import ATM_LOCATIONS

_URBAN_STATES  = {"Maharashtra", "Delhi", "Karnataka", "Tamil Nadu", "Telangana", "West Bengal"}
_SEMI_STATES   = {"Gujarat", "Punjab", "Rajasthan", "Kerala", "Chandigarh"}
_RURAL_STATES  = {"Bihar", "Jharkhand", "Uttar Pradesh", "Madhya Pradesh", "Odisha"}


def _atms_for_bias(bias: str) -> list:
    if bias == "Urban":
        pool = [a for a in ATM_LOCATIONS if a["state"] in _URBAN_STATES]
    elif bias == "Semi-Urban":
        pool = [a for a in ATM_LOCATIONS if a["state"] in _SEMI_STATES]
    elif bias == "Rural":
        pool = [a for a in ATM_LOCATIONS if a["state"] in _RURAL_STATES]
    else:
        pool = ATM_LOCATIONS
    return pool if pool else ATM_LOCATIONS   # fallback to all


@tool("Assign ATM Withdrawal Target")
def assign_atm_withdrawal(
    mule_chain_data_json: str,
    attacker_profiles_json: str,
    atm_bias: str,
    report_to_withdrawal_min: int,
    report_to_withdrawal_max: int,
    reference_timestamp: str,
) -> str:
    """
    For each attacker, select an ATM from the 200 synthetic locations and
    compute the predicted withdrawal timestamp.

    Args:
        mule_chain_data_json: JSON from build_mule_chain tool.
        attacker_profiles_json: JSON from generate_attacker_profile tool.
        atm_bias: One of "Urban", "Semi-Urban", "Rural", "Random".
        report_to_withdrawal_min: Minimum minutes victim report to ATM hit.
        report_to_withdrawal_max: Maximum minutes victim report to ATM hit.
        reference_timestamp: ISO datetime string for cycle start (= victim report time).

    Returns:
        JSON string — fully enriched event list ready for alert formatting.
    """
    chain_data = json.loads(mule_chain_data_json)
    profiles   = {p["attacker_id"]: p for p in json.loads(attacker_profiles_json)}
    ref_dt     = datetime.fromisoformat(reference_timestamp)
    atm_pool   = _atms_for_bias(atm_bias)
    results    = []

    for entry in chain_data:
        aid      = entry["attacker_id"]
        profile  = profiles.get(aid, {})
        atm      = random.choice(atm_pool)

        # Withdrawal window: report_time + random lag within configured window
        lag_min  = random.randint(report_to_withdrawal_min, report_to_withdrawal_max)
        withdrawal_dt = ref_dt + timedelta(minutes=lag_min)

        entry["attacker_profile"]   = profile
        entry["atm"]                = atm
        entry["predicted_withdrawal_time"] = withdrawal_dt.isoformat()
        entry["time_from_report_minutes"]  = lag_min
        results.append(entry)

    return json.dumps(results)
