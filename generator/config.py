"""
generator/config.py
--------------------
Dataclass holding all tunable generator parameters.
Populated from the Streamlit sidebar and passed as context to the Crew.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class GeneratorConfig:
    # ── Attacker Settings ─────────────────────────────────────────
    num_attackers_active: int = 3
    """Number of concurrent synthetic attackers (1 – 20)."""

    phone_churn_rate: float = 0.20
    """Probability (0.0–1.0) that an attacker swaps SIM each cycle."""

    ip_churn_rate: float = 0.20
    """Probability (0.0–1.0) that an attacker changes IP/VPN each cycle."""

    # ── Transaction Settings ──────────────────────────────────────
    transaction_amount_mean_inr: float = 70_000.0
    """Mean fraud transaction amount in INR."""

    transaction_amount_variance: float = 0.30
    """Std-dev as a fraction of mean (e.g. 0.30 = ±30%)."""

    frequency_before_atm: int = 3
    """Number of transactions before the final ATM withdrawal."""

    # ── Mule Chain Settings ────────────────────────────────-------
    mule_chain_depth: int = 3
    """Number of hop accounts money passes through (2 – 7)."""

    # ── ATM / Withdrawal Settings ─────────────────────────────────
    atm_location_bias: Literal["Urban", "Semi-Urban", "Rural", "Random"] = "Urban"
    """Bias towards which city tier the attacker prefers for withdrawal."""

    time_report_to_withdrawal_min: int = 10
    """Minimum minutes from victim filing report to ATM withdrawal."""

    time_report_to_withdrawal_max: int = 30
    """Maximum minutes from victim filing report to ATM withdrawal."""

    # ── Orchestrator / Timing Settings ───────────────────────────
    time_between_prompts_sec: int = 20
    """Seconds between each generation cycle (tick interval)."""

    def to_prompt_context(self) -> str:
        """Serialize config as a plain-English block for agent context injection."""
        return (
            f"GENERATOR CONFIG:\n"
            f"- Active attackers: {self.num_attackers_active}\n"
            f"- Phone churn rate: {self.phone_churn_rate:.0%}\n"
            f"- IP churn rate: {self.ip_churn_rate:.0%}\n"
            f"- Transaction mean: INR {self.transaction_amount_mean_inr:,.0f} "
            f"(±{self.transaction_amount_variance:.0%} variance)\n"
            f"- Transactions before ATM: {self.frequency_before_atm}\n"
            f"- Mule chain depth: {self.mule_chain_depth} hops\n"
            f"- ATM location bias: {self.atm_location_bias}\n"
            f"- Victim-report to withdrawal window: "
            f"{self.time_report_to_withdrawal_min}–{self.time_report_to_withdrawal_max} min\n"
            f"- Tick interval: {self.time_between_prompts_sec}s\n"
        )
