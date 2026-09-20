"""
generator/agents/alert_formatter_agent.py
-------------------------------------------
CrewAI Agent: Risk-scores each event and formats SMS prompts for the next agent.
"""

from crewai import Agent
from generator.tools.alert_tools import format_alert_prompts


def make_alert_formatter_agent(llm) -> Agent:
    return Agent(
        role="Cybercrime Alert Formatter",
        goal=(
            "Compute a risk score for each synthetic complaint event, "
            "assign a risk label (LOW/MEDIUM/HIGH/CRITICAL), and "
            "format the event as a structured SMS-style alert prompt "
            "ready for the downstream risk management agent to consume."
        ),
        backstory=(
            "You are the final stage of the predictive analytics pipeline. "
            "You transform raw simulated data into actionable intelligence. "
            "Your SMS prompts are the exact format the Risk Management Agent "
            "expects: structured, parseable, and unambiguous."
        ),
        tools=[format_alert_prompts],
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )
