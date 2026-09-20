"""
generator/agents/attacker_profile_agent.py
--------------------------------------------
CrewAI Agent: Generates synthetic attacker profiles with SIM/IP churn.
"""

from crewai import Agent
from generator.tools.attacker_tools import generate_attacker_profile


def make_attacker_profile_agent(llm) -> Agent:
    """
    Returns the AttackerProfileAgent.
    Call this with a configured LLM instance (e.g. ChatGoogleGenerativeAI).
    """
    return Agent(
        role="Cyber Attacker Profile Synthesiser",
        goal=(
            "Generate realistic synthetic profiles for cybercrime attackers. "
            "Simulate SIM card swapping and VPN/IP rotation as real attackers do "
            "to evade CDR (Call Detail Record) analysis by law enforcement."
        ),
        backstory=(
            "You model the behaviour of financial cybercriminals operating in India. "
            "You know that attackers frequently swap SIM cards, rotate through VPN IPs, "
            "and operate from states like UP, Rajasthan, and Jharkhand. "
            "You produce synthetic but behaviourally realistic profiles for training "
            "predictive analytics systems."
        ),
        tools=[generate_attacker_profile],
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )
