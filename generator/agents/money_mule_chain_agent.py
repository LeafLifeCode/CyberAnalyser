"""
generator/agents/money_mule_chain_agent.py
--------------------------------------------
CrewAI Agent: Simulates multi-hop money mule layering.
"""

from crewai import Agent
from generator.tools.mule_chain_tools import build_mule_chain


def make_mule_chain_agent(llm) -> Agent:
    return Agent(
        role="Money Mule Chain Analyst",
        goal=(
            "Simulate the layering stage of financial cybercrime: "
            "route fraud proceeds through N intermediate 'mule' accounts "
            "across different banks and states before final ATM withdrawal."
        ),
        backstory=(
            "You model the money-laundering behaviour of cybercrime syndicates. "
            "After receiving fraud proceeds, syndicates immediately transfer funds "
            "through a chain of disposable accounts (mules) across multiple banks "
            "to obscure the trail. Each hop may involve a different transfer type "
            "and incurs a small 'commission' fee skimmed by the mule."
        ),
        tools=[build_mule_chain],
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )
