"""
generator/tools/attacker_tools.py
-----------------------------------
CrewAI @tool functions for attacker profile generation.
All outputs are SYNTHETIC — no real data.
"""

import json
import random
import uuid
from datetime import datetime

from crewai.tools import tool
from faker import Faker

_fake = Faker("en_IN")
_fake.seed_instance(None)   # true random each run

# Official NCRP (National Cybercrime Reporting Portal) fraud activity categories
_MODI = [
    "Business Email Compromise/Email Takeover",
    "Debit/Credit Card Fraud/Sim Swap Fraud",
    "Demat/Depository Fraud",
    "E-Wallet Related Fraud",
    "Fraud Call/Vishing",
    "Internet Banking Related Fraud",
    "UPI Fraud",
]
_VPN_PROVIDERS = ["ProtonVPN", "NordVPN", "ExpressVPN", "Tor Exit", "Unknown Proxy"]
_STATES = [
    "Uttar Pradesh", "Rajasthan", "Jharkhand", "Bihar", "Haryana",
    "Madhya Pradesh", "Delhi", "Maharashtra", "West Bengal", "Gujarat",
]


def _gen_indian_phone() -> str:
    prefix = random.choice(["7", "8", "9"])
    return f"+91-{prefix}" + "".join(str(random.randint(0, 9)) for _ in range(9))


def _gen_ip() -> str:
    return ".".join(str(random.randint(1, 254)) for _ in range(4))


# ── Persistent Attacker Pool ──────────────────────────────────────────────────
# The same N attackers persist across generator cycles so that:
#   - ip_phone_mismatch: the same phone/IP appears multiple times in the EventStore
#     with different bindings (after churn), triggering mismatch detection.
#   - ip_velocity: the same IP appears at different ATM locations across cycles,
#     triggering impossible-travel detection.
# The pool is reset only when num_attackers changes.

_attacker_pool: list[dict] = []
_pool_size: int = 0


def _initialise_pool(num_attackers: int) -> None:
    """Create a fresh set of N persistent attacker profiles."""
    global _attacker_pool, _pool_size
    _attacker_pool = []
    for _ in range(num_attackers):
        phone_history = [_gen_indian_phone()]
        ip_history = [_gen_ip()]
        _attacker_pool.append({
            "attacker_id":   f"ATK-{uuid.uuid4().hex[:6].upper()}",
            "phone_history": phone_history,
            "active_phone":  phone_history[-1],
            "ip_history":    ip_history,
            "active_ip":     ip_history[-1],
            "vpn_provider":  random.choice(_VPN_PROVIDERS),
            "base_state":    random.choice(_STATES),
            "modus_operandi": random.choice(_MODI),
        })
    _pool_size = num_attackers


def _churn_pool(phone_churn_rate: float, ip_churn_rate: float) -> None:
    """
    Mutate each attacker's phone/IP independently at the configured churn rate.
    History is preserved so mismatch signals can detect the pattern.
    """
    for atk in _attacker_pool:
        if random.random() < phone_churn_rate:
            new_phone = _gen_indian_phone()
            atk["phone_history"].append(new_phone)
            atk["active_phone"] = new_phone
        if random.random() < ip_churn_rate:
            new_ip = _gen_ip()
            atk["ip_history"].append(new_ip)
            atk["active_ip"] = new_ip
            atk["vpn_provider"] = random.choice(_VPN_PROVIDERS)


@tool("Generate Attacker Profile")
def generate_attacker_profile(num_attackers: int, phone_churn_rate: float, ip_churn_rate: float) -> str:
    """
    Generate synthetic profiles for N concurrent cybercrime attackers.

    Attackers persist across generator cycles — the same identities recur so that
    the Variance Model can detect patterns like IP churn (mismatch) and impossible
    travel (velocity). Phone/IP churn occurs per-cycle at the configured rates.

    Args:
        num_attackers: How many attacker profiles to create (1-20).
        phone_churn_rate: Probability 0.0-1.0 that an attacker swaps their SIM this cycle.
        ip_churn_rate: Probability 0.0-1.0 that an attacker changes VPN/IP this cycle.

    Returns:
        JSON string — list of attacker profile dicts.
    """
    global _attacker_pool, _pool_size
    num_attackers = min(max(1, num_attackers), 20)

    if len(_attacker_pool) != num_attackers:
        # First call or attacker count changed — reinitialise the pool
        _initialise_pool(num_attackers)
    else:
        # Subsequent cycle — mutate existing attackers at the churn rates
        _churn_pool(phone_churn_rate, ip_churn_rate)

    return json.dumps(_attacker_pool)

