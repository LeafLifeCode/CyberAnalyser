"""
generator/crew.py
------------------
PAFCCI Synthetic Complaint Generator — Main CrewAI Crew.

Usage (standalone Python):
    from generator.crew import CybercrimeGeneratorCrew
    from generator.config import GeneratorConfig

    crew = CybercrimeGeneratorCrew()
    events = crew.run_cycle(GeneratorConfig(num_attackers_active=5))
    for ev in events:
        print(ev["sms_prompt"])

Usage (inside another CrewAI crew):
    from generator.crew import make_generator_crew
    generator_crew = make_generator_crew(llm=your_llm)
    result = generator_crew.kickoff(inputs={...})
"""

import json
import os
from datetime import datetime, timezone

from crewai import Agent, Crew, Process, Task
from langchain_google_genai import ChatGoogleGenerativeAI

from generator.config import GeneratorConfig
from generator.agents.attacker_profile_agent  import make_attacker_profile_agent
from generator.agents.transaction_sim_agent   import make_transaction_sim_agent
from generator.agents.money_mule_chain_agent  import make_mule_chain_agent
from generator.agents.atm_withdrawal_agent    import make_atm_withdrawal_agent
from generator.agents.alert_formatter_agent   import make_alert_formatter_agent
from generator.memory.event_store             import get_store


# -- LLM Factory --------------------------------------------------------------

