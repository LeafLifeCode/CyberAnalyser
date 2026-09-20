"""
generator/agents/atm_withdrawal_agent.py
------------------------------------------
CrewAI Agent: Selects ATM target and predicts withdrawal timing.
"""

from crewai import Agent
from generator.tools.atm_tools import assign_atm_withdrawal


def make_atm_withdrawal_agent(llm) -> Agent:
    return Agent(
        role="ATM Withdrawal Location Predictor",
        goal=(
            "Select the most likely ATM from the 200 synthetic locations "
            "where the attacker will withdraw funds, and compute the "
            "predicted withdrawal timestamp based on the mule chain delay "
            "and the victim report-to-withdrawal window."
        ),
        backstory=(
            "You model the final stage of financial cybercrime: "
            "cash-out at an ATM. Attackers prefer ATMs in busy urban areas "
            "during off-peak hours to minimise camera attention. "
            "The withdrawal is always time-pressured — attackers try to "
            "reach the ATM before the victim's bank can freeze the account."
        ),
        tools=[assign_atm_withdrawal],
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )
