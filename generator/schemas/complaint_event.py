"""
generator/schemas/complaint_event.py
--------------------------------------
Pydantic v2 data models for synthetic cybercrime complaint events.
All events are labelled synthetic=True and must not be used as legal evidence.
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Literal
from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """Single financial transaction in the attacker-victim chain."""
    txn_id: str
    timestamp: datetime
    txn_type: Literal["UPI", "IMPS", "NEFT", "RTGS", "Card"]
    sender_id: str          # VPA / account number (synthetic)
    receiver_id: str
    amount_inr: float
    bank_ifsc: str


class MuleHop(BaseModel):
    """One hop in the money-mule layering chain."""
    hop_number: int          # 1 = first hop from victim, N = final before ATM
    account_id: str          # synthetic account number
    bank_name: str
    bank_ifsc: str
    state: str
    amount_inr: float
    transfer_type: Literal["UPI", "IMPS", "NEFT", "RTGS"]
    delay_minutes: int       # time this hop took


class AttackerProfile(BaseModel):
    """Synthetic profile of a single cybercrime attacker."""
    attacker_id: str
    active_phone: str        # current spoofed / active number
    phone_history: List[str] # SIMs used (churn simulation)
    active_ip: str           # current IP (VPN hop)
    ip_history: List[str]
    base_state: str          # state where attacker is physically operating
    modus_operandi: Literal[
        "Business Email Compromise/Email Takeover",
        "Debit/Credit Card Fraud/Sim Swap Fraud",
        "Demat/Depository Fraud",
        "E-Wallet Related Fraud",
        "Fraud Call/Vishing",
        "Internet Banking Related Fraud",
        "UPI Fraud",
    ]


class ATMWithdrawal(BaseModel):
    """Predicted ATM withdrawal event."""
    atm_id: str
    bank: str
    location_label: str
    city: str
    state: str
    latitude: float
    longitude: float
    predicted_withdrawal_time: datetime
    amount_inr: float
    time_from_report_minutes: int  # lag between victim filing report and ATM hit


class ComplaintEvent(BaseModel):
    """
    A complete synthetic cybercrime complaint event.
    One event = one attacker's full cycle: fraud ? layering ? ATM withdrawal.
    The sms_prompt field is the ready-to-consume alert for the next CrewAI agent.
    """
    complaint_id: str
    generated_at: datetime
    synthetic: bool = True               # ALWAYS True — never real data

    attacker: AttackerProfile
    victim_state: str
    transactions: List[Transaction]      # transactions before mule chain
    mule_chain: List[MuleHop]
    withdrawal: ATMWithdrawal

    total_amount_inr: float
    mule_chain_depth: int
    risk_score: float                    # 0.0 – 1.0, computed by scoring heuristic
    risk_label: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    # -- Output for next agent --------------------------------------
    sms_prompt: str                      # Formatted SMS-style alert string
