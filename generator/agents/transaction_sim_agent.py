"""
generator/agents/transaction_sim_agent.py
-------------------------------------------
CrewAI Agent: Simulates victim-to-attacker financial transactions.
"""

from crewai import Agent
from generator.tools.transaction_tools import generate_transactions


def make_transaction_sim_agent(llm) -> Agent:
    return Agent(
        role="Financial Transaction Simulator",
        goal=(
            "Generate a realistic sequence of UPI/IMPS/NEFT transactions "
            "from victim accounts to attacker-controlled accounts, "
            "matching the configured amount and frequency parameters."
        ),
        backstory=(
            "You model how financial cyber fraud manifests in banking systems. "
            "Victims transfer money in multiple small or single large transactions. "
            "You simulate the transaction pattern that LEAs and banks see in "
            "their fraud detection systems before the money is layered."
        ),
        tools=[generate_transactions],
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )
