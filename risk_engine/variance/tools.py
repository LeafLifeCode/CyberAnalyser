"""
risk_engine/variance/tools.py
------------------------------
CrewAI Tool wrappers for the Variance Model signals and aggregators.

All tool functions wrap deterministic Python scoring functions, ensuring mathematical
reproducibility while allowing CrewAI agents to orchestrate analysis.
"""

import json
from crewai.tools import tool

from risk_engine.variance.signals import (
    detect_ip_phone_mismatch,
    detect_deposit_spike,
    detect_ip_velocity,
)
from risk_engine.variance.aggregator import (
    aggregate_variance_signals,
    aggregate_weekly_spikes,
)


@tool("Detect IP Phone Mismatch Signal")
def detect_ip_phone_mismatch_tool(events_json: str, time_window_hours: float = 24.0) -> str:
    """
    Detect abnormal change in IP address associated with a given phone number or vice versa.

    Args:
        events_json: JSON string of complaint events.
        time_window_hours: Time window in hours (default 24.0).

    Returns:
        JSON string of detected ip_phone_mismatch signal records.
    """
    events = json.loads(events_json) if isinstance(events_json, str) else events_json
    results = detect_ip_phone_mismatch(events, time_window_hours=float(time_window_hours))
    return json.dumps(results)


@tool("Detect Deposit Spike Signal")
def detect_deposit_spike_tool(events_json: str, baseline_days: int = 7, z_threshold: float = 2.5) -> str:
    """
    Detect sudden spikes in incoming deposits into bank accounts relative to trailing N-day baseline.

    Args:
        events_json: JSON string of complaint events.
        baseline_days: Days for trailing baseline mean/std (default 7).
        z_threshold: Standard deviation threshold (default 2.5).

    Returns:
        JSON string of detected deposit_spike signal records.
    """
    events = json.loads(events_json) if isinstance(events_json, str) else events_json
    results = detect_deposit_spike(events, baseline_days=int(baseline_days), z_threshold=float(z_threshold))
    return json.dumps(results)


@tool("Detect IP Velocity Signal")
def detect_ip_velocity_tool(events_json: str, max_speed_kmh: float = 900.0, vpn_buffer_km: float = 200.0) -> str:
    """
    Detect impossible travel / rapid proxy hopping exceeding commercial flight speed bounds (>900 km/h over >200 km).

    Args:
        events_json: JSON string of complaint events.
        max_speed_kmh: Max plausible travel speed in km/h (default 900.0).
        vpn_buffer_km: Spatial buffer in km for legitimate VPN switching (default 200.0).

    Returns:
        JSON string of detected ip_velocity signal records.
    """
    events = json.loads(events_json) if isinstance(events_json, str) else events_json
    results = detect_ip_velocity(events, max_speed_kmh=float(max_speed_kmh), vpn_buffer_km=float(vpn_buffer_km))
    return json.dumps(results)


@tool("Aggregate Variance Signals")
def aggregate_variance_signals_tool(signal_results_json: str) -> str:
    """
    Combine sub-scores from ip_phone_mismatch, deposit_spike, and ip_velocity signals into unified entity records.

    Args:
        signal_results_json: JSON string containing list of all sub-signal detection results.

    Returns:
        JSON string of aggregated risk records preserving full evidence explainability.
    """
    signals = json.loads(signal_results_json) if isinstance(signal_results_json, str) else signal_results_json
    results = aggregate_variance_signals(signals)
    return json.dumps(results)


@tool("Aggregate Weekly Spikes")
def aggregate_weekly_spikes_tool(flagged_records_json: str) -> str:
    """
    Bucket flagged entity events into ISO calendar weeks for time-series spike charting.

    Args:
        flagged_records_json: JSON string of aggregated risk records.

    Returns:
        JSON string of weekly bucketed records ready for visualization.
    """
    records = json.loads(flagged_records_json) if isinstance(flagged_records_json, str) else flagged_records_json
    results = aggregate_weekly_spikes(records)
    return json.dumps(results)