def _default_llm() -> ChatGoogleGenerativeAI:
    """
    Builds Gemini 1.5 Flash LLM (free tier).
    Requires GOOGLE_API_KEY in environment (set via .env file).
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY not set. "
            "Get a free key at https://aistudio.google.com/app/apikey "
            "and add it to your .env file."
        )
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=api_key,
        temperature=0.2,   # low = deterministic, avoids hallucination in tool calls
        max_tokens=4096,
    )


# -- Crew Builder (for external integration) -----------------------------------

def make_generator_crew(
    config: GeneratorConfig | None = None,
    llm=None,
) -> Crew:
    """
    Build and return a configured CrewAI Crew.
    Can be imported and used inside any parent CrewAI workflow.

    Args:
        config: GeneratorConfig instance. Defaults to GeneratorConfig().
        llm: A LangChain-compatible LLM. Defaults to Gemini 1.5 Flash.

    Returns:
        crewai.Crew instance ready for .kickoff(inputs={...})
    """
    if config is None:
        config = GeneratorConfig()
    if llm is None:
        llm = _default_llm()

    now_iso = datetime.now(tz=timezone.utc).isoformat()

    # -- Instantiate Agents ---------------------------------------------------
    profile_agent  = make_attacker_profile_agent(llm)
    txn_agent      = make_transaction_sim_agent(llm)
    mule_agent     = make_mule_chain_agent(llm)
    atm_agent      = make_atm_withdrawal_agent(llm)
    alert_agent    = make_alert_formatter_agent(llm)

    ctx = config.to_prompt_context()

    # -- Task 1: Generate attacker profiles ----------------------------------
    task_profiles = Task(
        description=(
            f"{ctx}\n"
            f"Call the 'Generate Attacker Profile' tool with:\n"
            f"- num_attackers = {config.num_attackers_active}\n"
            f"- phone_churn_rate = {config.phone_churn_rate}\n"
            f"- ip_churn_rate = {config.ip_churn_rate}\n"
            f"Return the raw JSON output of the tool unchanged."
        ),
        expected_output="A JSON array of synthetic attacker profile objects.",
        agent=profile_agent,
    )

    # -- Task 2: Generate transactions ----------------------------------------
    task_transactions = Task(
        description=(
            f"{ctx}\n"
            f"Using the attacker profiles from the previous task, "
            f"call the 'Generate Victim Transactions' tool with:\n"
            f"- attacker_profiles_json = <output of previous task>\n"
            f"- amount_mean_inr = {config.transaction_amount_mean_inr}\n"
            f"- amount_variance = {config.transaction_amount_variance}\n"
            f"- frequency_before_atm = {config.frequency_before_atm}\n"
            f"- reference_timestamp = '{now_iso}'\n"
            f"Return the raw JSON output of the tool unchanged."
        ),
        expected_output="A JSON array with transactions per attacker.",
        agent=txn_agent,
        context=[task_profiles],
    )

    # -- Task 3: Build mule chains --------------------------------------------
    task_mule = Task(
        description=(
            f"{ctx}\n"
            f"Using the transaction data from the previous task, "
            f"call the 'Build Money Mule Chain' tool with:\n"
            f"- transaction_data_json = <output of previous task>\n"
            f"- mule_chain_depth = {config.mule_chain_depth}\n"
            f"Return the raw JSON output of the tool unchanged."
        ),
        expected_output="A JSON array with mule chain data per attacker.",
        agent=mule_agent,
        context=[task_transactions],
    )

    # -- Task 4: Assign ATM targets -------------------------------------------
    task_atm = Task(
        description=(
            f"{ctx}\n"
            f"Using the mule chain data from the previous task and the attacker "
            f"profiles from task 1, call the 'Assign ATM Withdrawal Target' tool with:\n"
            f"- mule_chain_data_json = <mule chain output>\n"
            f"- attacker_profiles_json = <profiles from task 1>\n"
            f"- atm_bias = '{config.atm_location_bias}'\n"
            f"- report_to_withdrawal_min = {config.time_report_to_withdrawal_min}\n"
            f"- report_to_withdrawal_max = {config.time_report_to_withdrawal_max}\n"
            f"- reference_timestamp = '{now_iso}'\n"
            f"Return the raw JSON output of the tool unchanged."
        ),
        expected_output="A JSON array with ATM assignments and withdrawal times.",
        agent=atm_agent,
        context=[task_mule, task_profiles],
    )

    # -- Task 5: Format alerts ------------------------------------------------
    task_alert = Task(
        description=(
            f"{ctx}\n"
            f"Using the fully enriched event data from the previous task, "
            f"call the 'Format Alert SMS Prompts' tool with:\n"
            f"- enriched_data_json = <output of previous task>\n"
            f"- cycle_timestamp = '{now_iso}'\n"
            f"Return the raw JSON output of the tool unchanged. "
            f"This JSON will be parsed by the downstream risk management agent."
        ),
        expected_output=(
            "A JSON array of complete complaint events, each containing "
            "a 'sms_prompt' field with the formatted alert text."
        ),
        agent=alert_agent,
        context=[task_atm],
    )

    return Crew(
        agents=[profile_agent, txn_agent, mule_agent, atm_agent, alert_agent],
        tasks=[task_profiles, task_transactions, task_mule, task_atm, task_alert],
        process=Process.sequential,
        verbose=False,
    )


# ── High-level convenience class ──────────────────────────────────────────────

class CybercrimeGeneratorCrew:
    """
    High-level wrapper around the CrewAI Cybercrime Generator.
    Supports both LLM-driven CrewAI execution and instant direct tool execution.

    Example:
        crew = CybercrimeGeneratorCrew(use_llm=False)
        events = crew.run_cycle(GeneratorConfig(num_attackers_active=5))
    """

    def __init__(self, use_llm: bool = False, llm=None):
        self.use_llm = use_llm
        self._llm = None
        if use_llm:
            try:
                self._llm = llm or _default_llm()
            except Exception:
                self.use_llm = False
        self._store = get_store()

    def run_cycle(self, config: GeneratorConfig) -> list[dict]:
        """
        Run one generation cycle: produce one batch of synthetic complaint events.

        Returns:
            List of ComplaintEvent dicts (each has a 'sms_prompt' field).
        """
        if self.use_llm and self._llm:
            return self._run_crew_llm(config)
        else:
            return self._run_direct_tools(config)

    def _run_direct_tools(self, config: GeneratorConfig) -> list[dict]:
        """Direct deterministic Python execution through the 5-tool pipeline (~1 sec)."""
        from generator.tools import (
            attacker_tools,
            transaction_tools,
            mule_chain_tools,
            atm_tools,
            alert_tools,
        )

        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30), name="IST")
        now_iso = datetime.now(tz=IST).isoformat()

        # Step 1: Attacker Profiles
        raw1 = attacker_tools.generate_attacker_profile.func(
            num_attackers=config.num_attackers_active,
            phone_churn_rate=config.phone_churn_rate,
            ip_churn_rate=config.ip_churn_rate,
        )

        # Step 2: Transactions
        raw2 = transaction_tools.generate_transactions.func(
            attacker_profiles_json=raw1,
            amount_mean_inr=config.transaction_amount_mean_inr,
            amount_variance=config.transaction_amount_variance,
            frequency_before_atm=config.frequency_before_atm,
            reference_timestamp=now_iso,
        )

        # Step 3: Mule Chains
        raw3 = mule_chain_tools.build_mule_chain.func(
            transaction_data_json=raw2,
            mule_chain_depth=config.mule_chain_depth,
        )

        # Step 4: ATM Assignment
        raw4 = atm_tools.assign_atm_withdrawal.func(
            mule_chain_data_json=raw3,
            attacker_profiles_json=raw1,
            atm_bias=config.atm_location_bias,
            report_to_withdrawal_min=config.time_report_to_withdrawal_min,
            report_to_withdrawal_max=config.time_report_to_withdrawal_max,
            reference_timestamp=now_iso,
        )

        # Step 5: Alert SMS Formatting
        raw5 = alert_tools.format_alert_prompts.func(
            enriched_data_json=raw4,
            cycle_timestamp=now_iso,
        )

        events = json.loads(raw5)
        self._store.add_events(events)
        return events

    def _run_crew_llm(self, config: GeneratorConfig) -> list[dict]:
        """CrewAI LLM-driven execution."""
        crew = make_generator_crew(config=config, llm=self._llm)
        result = crew.kickoff()

        raw = result.raw if hasattr(result, "raw") else str(result)
        try:
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            events = json.loads(raw)
        except json.JSONDecodeError:
            events = [{
                "complaint_id": "PARSE-ERROR",
                "sms_prompt": f"[ERROR] Could not parse crew output:\n{raw[:500]}",
                "synthetic": True,
            }]

        self._store.add_events(events)
        return events

    def get_all_events(self) -> list[dict]:
        """Return all events stored in the last 30 minutes."""
        return self._store.get_all()

