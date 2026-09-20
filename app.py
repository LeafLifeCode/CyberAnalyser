"""
app.py  — PAFCCI Synthetic Complaint Live Generator & Risk Engine Dashboard
=============================================================================
Streamlit dashboard for Complaint Generation (Phase 0) & Risk Engine Variance Model (Component 2).

Run:
    streamlit run app.py
"""

import json
import os
import threading
import time
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

import pydeck as pdk
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Load .env before importing crew
load_dotenv()

from generator.config import GeneratorConfig
from generator.crew import CybercrimeGeneratorCrew
from generator.memory.event_store import get_store
from risk_engine.variance.agent import run_variance_analysis
from risk_engine.prediction.agent import run_prediction_analysis
from risk_engine.prediction.markov import reset_model
from risk_engine.prediction.recalibration import get_audit_log, reset_engines
from risk_engine.prediction.drift_detector import reset_drift_detector
from delivery_model.agent import run_delivery_routing
from delivery_model.appeals import get_appeals_manager, reset_appeals_manager
from delivery_model.audit import get_delivery_audit_log, reset_delivery_audit_log
from cyber_portal.bridge import (
    AUTHORITY_USERS,
    verify_and_claim_otp,
    commit_authority_actions,
    sign_out_user,
    get_user_status,
)

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PAFCCI Platform | I4C Cybercrime Intelligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS Theming ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .risk-CRITICAL { color: #ff4b4b; font-weight: bold; }
    .risk-HIGH     { color: #ff8800; font-weight: bold; }
    .risk-MEDIUM   { color: #ffd700; }
    .risk-LOW      { color: #00cc88; }
    .sms-box {
        background: #1e1e2e; border: 1px solid #444;
        border-radius: 8px; padding: 12px;
        font-family: 'Courier New', monospace; font-size: 12px;
        white-space: pre-wrap; color: #e0e0e0;
        max-height: 400px; overflow-y: auto;
    }
    .evidence-box {
        background: #1a1c23; border-left: 4px solid #00cc88;
        padding: 10px; font-family: monospace; font-size: 13px;
    }
    .stPydeckChart, iframe[title="pydeck.Deck"], div[data-testid="stDeckGlJsonContainer"] {
        background-color: #0D3280 !important;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ── Session State Init ────────────────────────────────────────────────────────
if "running"           not in st.session_state: st.session_state.running           = False
if "crew"              not in st.session_state: st.session_state.crew              = None
if "cycle_count"       not in st.session_state: st.session_state.cycle_count       = 0
if "last_cycle_time"   not in st.session_state: st.session_state.last_cycle_time   = None
if "last_events"       not in st.session_state: st.session_state.last_events       = []
if "error_msg"         not in st.session_state: st.session_state.error_msg         = ""
if "selected_atm"      not in st.session_state: st.session_state.selected_atm      = None
if "cache_cycle_count" not in st.session_state: st.session_state.cache_cycle_count = -1
if "cached_var_res"    not in st.session_state: st.session_state.cached_var_res    = None
if "cached_pred_res"   not in st.session_state: st.session_state.cached_pred_res   = None
if "cached_deliv_res"  not in st.session_state: st.session_state.cached_deliv_res  = None
if "dm_auth_officer"   not in st.session_state: st.session_state.dm_auth_officer   = None
if "dm_staged_actions" not in st.session_state: st.session_state.dm_staged_actions = []
if "dm_show_signout_confirm" not in st.session_state: st.session_state.dm_show_signout_confirm = False

store = get_store()

# ── Sidebar Controls ─────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Generator & Engine Controls")
    st.caption("All data is SYNTHETIC — not real.")
    st.divider()

    st.subheader("⚡ Execution Mode")
    exec_mode = st.radio(
        "Platform Mode",
        ["Fast Direct Mode (~1s, Offline)", "CrewAI Agent Mode (Gemini LLM)"],
        index=0,
        help="Fast Direct mode runs deterministic pipeline locally without API keys.",
    )
    use_llm = "Gemini LLM" in exec_mode

    st.subheader("👤 Attacker Settings")
    num_attackers   = st.slider("Active Attackers",         1, 20,  3)
    phone_churn     = st.slider("Phone Churn Rate",        0.0, 1.0, 0.20, 0.05)
    ip_churn        = st.slider("IP/VPN Churn Rate",       0.0, 1.0, 0.20, 0.05)

    st.subheader("💸 Transaction Settings")
    amount_mean     = st.number_input("Mean Fraud Amount (INR)", 1000, 500000, 70000, 1000)
    amount_var      = st.slider("Amount Variance",           0.05, 1.0, 0.30, 0.05)
    freq_before_atm = st.slider("Transactions before ATM",    1, 20,   3)

    st.subheader("🔗 Mule Chain Settings")
    mule_depth      = st.slider("Max Mule Chain Depth (hops)",   2,  7,   3)

    st.subheader("🏧 ATM / Withdrawal Settings")
    atm_bias        = st.selectbox("ATM Location Bias", ["Urban", "Semi-Urban", "Rural", "Random"])
    report_to_w_min = st.slider("Report→Withdrawal Min (min)",  1, 60,  10)
    report_to_w_max = st.slider("Report→Withdrawal Max (min)", 10, 240, 30)

    st.subheader("⏱️ Timing Settings")
    tick_interval   = st.slider("Interval Between Cycles (sec)", 10, 300, 20, 10)

    st.divider()

    # Start / Stop
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶ START", use_container_width=True,
                     disabled=st.session_state.running,
                     type="primary"):
            st.session_state.running = True
            st.session_state.error_msg = ""
            st.rerun()
    with col2:
        if st.button("⏹ STOP", use_container_width=True,
                     disabled=not st.session_state.running):
            st.session_state.running = False
            st.rerun()

    if st.button("🗑 Clear Store", use_container_width=True):
        from generator.tools.attacker_tools import _initialise_pool
        store.clear()
        _initialise_pool(0)           # wipe the persistent attacker pool
        reset_model()                 # wipe Markov prediction model
        reset_engines()               # wipe recalibration engine + audit log
        reset_drift_detector()        # wipe drift detection windows
        reset_appeals_manager()       # wipe appeals state machine
        reset_delivery_audit_log()    # wipe delivery audit log
        st.session_state.cycle_count       = 0
        st.session_state.last_events       = []
        st.session_state.selected_atm      = None
        st.session_state.cache_cycle_count   = -1
        st.session_state.cached_pred_cycle   = -1
        st.session_state.cached_event_count  = -1
        st.session_state.cached_var_res      = None
        st.session_state.cached_pred_res     = None
        st.session_state.cached_deliv_res    = None
        st.session_state.cached_deliv_params = None
        st.rerun()

    if st.button("▶ Run One Cycle Now", use_container_width=True):
        st.session_state.running = False
        st.session_state._run_once = True
        st.rerun()

# ── Build Config from Sidebar Values ─────────────────────────────────────────
config = GeneratorConfig(
    num_attackers_active          = num_attackers,
    phone_churn_rate              = phone_churn,
    ip_churn_rate                 = ip_churn,
    transaction_amount_mean_inr   = float(amount_mean),
    transaction_amount_variance   = amount_var,
    frequency_before_atm          = freq_before_atm,
    mule_chain_depth              = mule_depth,
    atm_location_bias             = atm_bias,
    time_report_to_withdrawal_min = report_to_w_min,
    time_report_to_withdrawal_max = report_to_w_max,
    time_between_prompts_sec      = tick_interval,
)

# ── Main Title ────────────────────────────────────────────────────────────────
st.title("🔍 PAFCCI — Cybercrime Predictive Analytics Platform")
st.caption(
    "Predictive Analytics Framework for Cybercrime Complaint Intelligence · "
    "[I4C / MHA Research Prototype] · **SYNTHETIC DATA ONLY**"
)

# ── Status Bar ────────────────────────────────────────────────────────────────
status_col, cyc_col, store_col, err_col = st.columns([2, 1, 1, 3])
with status_col:
    if st.session_state.running:
        st.success("🟢 Generator & Engine RUNNING")
    else:
        st.info("🔴 Platform STOPPED")
with cyc_col:
    st.metric("Cycles Run", st.session_state.cycle_count)
with store_col:
    st.metric("Events in Store", store.count())
with err_col:
    if st.session_state.error_msg:
        st.error(st.session_state.error_msg)

st.divider()

# ── Generation Logic ──────────────────────────────────────────────────────────
def _run_one_cycle():
    """Instantiate crew and run one generation cycle."""
    try:
        crew = CybercrimeGeneratorCrew(use_llm=use_llm)
        events = crew.run_cycle(config)
        st.session_state.last_events   = events
        st.session_state.cycle_count  += 1
        st.session_state.last_cycle_time = datetime.now(tz=timezone.utc).isoformat()
        st.session_state.error_msg = ""
        return events
    except Exception as e:
        st.session_state.error_msg = f"Error: {e}"
        st.session_state.running   = False
        return []

# Trigger: single cycle button
if st.session_state.get("_run_once"):
    st.session_state._run_once = False
    with st.spinner("Running one generation cycle..."):
        _run_one_cycle()
    st.rerun()

# Trigger: auto-generate loop
if st.session_state.running:
    with st.spinner(f"Generating cycle {st.session_state.cycle_count + 1}..."):
        _run_one_cycle()
    time.sleep(0.5)
    st.rerun()

# ── MAIN COMPONENT TABS ───────────────────────────────────────────────────────
tab_gen, tab_variance, tab_heatmap, tab_delivery = st.tabs([
    "📝 Victim Report Generator (Component 1)",
    "⚡ Risk Engine: Variance Model (Component 2a)",
    "🗺️ Risk Heatmap: Prediction Model (Component 2b)",
    "📢 Delivery & Action Routing (Component 4)",
])

# ==============================================================================
# TAB 1: VICTIM REPORT GENERATOR
# ==============================================================================
with tab_gen:
    st.subheader("📨 Latest SMS Prompts (for Risk Management Agent)")
    if st.session_state.last_events:
        tabs = st.tabs([
            f"{'🔴' if e.get('risk_label') == 'CRITICAL' else '🟠' if e.get('risk_label') == 'HIGH' else '🟡' if e.get('risk_label') == 'MEDIUM' else '🟢'} "
            f"{e.get('attacker', {}).get('attacker_id', e.get('complaint_id', f'Event {i+1}'))}"
            for i, e in enumerate(st.session_state.last_events)
        ])
        for tab, event in zip(tabs, st.session_state.last_events):
            with tab:
                label = event.get("risk_label", "?")
                score = event.get("risk_score", 0)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Risk Label", label)
                m2.metric("Risk Score", f"{score:.2f}")
                m3.metric("ATM City", event.get("atm", {}).get("city", "?"))
                m4.metric("Amount (INR)", f"₹{event.get('total_amount_inr', 0):,.0f}")
                st.markdown('<div class="sms-box">' + event.get("sms_prompt", "No prompt").replace("\n", "<br>") + "</div>", unsafe_allow_html=True)
                with st.expander("📋 Full Event JSON"):
                    st.json(event)
    else:
        st.info("No events yet. Click **▶ Run One Cycle Now** or **▶ START** to generate.")

    st.subheader(f"📊 Live Event Log ({store.count()} events)")
    all_events = store.get_all()
    if all_events:
        rows = []
        for e in reversed(all_events):
            atm = e.get("atm", {})
            prf = e.get("attacker", {})
            rows.append({
                "Complaint ID":   e.get("complaint_id", "?"),
                "Generated At":   e.get("generated_at", "?")[:19].replace("T", " "),
                "Attacker ID":    prf.get("attacker_id", "?"),
                "Modus":          prf.get("modus_operandi", "?"),
                "Victim State":   e.get("victim_state", "?"),
                "Amount (INR)":   f"₹{e.get('total_amount_inr', 0):,.0f}",
                "ATM City":       atm.get("city", "?"),
                "ATM State":      atm.get("state", "?"),
                "Bank":           atm.get("bank", "?"),
                "Chain Depth":    e.get("mule_chain_depth", "?"),
                "Score":          e.get("risk_score", 0),
            })
        df = pd.DataFrame(rows, index=range(1, len(rows) + 1))
        st.dataframe(df, use_container_width=True, height=350)

        csv = df.to_csv(index=False)
        st.download_button("⬇️ Export CSV", csv, "pafcci_events.csv", "text/csv")
    else:
        st.info("Event log is empty. Generate some events to populate it.")

# ==============================================================================
# TAB 2: RISK ENGINE — VARIANCE MODEL (COMPONENT 2)
# ==============================================================================
with tab_variance:
    st.subheader("⚡ Risk Engine — Variance Model Anomaly Detection")
    st.caption(
        "Detects anomalous patterns across 3 independent deterministic signals: "
        "**IP/Phone Mismatch**, **Deposit Spikes**, **IP Velocity**. "
        "Select any flagged entity to inspect its individual behavior timeline."
    )

    all_current_events = store.get_all()

    if not all_current_events:
        st.info("No complaint data in memory yet. Click **▶ Run One Cycle Now** or **▶ START** to populate the stream.")
    else:
        _cur_cycle = st.session_state.cycle_count
        _cur_event_count = len(all_current_events)
        if (
            st.session_state.cached_var_res is None
            or st.session_state.cache_cycle_count != _cur_cycle
            or getattr(st.session_state, "cached_event_count", -1) != _cur_event_count
            or use_llm
        ):
            variance_results = run_variance_analysis(all_current_events, use_llm=use_llm)
            if not use_llm:
                st.session_state.cached_var_res = variance_results
                st.session_state.cache_cycle_count = _cur_cycle
                st.session_state.cached_event_count = _cur_event_count
        else:
            variance_results = st.session_state.cached_var_res

        stats = variance_results["summary_stats"]
        aggregated = variance_results["aggregated_entities"]
        raw_signals = variance_results["raw_signals"]

        # ── Overview Metrics ──────────────────────────────────────────────────
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Events Analyzed", stats["total_events_analyzed"])
        m2.metric("Signals Triggered", stats["total_signals_triggered"])
        m3.metric("IP/Phone Mismatches", stats["signals_by_type"]["ip_phone_mismatch"])
        m4.metric("Deposit Spikes", stats["signals_by_type"]["deposit_spike"])
        m5.metric("Velocity Anomalies", stats["signals_by_type"]["ip_velocity"])

        st.divider()

        if not aggregated:
            st.success("✅ No anomalous patterns detected in current stream window. All entities within baseline bounds.")
        else:
            # ── Section 1: Ranked Entity List ─────────────────────────────────
            st.subheader(f"🚩 Flagged Entities ({len(aggregated)} total — sorted by confidence)")

            # Build ranked dropdown options — sorted high to low confidence
            def risk_badge(score):
                if score >= 0.85: return "🔴 CRITICAL"
                if score >= 0.70: return "🟠 HIGH"
                if score >= 0.50: return "🟡 MEDIUM"
                return "🟢 LOW"

            entity_options = [
                f"{risk_badge(item['combined_score'])} | {item['entity_type'].upper():8} | "
                f"Conf: {item['confidence']:.2f} | Score: {item['combined_score']:.3f} | "
                f"{item['entity_id']} [{', '.join(item['signal_names'])}]"
                for item in aggregated
            ]

            selected_label = st.selectbox(
                "🔎 Select entity to inspect (sorted: highest confidence → lowest):",
                entity_options,
                index=0,
            )
            selected_index = entity_options.index(selected_label)
            selected = aggregated[selected_index]

            # ── Section 2: Selected Entity Detailed Card ──────────────────────
            score = selected["combined_score"]
            conf = selected["confidence"]
            badge = risk_badge(score)

            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("Entity ID", selected["entity_id"])
            col_b.metric("Entity Type", selected["entity_type"].upper())
            col_c.metric("Combined Score", f"{score:.3f}")
            col_d.metric("Confidence", f"{conf:.2f}")

            st.caption(f"**Signals fired:** {', '.join(selected['signal_names'])} &nbsp;|&nbsp; **Explanation:** {selected['explanation_summary']}")

            st.divider()

            # ── Section 3: Single-Entity Behavior Chart ───────────────────────
            # Find the first deposit_spike signal for this entity (has transaction history)
            deposit_sig = next(
                (s for s in selected["signals_triggered"] if s["signal_type"] == "deposit_spike"),
                None,
            )
            velocity_sig = next(
                (s for s in selected["signals_triggered"] if s["signal_type"] == "ip_velocity"),
                None,
            )
            mismatch_sig = next(
                (s for s in selected["signals_triggered"] if s["signal_type"] == "ip_phone_mismatch"),
                None,
            )

            if deposit_sig:
                ev = deposit_sig["evidence"]
                amounts = ev.get("deposit_history", [])
                timestamps = ev.get("deposit_timestamps", [])
                spike_idx = ev.get("spike_index", len(amounts) - 1)
                baseline_mean = ev.get("baseline_mean_inr", 0)
                baseline_std = ev.get("baseline_std_dev_inr", 0)
                z_score = ev.get("z_score", 0)
                z_thresh = ev.get("z_threshold", 2.5)

                st.subheader(f"📈 Deposit Behavior Timeline — {selected['entity_id']}")
                st.caption(
                    f"Baseline mean: **₹{baseline_mean:,.0f}** | "
                    f"Std deviation: **₹{baseline_std:,.0f}** | "
                    f"Spike z-score: **{z_score:.2f}** (threshold: {z_thresh}) | "
                    f"Transactions: **{len(amounts)}**"
                )

                if len(amounts) >= 2:
                    chart_data = pd.DataFrame(
                        {
                            "Transaction Amount (INR)": amounts,
                            "Baseline Mean": [baseline_mean] * len(amounts),
                            f"Alert Threshold (z={z_thresh})": [baseline_mean + z_thresh * baseline_std] * len(amounts),
                        },
                        index=range(1, len(amounts) + 1),   # x-axis: Txn 1, 2, 3...
                    )
                    st.line_chart(chart_data, use_container_width=True, height=300)

                    # Highlight spike point
                    st.markdown(
                        f"🔴 **Spike detected at transaction #{spike_idx + 1}**: "
                        f"₹{amounts[spike_idx]:,.2f} — "
                        f"**{z_score:.1f}× standard deviations above baseline**"
                    )
                else:
                    # Single-transaction absolute threshold flag
                    chart_data = pd.DataFrame(
                        {
                            "Deposit Amount (INR)": amounts,
                            "Absolute Alert Threshold": [350_000.0] * len(amounts),
                        },
                        index=range(1, len(amounts) + 1),
                    )
                    st.bar_chart(chart_data, use_container_width=True, height=200)
                    st.warning(f"⚠️ Single large deposit of ₹{amounts[0]:,.2f} exceeds absolute threshold of ₹3,50,000.")

            if velocity_sig:
                ev = velocity_sig["evidence"]
                st.subheader(f"🌐 IP Velocity Anomaly — {selected['entity_id']}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Speed", f"{ev.get('calculated_speed_kmh', 0):,.0f} km/h")
                col2.metric("Max Allowed", f"{ev.get('max_allowed_speed_kmh', 900):,.0f} km/h")
                col3.metric("Distance", f"{ev.get('distance_km', 0):,.0f} km")
                col4.metric("Time Elapsed", f"{ev.get('time_elapsed_minutes', 0):.1f} min")
                st.markdown(
                    f"📍 **Origin:** {ev.get('origin_location', '?')}  \n"
                    f"📍 **Destination:** {ev.get('destination_location', '?')}  \n"
                    f"⚡ **Effective speed {ev.get('calculated_speed_kmh', 0):,.0f} km/h exceeds max commercial flight speed "
                    f"of {ev.get('max_allowed_speed_kmh', 900)} km/h** — proxy/VPN hop detected."
                )

            if mismatch_sig:
                ev = mismatch_sig["evidence"]
                st.subheader(f"📵 IP/Phone Binding Anomaly — {selected['entity_id']}")
                col1, col2 = st.columns(2)
                if "distinct_ip_count" in ev:
                    col1.metric("Distinct IPs seen", ev["distinct_ip_count"])
                    col2.metric("Max Allowed", ev["max_allowed_ips"])
                    st.markdown(f"**Associated IPs:** `{ev.get('associated_ips', [])}`")
                    if ev.get("detected_vpn_providers"):
                        st.markdown(f"**VPN Providers detected:** `{ev['detected_vpn_providers']}`")
                else:
                    col1.metric("Distinct Phones seen", ev["distinct_phone_count"])
                    col2.metric("Max Allowed", ev["max_allowed_phones"])
                    st.markdown(f"**Associated Phones:** `{ev.get('associated_phones', [])}`")

            st.divider()

            # ── Section 4: Full Ranked Table ──────────────────────────────────
            with st.expander("📊 View All Flagged Entities Table"):
                agg_rows = []
                for item in aggregated:
                    s = item["combined_score"]
                    label = "CRITICAL" if s >= 0.85 else "HIGH" if s >= 0.70 else "MEDIUM" if s >= 0.50 else "LOW"
                    agg_rows.append({
                        "Entity ID":        item["entity_id"],
                        "Type":             item["entity_type"].upper(),
                        "Signals":          ", ".join(item["signal_names"]),
                        "# Signals":        item["distinct_signals_count"],
                        "Combined Score":   f"{s:.3f}",
                        "Confidence":       f"{item['confidence']:.2f}",
                        "Risk Level":       label,
                    })
                df_agg = pd.DataFrame(agg_rows, index=range(1, len(agg_rows) + 1))

                def colour_var_risk(val):
                    return {
                        "CRITICAL": "background-color:#4d0000;color:#ff4b4b",
                        "HIGH":     "background-color:#4d2200;color:#ff8800",
                        "MEDIUM":   "background-color:#4d4400;color:#ffd700",
                        "LOW":      "background-color:#004d33;color:#00cc88",
                    }.get(val, "")

                st.dataframe(df_agg.style.map(colour_var_risk, subset=["Risk Level"]),
                             use_container_width=True, height=300)
                csv_agg = df_agg.to_csv(index=False)
                st.download_button("⬇️ Export Flagged Entities CSV", csv_agg, "pafcci_variance_flagged.csv", "text/csv")

            # ── Section 5: Raw Signal Evidence ────────────────────────────────
            with st.expander("🔍 Raw Forensic Evidence — Selected Entity"):
                for sig in selected["signals_triggered"]:
                    st.markdown(f"**Signal:** `{sig['signal_type']}` | **Sub-score:** `{sig['sub_score']:.3f}`")
                    evidence_display = {k: v for k, v in sig["evidence"].items()
                                        if k not in ("deposit_history", "deposit_timestamps")}
                    st.json(evidence_display)

# ==============================================================================
# TAB 3: RISK HEATMAP — PREDICTION MODEL (COMPONENT 2b)
# ==============================================================================
with tab_heatmap:
    st.subheader("🗺️ Risk Heatmap — ATM Withdrawal Prediction")
    st.caption(
        "Markov-chain predictions of next likely withdrawal locations from variance-flagged entities. "
        "**Hover** over a dot to see Bank & Location. **Click** a dot to open the prediction console."
    )

    _heatmap_events = store.get_all()

    if not _heatmap_events:
        st.info("No complaint data in memory yet. Generate events first, then return to this tab.")
    else:
        # ── Run prediction analysis ────────────────────────────────────────────
        _var_for_pred = st.session_state.cached_var_res or run_variance_analysis(_heatmap_events, use_llm=False)
        _aggregated_for_pred = _var_for_pred.get("aggregated_entities", [])

        # ── Sidebar-synced filters ─────────────────────────────────────────────
        from generator.data.atm_locations import list_states as _list_states
        _all_states     = ["All"] + sorted(_list_states())
        _all_categories = ["All Categories",
                           "deposit_spike", "ip_phone_mismatch", "ip_velocity"]

        fcol1, fcol2, fcol3 = st.columns(3)
        with fcol1:
            _state_sel = st.selectbox("🌍 Filter by State", _all_states, key="hm_state")
        with fcol2:
            _cat_sel = st.selectbox("🔍 Filter by Signal Type", _all_categories, key="hm_cat")
        with fcol3:
            _min_risk = st.selectbox("⚠️ Min Risk Level",
                                     ["LOW", "MEDIUM", "HIGH", "CRITICAL"], key="hm_risk")

        _filter_params = {
            "state_filter":          None if _state_sel == "All" else _state_sel,
            "crime_category_filter": None if _cat_sel == "All Categories" else _cat_sel,
            "min_risk_level":        _min_risk,
        }

        # ── Run prediction model ───────────────────────────────────────────────
        _pred_result = run_prediction_analysis(
            variance_results=_var_for_pred,
            events=_heatmap_events,
            use_llm=False,
            filter_params=_filter_params,
        )
        _heatmap_records = _pred_result["heatmap_records"]
        _pred_stats      = _pred_result["summary_stats"]

        # ── Summary metrics ────────────────────────────────────────────────────
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Entities Analysed",  _pred_stats["total_entities_predicted"])
        mc2.metric("ATMs at Risk",        _pred_stats["heatmap_locations"])
        mc3.metric("🔴 CRITICAL",         _pred_stats["critical_locations"])
        mc4.metric("🟠 HIGH",             _pred_stats["high_locations"])

        st.divider()

        if not _heatmap_records:
            st.info("No ATM locations meet the current filter criteria. Try lowering the Min Risk Level.")
        else:
            # ── ATM selector (for click-to-console) ───────────────────────────
            _atm_options = {
                f"{'🔴' if r['risk_level']=='CRITICAL' else '🟠' if r['risk_level']=='HIGH' else '🟡' if r['risk_level']=='MEDIUM' else '🟢'} "
                f"{r['bank']}, {r['city']} ({r['atm_id']})": r
                for r in _heatmap_records
            }

            _sel_label = st.selectbox(
                "🖱️ Select ATM to open prediction console (or click dot on map below)",
                list(_atm_options.keys()),
                key="hm_atm_sel",
            )
            _selected_hm = _atm_options[_sel_label]

            # ── Console-style prediction panel ────────────────────────────────
            _risk_colors_css = {
                "CRITICAL": "#ff4b4b", "HIGH": "#ff8800",
                "MEDIUM": "#ffd700",   "LOW": "#00cc88",
            }
            _rl  = _selected_hm["risk_level"]
            _col = _risk_colors_css[_rl]

            _window_str = _selected_hm.get("time_bucket", "Calculating...")
            _cats_str = ", ".join(_selected_hm.get("crime_categories", [])) or "Mixed"

            _console_text = (
                f"{'='*60}\n"
                f"  PAFCCI WITHDRAWAL PREDICTION CONSOLE\n"
                f"{'='*60}\n"
                f"  ATM ID         : {_selected_hm['atm_id']}\n"
                f"  Bank           : {_selected_hm['bank']}\n"
                f"  ATM Type       : {_selected_hm['atm_type']}\n"
                f"  Location       : {_selected_hm['location_label']}\n"
                f"  City           : {_selected_hm['city']}\n"
                f"  State          : {_selected_hm['state']}\n"
                f"  Coordinates    : {_selected_hm['lat']:.6f}°N, {_selected_hm['lon']:.6f}°E\n"
                f"{'─'*60}\n"
                f"  RISK LEVEL     : {_rl}\n"
                f"  RISK SCORE     : {_selected_hm['risk_score']:.3f} / 1.000\n"
                f"  SIGNAL TYPES   : {_cats_str}\n"
                f"  ENTITIES LINKED: {_selected_hm['entity_count']}\n"
                f"  ENTITY IDs     : {', '.join(_selected_hm['entity_ids'][:5])}\n"
                f"{'─'*60}\n"
                f"  PREDICTED WINDOW\n"
                f"  {_window_str}\n"
                f"{'─'*60}\n"
                f"  WHY FLAGGED\n"
                f"  {_selected_hm['why_flagged']}\n"
                f"{'='*60}\n"
            )

            st.markdown(
                f"<div style='background:#0d1117;border:1px solid {_col};"
                f"border-left:4px solid {_col};border-radius:6px;padding:14px;"
                f"font-family:\"Courier New\",monospace;font-size:12px;color:#e0e0e0;"
                f"white-space:pre;overflow-x:auto;'>{_console_text}</div>",
                unsafe_allow_html=True,
            )

            st.divider()

            # ── pydeck Map ────────────────────────────────────────────────────
            st.markdown("#### 🗺️ ATM Risk Heatmap")

            _map_df = pd.DataFrame([
                {
                    "atm_id":        r["atm_id"],
                    "lat":           r["lat"],
                    "lon":           r["lon"],
                    "bank":          r["bank"],
                    "city":          r["city"],
                    "state":         r["state"],
                    "risk_level":    r["risk_level"],
                    "risk_score":    r["risk_score"],
                    "tooltip_label": r["tooltip_label"],   # "Bank, City"
                    "color_r":       r["color"][0],
                    "color_g":       r["color"][1],
                    "color_b":       r["color"][2],
                    "color_a":       r["color"][3],
                    # Pinpoint dot radius in pixels (8px to 12px)
                    "pixel_radius":  round(8 + r["risk_score"] * 4, 1),
                }
                for r in _heatmap_records
            ])

            _scatter_layer = pdk.Layer(
                "ScatterplotLayer",
                data=_map_df,
                get_position=["lon", "lat"],
                get_fill_color=["color_r", "color_g", "color_b", "color_a"],
                get_radius="pixel_radius",
                radius_units="pixels",
                radius_min_pixels=6,
                radius_max_pixels=14,
                stroked=True,
                get_line_color=[0, 0, 0, 220],
                line_width_min_pixels=1.5,
                pickable=True,
                auto_highlight=True,
                highlight_color=[255, 255, 255, 120],
            )

            # Auto-center map on average coordinates of current flagged ATMs
            _avg_lat = float(_map_df["lat"].mean()) if not _map_df.empty else 20.5937
            _avg_lon = float(_map_df["lon"].mean()) if not _map_df.empty else 78.9629
            _zoom    = 4.5 if _state_sel == "All" else 7.0

            _view = pdk.ViewState(
                latitude=_avg_lat,
                longitude=_avg_lon,
                zoom=_zoom,
                pitch=0,
            )

            _deck = pdk.Deck(
                layers=[_scatter_layer],
                initial_view_state=_view,
                tooltip={"text": "{tooltip_label}\nRisk: {risk_level}"},
                map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
            )

            st.pydeck_chart(_deck, use_container_width=True, height=480)

            # ── Legend ────────────────────────────────────────────────────────
            leg1, leg2, leg3, leg4 = st.columns(4)
            leg1.markdown("🟢 **LOW** — baseline / cold-start")
            leg2.markdown("🟡 **MEDIUM** — moderate pattern")
            leg3.markdown("🟠 **HIGH** — strong signal")
            leg4.markdown("🔴 **CRITICAL** — convergent evidence")

            st.divider()

            # ── Ranked ATM Table ──────────────────────────────────────────────
            with st.expander("📊 Ranked ATM Risk Table", expanded=True):
                _tbl_rows = []
                for i, r in enumerate(_heatmap_records, start=1):
                    _tbl_rows.append({
                        "#":          i,
                        "ATM ID":     r["atm_id"],
                        "Bank":       r["bank"],
                        "City":       r["city"],
                        "State":      r["state"],
                        "Risk Level": r["risk_level"],
                        "Risk Score": f"{r['risk_score']:.3f}",
                        "Entities":   r["entity_count"],
                        "Time Window": r["time_bucket"],
                    })
                _df_tbl = pd.DataFrame(_tbl_rows).set_index("#")

                def _colour_rl(val):
                    return {
                        "CRITICAL": "background-color:#4d0000;color:#ff4b4b",
                        "HIGH":     "background-color:#4d2200;color:#ff8800",
                        "MEDIUM":   "background-color:#4d4400;color:#ffd700",
                        "LOW":      "background-color:#004d33;color:#00cc88",
                    }.get(val, "")

                st.dataframe(
                    _df_tbl.style.map(_colour_rl, subset=["Risk Level"]),
                    use_container_width=True, height=350,
                )
                st.download_button(
                    "⬇️ Export Heatmap CSV",
                    _df_tbl.to_csv(index=False),
                    "pafcci_heatmap.csv",
                    "text/csv",
                )

            # ── Audit Log (internal — password gated) ─────────────────────────
            with st.expander("🔒 Internal Audit Log (Authorised Reviewers Only)"):
                _pwd = st.text_input("Enter access code", type="password", key="hm_audit_pwd")
                if _pwd == "audit":
                    _audit_entries = get_audit_log().get_recent(30)
                    if _audit_entries:
                        st.caption(f"Showing last {len(_audit_entries)} recalibration entries.")
                        st.json(_audit_entries)
                    else:
                        st.info("No recalibration events yet. Log an actual withdrawal to populate.")
                elif _pwd:
                    st.error("Access denied.")

# ==============================================================================
# TAB 4: DELIVERY MODEL & ACTION ROUTING (COMPONENT 4)
# ==============================================================================
with tab_delivery:
    st.subheader("📢 Delivery Model & Action Routing")
    st.caption(
        "Deterministic routing of Risk Engine output to downstream recipient channels: "
        "Civilian Safety Advisories, Cyber Crime Authority Manual Review Queues, and Bank Fraud Queues. "
        "Mandates human review for entity actions and enforces transparent recourse appeal paths."
    )

    _deliv_events = store.get_all()

    if not _deliv_events:
        st.info("No complaint data in memory yet. Run generation cycles first to populate routing queues.")
    else:
        # Controls
        dcol1, dcol2 = st.columns(2)
        with dcol1:
            _reg_thresh = st.slider("Civilian Alert Regional Risk Threshold",
                                    min_value=0.50, max_value=0.95, value=0.75, step=0.05,
                                    help="Minimum regional risk score required to trigger civilian safety advisory.")
        with dcol2:
            _cooldown_h = st.number_input("Civilian Cooldown Window (Hours)",
                                          min_value=1, max_value=72, value=24, step=1,
                                          help="Prevents repeated regional alerts within this window to avoid alert fatigue.")

        # Re-use cached analysis results if cycle and event count match (eliminates hanging)
        _cur_cycle = st.session_state.cycle_count
        _cur_event_count = len(_deliv_events)
        _deliv_params_key = (_cur_cycle, _cur_event_count, _reg_thresh, _cooldown_h)

        if (
            st.session_state.cached_var_res is None
            or st.session_state.cache_cycle_count != _cur_cycle
            or getattr(st.session_state, "cached_event_count", -1) != _cur_event_count
        ):
            st.session_state.cached_var_res = run_variance_analysis(_deliv_events, use_llm=False)
            st.session_state.cache_cycle_count = _cur_cycle
            st.session_state.cached_event_count = _cur_event_count

        if (
            st.session_state.cached_pred_res is None
            or st.session_state.get("cached_pred_cycle", -1) != _cur_cycle
            or getattr(st.session_state, "cached_event_count", -1) != _cur_event_count
        ):
            st.session_state.cached_pred_res = run_prediction_analysis(
                st.session_state.cached_var_res, _deliv_events, use_llm=False
            )
            st.session_state.cached_pred_cycle = _cur_cycle

        if (
            st.session_state.cached_deliv_res is None
            or getattr(st.session_state, "cached_deliv_params", None) != _deliv_params_key
        ):
            st.session_state.cached_deliv_res = run_delivery_routing(
                variance_results=st.session_state.cached_var_res,
                prediction_results=st.session_state.cached_pred_res,
                use_llm=False,
                regional_threshold=_reg_thresh,
                cooldown_minutes=int(_cooldown_h * 60),
            )
            st.session_state.cached_deliv_params = _deliv_params_key

        _delivery_res = st.session_state.cached_deliv_res
        _civ_alerts   = _delivery_res["civilian_alerts"]
        _appeals_mgr  = get_appeals_manager()
        _live_auth_all = _appeals_mgr.get_by_recipient("authority")
        _live_bank_all = _appeals_mgr.get_by_recipient("bank")
        _distinct_banks = len({b.get("bank_name") for b in _live_bank_all if b.get("bank_name")})

        # ── Metrics Bar ────────────────────────────────────────────────────────
        dm1, dm2, dm3, dm4 = st.columns(4)
        dm1.metric("📢 Civilian Advisories", len(_civ_alerts))
        dm2.metric("🛡️ Authority Items Queued", len(_live_auth_all))
        dm3.metric("🏦 Bank Items Queued",      len(_live_bank_all))
        dm4.metric("🏛️ Active Bank Queues",    _distinct_banks)

        st.divider()

        # ── Authoritative Session & OTP Gate ──────────────────────────────────
        _cur_officer = st.session_state.dm_auth_officer

        # Verify active lock with bridge
        if _cur_officer:
            if get_user_status(_cur_officer["username"]) != "ONLINE":
                _cur_officer = None
                st.session_state.dm_auth_officer = None
                st.session_state.dm_staged_actions = []

        if not _cur_officer:
            st.markdown(
                """
                <div style='background:#111c2e;border:1px solid #3b82f6;border-left:5px solid #3b82f6;padding:12px 18px;border-radius:8px;margin-bottom:12px;'>
                    <h5 style='margin:0 0 4px 0;color:#60a5fa;'>🔐 Action Routing & Delivery Audit — Authoritative Access Required</h5>
                    <p style='margin:0;font-size:0.86rem;color:#cbd5e1;'>
                        Executing actions (Block, Whitelist, Debit Freeze) and inspecting Delivery Audit requires an active one-time password (OTP) generated from the <b>Cyber Portal (Port 8502)</b>.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.expander("🔑 Unlock Action Routing with Cyber Portal OTP", expanded=True):
                col_u1, col_u2, col_u3 = st.columns([2, 1.5, 1.5])
                with col_u1:
                    _auth_user_keys = list(AUTHORITY_USERS.keys())
                    _chosen_auth_user = st.selectbox(
                        "Select Authority Officer",
                        options=_auth_user_keys,
                        format_func=lambda k: f"{AUTHORITY_USERS[k]['name']} ({AUTHORITY_USERS[k]['role']})",
                        key="dm_auth_user_select",
                    )
                with col_u2:
                    _entered_otp = st.text_input("Enter 6-Digit OTP from Cyber Portal", placeholder="e.g. 842109", max_chars=6, key="dm_otp_input")
                with col_u3:
                    st.markdown("<div style='padding-top:28px;'></div>", unsafe_allow_html=True)
                    _unlock_btn = st.button("🔓 Authenticate OTP", type="primary", use_container_width=True, key="dm_unlock_btn")

                if _unlock_btn:
                    if not _entered_otp.strip():
                        st.error("Please enter the 6-digit OTP code.")
                    else:
                        try:
                            auth_res = verify_and_claim_otp(_chosen_auth_user, _entered_otp.strip())
                            st.session_state.dm_auth_officer = auth_res
                            st.session_state.dm_staged_actions = []
                            st.session_state.dm_show_signout_confirm = False
                            st.success(f"Authenticated as {auth_res['name']}! Action routing unlocked.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Authentication Failed: {exc}")

                st.caption("💡 Don't have an active OTP? Open the Cyber Portal at [http://localhost:8502](http://localhost:8502), select your officer profile, and click 'Generate OTP'.")
        else:
            # Active authenticated session bar
            st.markdown(
                f"""
                <div style='background:#064e3b;border:1px solid #00cc88;border-left:5px solid #00cc88;padding:12px 18px;border-radius:8px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;'>
                    <div>
                        <span style='color:#00ffaa;font-weight:bold;font-size:1.05rem;'>🟢 {_cur_officer['name']}</span>
                        <span style='color:#cbd5e1;font-size:0.88rem;margin-left:8px;'>({_cur_officer['role']} · {_cur_officer['badge_id']})</span>
                    </div>
                    <div>
                        <span style='background:#0f2b1d;color:#a7f3d0;padding:4px 10px;border-radius:6px;font-size:0.85rem;border:1px solid #00cc88;'>
                            Uncommitted Actions: <b>{len(st.session_state.dm_staged_actions)}</b>
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Controls: Commit & Sign Out
            scol_a, scol_b, scol_c = st.columns([2, 1, 1])
            with scol_a:
                if len(st.session_state.dm_staged_actions) > 0:
                    st.caption(f"⚠️ You have {len(st.session_state.dm_staged_actions)} staged action(s). Commit to record to local CSV.")
                else:
                    st.caption("Ready. Executed actions will stage here before committing.")
            with scol_b:
                if st.button("💾 Commit Changes", type="primary", use_container_width=True, key="dm_commit_btn"):
                    if len(st.session_state.dm_staged_actions) == 0:
                        st.info("No uncommitted actions to commit.")
                    else:
                        cnt = commit_authority_actions(_cur_officer["name"], st.session_state.dm_staged_actions)
                        st.session_state.dm_staged_actions = []
                        st.success(f"Successfully committed {cnt} action(s) to cyber_portal_authority_actions.csv!")
                        st.rerun()
            with scol_c:
                if st.button("🚪 Sign Out", type="secondary", use_container_width=True, key="dm_signout_init_btn"):
                    if len(st.session_state.dm_staged_actions) > 0:
                        st.session_state.dm_show_signout_confirm = True
                        st.rerun()
                    else:
                        sign_out_user(_cur_officer["username"], commit_staged=False)
                        st.session_state.dm_auth_officer = None
                        st.session_state.dm_staged_actions = []
                        st.session_state.dm_show_signout_confirm = False
                        st.info("Session ended and OTP invalidated.")
                        st.rerun()

            # Confirmation Dialog if signing out with uncommitted changes
            if st.session_state.dm_show_signout_confirm:
                st.warning(
                    f"⚠️ **Do you want to commit changes?**\n\n"
                    f"You have **{len(st.session_state.dm_staged_actions)}** uncommitted action(s) in this session. "
                    "Signing out without committing will discard these staged decisions."
                )
                cf_col1, cf_col2 = st.columns(2)
                with cf_col1:
                    if st.button("Yes", type="primary", use_container_width=True, key="confirm_signout_yes"):
                        sign_out_user(
                            _cur_officer["username"],
                            commit_staged=True,
                            staged_actions=st.session_state.dm_staged_actions,
                        )
                        st.session_state.dm_auth_officer = None
                        st.session_state.dm_staged_actions = []
                        st.session_state.dm_show_signout_confirm = False
                        st.success("Changes committed to CSV and session closed.")
                        st.rerun()
                with cf_col2:
                    if st.button("No", type="secondary", use_container_width=True, key="confirm_signout_no"):
                        sign_out_user(
                            _cur_officer["username"],
                            commit_staged=False,
                        )
                        st.session_state.dm_auth_officer = None
                        st.session_state.dm_staged_actions = []
                        st.session_state.dm_show_signout_confirm = False
                        st.info("Changes discarded and session closed.")
                        st.rerun()

        # ── Delivery Sub-tabs ──────────────────────────────────────────────────
        dtab_civ, dtab_auth, dtab_bank, dtab_appeal = st.tabs([
            "📢 Civilian Advisories",
            "🛡️ Authority Review Queue (Phone/IP)",
            "🏦 Bank Fraud Queues",
            "⚖️ Recourse & Appeals Console",
        ])

        # ── Sub-tab 1: Civilian Advisories ─────────────────────────────────────
        with dtab_civ:
            st.markdown("#### 📢 Regional Civilian Safety Advisories")
            st.caption(
                "Issued only when regional aggregate risk exceeds threshold. "
                "**STRICT PRIVACY GUARANTEE**: Contains generic regional guidance only — NO phone numbers, IPs, or accounts."
            )
            if not _civ_alerts:
                st.info("No regions currently exceed the regional risk threshold, or alerts are currently suppressed by active 24h cooldown.")
            else:
                for alert in _civ_alerts:
                    st.markdown(
                        f"<div style='background:#121d33;border-left:5px solid #ff8800;"
                        f"padding:14px;border-radius:6px;margin-bottom:12px;'>"
                        f"<h5 style='margin:0 0 8px 0;color:#ff8800;'>{alert['region']} (Regional Risk Score: {alert['regional_risk_score']:.3f})</h5>"
                        f"<pre style='font-family:monospace;white-space:pre-wrap;color:#e0e0e0;margin:0;'>{alert['alert_text']}</pre>"
                        f"<div style='margin-top:8px;font-size:11px;color:#888;'>"
                        f"🔒 Privacy Guard: No per-entity data disclosed · ⏱️ 24h Cooldown Active until {(datetime.now(IST)+timedelta(hours=24)).strftime('%H:%M IST')}"
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )

        # ── Sub-tab 2: Authority Queue (Phone/IP) — Sliding Table Layout ────────
        with dtab_auth:
            st.markdown("#### 🛡️ Cyber Crime Authority — Manual Review Queue")
            st.caption("MANDATORY HUMAN REVIEW: Review queued entities in the sliding matrix (columns 1 to N). Select a column below to inspect forensic evidence and record an officer action.")

            _live_auth_items = _appeals_mgr.get_by_recipient("authority")

            if not _live_auth_items:
                st.info("No phone or IP entities currently queued for authority review.")
            else:
                # Top Filter & Status Counters
                fcol1, fcol2, fcol3 = st.columns([2, 2, 3])
                with fcol1:
                    _status_filter = st.selectbox(
                        "Status Filter",
                        ["All Statuses", "pending_review", "appealed", "actioned", "dismissed", "resolved"],
                        key="auth_st_filter",
                    )
                with fcol2:
                    _type_filter = st.selectbox(
                        "Entity Type",
                        ["All Types", "phone", "ip"],
                        key="auth_type_filter",
                    )
                with fcol3:
                    p_count = sum(1 for i in _live_auth_items if i["status"] == "pending_review")
                    a_count = sum(1 for i in _live_auth_items if i["status"] == "appealed")
                    d_count = sum(1 for i in _live_auth_items if i["status"] in ("actioned", "dismissed", "resolved"))
                    st.markdown(
                        f"<div style='padding-top:24px;font-size:12px;'>"
                        f"🔴 <b>Pending:</b> {p_count} &nbsp;|&nbsp; "
                        f"⚖️ <b>Appealed:</b> {a_count} &nbsp;|&nbsp; "
                        f"✅ <b>Completed:</b> {d_count}</div>",
                        unsafe_allow_html=True,
                    )

                # Filter and rank items
                _filtered_items = list(_live_auth_items)
                if _status_filter != "All Statuses":
                    _filtered_items = [i for i in _filtered_items if i["status"] == _status_filter]
                if _type_filter != "All Types":
                    _filtered_items = [i for i in _filtered_items if i["entity_type"] == _type_filter]

                # Sort descending by risk score
                _filtered_items = sorted(_filtered_items, key=lambda x: x.get("risk_level", 0.0), reverse=True)

                if not _filtered_items:
                    st.info("No queued items match the selected filters.")
                else:
                    N_auth = len(_filtered_items)

                    # Build Sliding Table Data (Row headers stay fixed, Column headers are Tracker IDs)
                    auth_row_labels = [
                        "Entity ID",
                        "Entity Type",
                        "Current Status",
                        "Risk Score",
                        "Risk Level",
                        "Region",
                        "Dispute Filed?",
                        "Signals Triggered",
                        "Registered At",
                    ]

                    auth_col_data = {}
                    for idx, item in enumerate(_filtered_items):
                        col_key = item["tracking_id"]
                        st_raw = item["status"]
                        st_display = (
                            "🔴 PENDING_REVIEW" if st_raw == "pending_review" else
                            "⚖️ APPEALED" if st_raw == "appealed" else
                            "✅ ACTIONED" if st_raw == "actioned" else
                            "⚪ DISMISSED" if st_raw == "dismissed" else
                            "✅ RESOLVED" if st_raw == "resolved" else st_raw.upper()
                        )
                        r_score = item.get("risk_level", 0.0)
                        r_level = "CRITICAL" if r_score >= 0.85 else "HIGH" if r_score >= 0.70 else "MEDIUM"
                        sig_names = ", ".join(s.get("signal_type", "") for s in item.get("signals_triggered", []))
                        disp_str = f"⚠️ YES ({item.get('advocate_name', 'Filer')})" if item.get("dispute_reason") else "None"
                        auth_col_data[col_key] = [
                            item["entity_id"],
                            item["entity_type"].upper(),
                            st_display,
                            f"{r_score:.3f}",
                            r_level,
                            item.get("region", "India Nationwide"),
                            disp_str,
                            sig_names or "None",
                            item.get("created_at", "")[:19].replace("T", " "),
                        ]

                    df_sliding_auth = pd.DataFrame(auth_col_data, index=auth_row_labels)

                    st.markdown(f"##### 📊 Review Matrix by Tracker ID ({N_auth} Entities)")
                    st.caption("👈 Use horizontal scrollbar to slide across Tracker IDs. Click any column or Tracker ID to inspect forensic details and take officer action.")
                    df_auth_selected = st.dataframe(
                        df_sliding_auth,
                        on_select="rerun",
                        selection_mode="single-column",
                        use_container_width=True,
                        height=280,
                        key="auth_df_matrix",
                    )

                    # Determine selected Tracker ID from column click or session state default
                    _auth_trk_list = [x["tracking_id"] for x in _filtered_items]
                    _clicked_auth_trk = None
                    if df_auth_selected:
                        sel = getattr(df_auth_selected, "selection", None)
                        if sel is None and isinstance(df_auth_selected, dict):
                            sel = df_auth_selected.get("selection")
                        if sel:
                            cols = getattr(sel, "columns", None)
                            if cols is None and isinstance(sel, dict):
                                cols = sel.get("columns", [])
                            if cols and len(cols) > 0 and cols[0] in _auth_trk_list:
                                _clicked_auth_trk = cols[0]

                    if _clicked_auth_trk:
                        st.session_state["selected_auth_trk"] = _clicked_auth_trk

                    _cur_auth_trk = st.session_state.get("selected_auth_trk", _auth_trk_list[0])
                    if _cur_auth_trk not in _auth_trk_list:
                        _cur_auth_trk = _auth_trk_list[0]
                        st.session_state["selected_auth_trk"] = _cur_auth_trk

                    _s_item = next((x for x in _filtered_items if x["tracking_id"] == _cur_auth_trk), _filtered_items[0])

                    st.markdown("---")

                    # Inspection & Tracker Selection Header
                    scol1, scol2 = st.columns([3, 1])
                    with scol1:
                        _def_auth_idx = _auth_trk_list.index(_cur_auth_trk)
                        _chosen_auth_trk = st.selectbox(
                            "🔎 Active Tracker ID (click a column above or select below):",
                            _auth_trk_list,
                            index=_def_auth_idx,
                            key="auth_trk_select_dropdown",
                        )
                        if _chosen_auth_trk != _cur_auth_trk:
                            _cur_auth_trk = _chosen_auth_trk
                            st.session_state["selected_auth_trk"] = _cur_auth_trk
                            _s_item = next((x for x in _filtered_items if x["tracking_id"] == _cur_auth_trk), _filtered_items[0])

                    with scol2:
                        st.markdown(
                            f"<div style='padding-top:28px;font-size:13px;color:#00cc88;'>Active: <b>{_cur_auth_trk}</b> ({_auth_trk_list.index(_cur_auth_trk) + 1} of {len(_auth_trk_list)})</div>",
                            unsafe_allow_html=True,
                        )

                    # Selected Item Details
                    _s_status = _s_item["status"]
                    _badge_color = {
                        "pending_review": "#ff4b4b",
                        "appealed":       "#ffd700",
                        "actioned":       "#00cc88",
                        "dismissed":      "#888888",
                        "resolved":       "#00cc88",
                    }.get(_s_status, "#888888")

                    st.markdown(
                        f"<div style='background:#12161f;border:1px solid {_badge_color};"
                        f"border-left:5px solid {_badge_color};padding:14px;border-radius:6px;margin-bottom:12px;'>"
                        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                        f"<h5 style='margin:0;color:#fff;'>{_s_item['tracking_id']} | {_s_item['entity_type'].upper()}: {_s_item['entity_id']}</h5>"
                        f"<span style='background:{_badge_color};color:#000;padding:4px 10px;border-radius:4px;font-weight:bold;font-size:12px;'>"
                        f"{_s_status.upper()}</span></div>"
                        f"<div style='font-size:12px;color:#aaa;margin-top:6px;'>"
                        f"Tracking ID: <b>{_s_item['tracking_id']}</b> &nbsp;|&nbsp; Region: <b>{_s_item['region']}</b> &nbsp;|&nbsp; Risk Score: <b>{_s_item['risk_level']:.3f}</b>"
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown(f"**Recommended Action:**\n{_s_item['recommended_action']}")

                    if _s_item.get("dispute_reason"):
                        st.warning(
                            f"⚖️ **FORMAL DISPUTE FILED** ({_s_item.get('advocate_name', 'Filer')}):\n"
                            f"{_s_item['dispute_reason']}"
                        )

                    with st.expander("🔬 Forensic Evidence & Signal Trail", expanded=False):
                        for sig in _s_item.get("signals_triggered", []):
                            st.markdown(f"• **Signal:** `{sig.get('signal_type')}` | **Sub-Score:** `{sig.get('sub_score', 0.0):.3f}`")
                            ev_clean = {k: v for k, v in sig.get("evidence", {}).items() if k not in ("deposit_history", "deposit_timestamps")}
                            if ev_clean:
                                st.json(ev_clean)

                    st.markdown("##### 👮 Officer Decision Panel")
                    notes_input = st.text_input(
                        "Officer Audit Notes / Remarks",
                        placeholder="Enter notes for audit trail...",
                        key=f"auth_notes_{_s_item['tracking_id']}",
                    )

                    bcol1, bcol2, bcol3 = st.columns(3)
                    with bcol1:
                        if st.button("🔴 Action: Block / Blacklist", key=f"auth_act_{_s_item['tracking_id']}", disabled=not bool(_cur_officer), use_container_width=True):
                            _reviewer = _cur_officer["name"] if _cur_officer else "OFFICER-001"
                            _appeals_mgr.update_status(_s_item["tracking_id"], "actioned", reviewer_id=_reviewer, notes=notes_input or "Officer approved block action.")
                            st.session_state.dm_staged_actions.append({
                                "tracking_id": _s_item["tracking_id"],
                                "action_type": "BLOCK",
                                "entity_id": _s_item["entity_id"],
                                "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                            })
                            st.success(f"Staged action: BLOCK on {_s_item['tracking_id']}. Click '💾 Commit Changes' above or commit on sign out.")
                            st.rerun()
                    with bcol2:
                        if st.button("⚪ Whitelist Entity", key=f"auth_white_{_s_item['tracking_id']}", disabled=not bool(_cur_officer), use_container_width=True):
                            _reviewer = _cur_officer["name"] if _cur_officer else "OFFICER-001"
                            _appeals_mgr.update_status(_s_item["tracking_id"], "dismissed", reviewer_id=_reviewer, notes=notes_input or "Whitelisted after review.")
                            st.session_state.dm_staged_actions.append({
                                "tracking_id": _s_item["tracking_id"],
                                "action_type": "WHITELIST",
                                "entity_id": _s_item["entity_id"],
                                "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                            })
                            st.success(f"Staged action: WHITELIST on {_s_item['tracking_id']}.")
                            st.rerun()
                    with bcol3:
                        if st.button("⚖️ Resolve Dispute", key=f"auth_res_{_s_item['tracking_id']}", disabled=(not bool(_cur_officer) or _s_status != "appealed"), use_container_width=True):
                            _reviewer = _cur_officer["name"] if _cur_officer else "SENIOR-OFFICER-001"
                            _appeals_mgr.update_status(_s_item["tracking_id"], "resolved", reviewer_id=_reviewer, notes=notes_input or "Senior dispute resolution complete.")
                            st.session_state.dm_staged_actions.append({
                                "tracking_id": _s_item["tracking_id"],
                                "action_type": "RESOLVE_DISPUTE",
                                "entity_id": _s_item["entity_id"],
                                "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                            })
                            st.success(f"Staged action: RESOLVE_DISPUTE on {_s_item['tracking_id']}.")
                            st.rerun()

                    if not _cur_officer:
                        st.caption("🔒 Officer action buttons are disabled. Please authenticate with your Cyber Portal OTP in the header above to execute decisions.")

        # ── Sub-tab 3: Bank Queues — Sliding Table Layout ──────────────────────
        with dtab_bank:
            st.markdown("#### 🏦 Bank Fraud Investigation Console")
            st.caption("Partitioned by financial institution. Review flagged accounts in the sliding matrix (columns 1 to N). Select a column below to inspect signals and execute fraud prevention measures.")

            _live_bank_items = _appeals_mgr.get_by_recipient("bank")

            if not _live_bank_items:
                st.info("No bank account entities currently queued for fraud review.")
            else:
                _bank_names = sorted({b.get("bank_name", "Unknown Bank") for b in _live_bank_items if b.get("bank_name")})
                _sel_bank   = st.selectbox("🏛️ Select Financial Institution Queue", _bank_names, key="dm_bank_sel")
                _filtered_bank_items = [b for b in _live_bank_items if b.get("bank_name") == _sel_bank]
                _filtered_bank_items = sorted(_filtered_bank_items, key=lambda x: x.get("risk_level", 0.0), reverse=True)

                if not _filtered_bank_items:
                    st.info(f"No accounts queued for {_sel_bank}.")
                else:
                    M_bank = len(_filtered_bank_items)

                    # Build Sliding Table Data for Bank (Row headers stay fixed, Column headers are Tracker IDs)
                    bk_row_labels = [
                        "Account ID",
                        "Institution",
                        "Current Status",
                        "Risk Score",
                        "Risk Level",
                        "Region",
                        "Dispute Filed?",
                        "Signals Triggered",
                        "Registered At",
                    ]

                    bk_col_data = {}
                    for idx, b_item in enumerate(_filtered_bank_items):
                        col_key = b_item["tracking_id"]
                        b_st = b_item["status"]
                        st_text = (
                            "🔴 PENDING_REVIEW" if b_st == "pending_review" else
                            "⚖️ APPEALED" if b_st == "appealed" else
                            "🔒 ACTIONED" if b_st == "actioned" else
                            "❌ DISMISSED" if b_st == "dismissed" else
                            "✅ RESOLVED" if b_st == "resolved" else b_st.upper()
                        )
                        b_score = b_item.get("risk_level", 0.0)
                        r_level = "CRITICAL" if b_score >= 0.85 else "HIGH" if b_score >= 0.70 else "MEDIUM"
                        sig_types = ", ".join(s.get("signal_type", "") for s in b_item.get("signals_triggered", []))
                        b_disp = f"⚠️ YES ({b_item.get('advocate_name', 'Advocate')})" if b_item.get("dispute_reason") else "None"

                        bk_col_data[col_key] = [
                            b_item["entity_id"],
                            b_item.get("bank_name", "Unknown"),
                            st_text,
                            f"{b_score:.3f}",
                            r_level,
                            b_item.get("region", "India Nationwide"),
                            b_disp,
                            sig_types or "None",
                            b_item.get("created_at", "")[:19].replace("T", " "),
                        ]

                    df_sliding_bk = pd.DataFrame(bk_col_data, index=bk_row_labels)

                    st.markdown(f"##### 📊 {_sel_bank} Fraud Queue Matrix ({M_bank} Accounts)")
                    st.caption("👈 Use horizontal scrollbar to slide across Tracker IDs. Click any column or Tracker ID to inspect and action.")
                    df_bk_selected = st.dataframe(
                        df_sliding_bk,
                        on_select="rerun",
                        selection_mode="single-column",
                        use_container_width=True,
                        height=280,
                        key=f"bk_df_matrix_{_sel_bank}",
                    )

                    # Determine selected Tracker ID from column click or session state default
                    _bk_trk_list = [x["tracking_id"] for x in _filtered_bank_items]
                    _clicked_bk_trk = None
                    if df_bk_selected:
                        sel = getattr(df_bk_selected, "selection", None)
                        if sel is None and isinstance(df_bk_selected, dict):
                            sel = df_bk_selected.get("selection")
                        if sel:
                            cols = getattr(sel, "columns", None)
                            if cols is None and isinstance(sel, dict):
                                cols = sel.get("columns", [])
                            if cols and len(cols) > 0 and cols[0] in _bk_trk_list:
                                _clicked_bk_trk = cols[0]

                    if _clicked_bk_trk:
                        st.session_state[f"selected_bank_trk_{_sel_bank}"] = _clicked_bk_trk

                    _cur_bk_trk = st.session_state.get(f"selected_bank_trk_{_sel_bank}", _bk_trk_list[0])
                    if _cur_bk_trk not in _bk_trk_list:
                        _cur_bk_trk = _bk_trk_list[0]
                        st.session_state[f"selected_bank_trk_{_sel_bank}"] = _cur_bk_trk

                    _b_item = next((x for x in _filtered_bank_items if x["tracking_id"] == _cur_bk_trk), _filtered_bank_items[0])

                    st.markdown("---")

                    # Inspection & Tracker Selection Header for Bank
                    bcol_s1, bcol_s2 = st.columns([3, 1])
                    with bcol_s1:
                        _def_bk_idx = _bk_trk_list.index(_cur_bk_trk)
                        _chosen_bk_trk = st.selectbox(
                            f"🔎 Active {_sel_bank} Tracker ID (click a column above or select below):",
                            _bk_trk_list,
                            index=_def_bk_idx,
                            key=f"bk_trk_dropdown_{_sel_bank}",
                        )
                        if _chosen_bk_trk != _cur_bk_trk:
                            _cur_bk_trk = _chosen_bk_trk
                            st.session_state[f"selected_bank_trk_{_sel_bank}"] = _cur_bk_trk
                            _b_item = next((x for x in _filtered_bank_items if x["tracking_id"] == _cur_bk_trk), _filtered_bank_items[0])

                    with bcol_s2:
                        st.markdown(
                            f"<div style='padding-top:28px;font-size:13px;color:#ff8800;'>Active: <b>{_cur_bk_trk}</b> ({_bk_trk_list.index(_cur_bk_trk) + 1} of {len(_bk_trk_list)})</div>",
                            unsafe_allow_html=True,
                        )

                    # Selected Bank Item Details
                    _b_status = _b_item["status"]
                    _b_color  = {
                        "pending_review": "#ff8800",
                        "appealed":       "#ffd700",
                        "actioned":       "#00cc88",
                        "dismissed":      "#888888",
                        "resolved":       "#00cc88",
                    }.get(_b_status, "#888888")

                    st.markdown(
                        f"<div style='background:#12161f;border:1px solid {_b_color};"
                        f"border-left:5px solid {_b_color};padding:14px;border-radius:6px;margin-bottom:12px;'>"
                        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                        f"<h5 style='margin:0;color:#fff;'>{_b_item['tracking_id']} | Account: {_b_item['entity_id']}</h5>"
                        f"<span style='background:{_b_color};color:#000;padding:4px 10px;border-radius:4px;font-weight:bold;font-size:12px;'>"
                        f"{_b_status.upper()}</span></div>"
                        f"<div style='font-size:12px;color:#aaa;margin-top:6px;'>"
                        f"Institution: <b>{_b_item['bank_name']}</b> &nbsp;|&nbsp; Tracking ID: <b>{_b_item['tracking_id']}</b> &nbsp;|&nbsp; Risk Score: <b>{_b_item['risk_level']:.3f}</b>"
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown(f"**Recommended Action:**\n{_b_item['recommended_action']}")

                    if _b_item.get("dispute_reason"):
                        st.warning(f"⚖️ **FORMAL DISPUTE FILED** ({_b_item.get('advocate_name', 'Advocate')}):\n{_b_item['dispute_reason']}")

                    with st.expander("🔬 Deposit Surge & Mule Evidence", expanded=False):
                        st.json(_b_item.get("signals_triggered", []))

                    st.markdown("##### 🏦 Risk Officer Actions")
                    bk_notes = st.text_input(
                        "Bank Audit Remarks",
                        placeholder="Notes for compliance log...",
                        key=f"bk_notes_{_b_item['tracking_id']}",
                    )

                    bcol1, bcol2, bcol3 = st.columns(3)
                    with bcol1:
                        if st.button("🔒 Freeze Credits & Request KYC", key=f"bk_frz_{_b_item['tracking_id']}", disabled=not bool(_cur_officer), use_container_width=True):
                            _reviewer = _cur_officer["name"] if _cur_officer else f"RISK-OFFICER-{_sel_bank[:3]}"
                            _appeals_mgr.update_status(_b_item["tracking_id"], "actioned", reviewer_id=_reviewer, notes=bk_notes or "Credits frozen.")
                            st.session_state.dm_staged_actions.append({
                                "tracking_id": _b_item["tracking_id"],
                                "action_type": "DEBIT_FREEZE",
                                "entity_id": _b_item["entity_id"],
                                "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                            })
                            st.success(f"Staged action: DEBIT_FREEZE on {_b_item['tracking_id']}. Click '💾 Commit Changes' above or commit on sign out.")
                            st.rerun()
                    with bcol2:
                        if st.button("❌ Dismiss Flag", key=f"bk_dis_{_b_item['tracking_id']}", disabled=not bool(_cur_officer), use_container_width=True):
                            _reviewer = _cur_officer["name"] if _cur_officer else f"RISK-OFFICER-{_sel_bank[:3]}"
                            _appeals_mgr.update_status(_b_item["tracking_id"], "dismissed", reviewer_id=_reviewer, notes=bk_notes or "Dismissed after manual audit.")
                            st.session_state.dm_staged_actions.append({
                                "tracking_id": _b_item["tracking_id"],
                                "action_type": "DISMISS_FLAG",
                                "entity_id": _b_item["entity_id"],
                                "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                            })
                            st.success(f"Staged action: DISMISS_FLAG on {_b_item['tracking_id']}.")
                            st.rerun()
                    with bcol3:
                        if st.button("⚖️ Resolve Dispute", key=f"bk_res_{_b_item['tracking_id']}", disabled=(not bool(_cur_officer) or _b_status != "appealed"), use_container_width=True):
                            _reviewer = _cur_officer["name"] if _cur_officer else f"SENIOR-RISK-OFFICER-{_sel_bank[:3]}"
                            _appeals_mgr.update_status(_b_item["tracking_id"], "resolved", reviewer_id=_reviewer, notes=bk_notes or "Dispute resolved.")
                            st.session_state.dm_staged_actions.append({
                                "tracking_id": _b_item["tracking_id"],
                                "action_type": "RESOLVE_DISPUTE",
                                "entity_id": _b_item["entity_id"],
                                "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                            })
                            st.success(f"Staged action: RESOLVE_DISPUTE on {_b_item['tracking_id']}.")
                            st.rerun()

                    if not _cur_officer:
                        st.caption("🔒 Bank risk actions are disabled. Please authenticate with your Cyber Portal OTP in the header above to execute decisions.")

        # ── Sub-tab 4: Appeals & Recourse Console ──────────────────────────────
        with dtab_appeal:
            st.markdown("#### ⚖️ Recourse & Dispute Appeals Console")
            st.caption("Allows flagged parties or their legal advocates to submit formal disputes against flagged status using a Tracking ID.")

            _appeals_mgr = get_appeals_manager()

            col_form, col_list = st.columns([1, 1])

            with col_form:
                st.markdown("##### 📝 Submit Dispute Appeal")
                with st.form("appeal_submit_form"):
                    _tr_id_in  = st.text_input("Tracking ID (e.g. TRK-A8F31C)", placeholder="TRK-...")
                    _adv_in    = st.text_input("Advocate / Filer Name", value="Self / Legal Counsel")
                    _reason_in = st.text_area("Dispute Reason & Grounds for Appeal", placeholder="Provide context explaining why the entity is legitimate...")
                    _sub_btn   = st.form_submit_button("⚖️ Submit Dispute Appeal")

                    if _sub_btn:
                        if not _tr_id_in.strip() or not _reason_in.strip():
                            st.error("Please provide both Tracking ID and Dispute Reason.")
                        else:
                            _up_rec = _appeals_mgr.submit_appeal(
                                tracking_id=_tr_id_in.strip(),
                                dispute_reason=_reason_in.strip(),
                                advocate_name=_adv_in.strip(),
                            )
                            if _up_rec:
                                st.success(f"Appeal for `{_tr_id_in.strip()}` successfully submitted! Item re-queued for Senior Reviewer inspection.")
                                st.rerun()
                            else:
                                st.error(f"Tracking ID `{_tr_id_in.strip()}` not found in queue system.")

            with col_list:
                st.markdown("##### 📋 Review Queue Status Tracker")
                _all_items = _appeals_mgr.get_all()
                if not _all_items:
                    st.info("No items in review queue.")
                else:
                    _t_rows = []
                    for it in _all_items:
                        _t_rows.append({
                            "Tracking ID": it["tracking_id"],
                            "Entity":      f"{it['entity_type'].upper()}: {it['entity_id']}",
                            "Recipient":   it["recipient_type"].title(),
                            "Status":      it["status"].upper(),
                            "Dispute":     "YES" if it.get("dispute_reason") else "NO",
                            "Created At":  it["created_at"][:19].replace("T", " "),
                        })
                    st.dataframe(pd.DataFrame(_t_rows), use_container_width=True, height=350)

        st.divider()

        # ── Delivery Audit Log (Authorised Reviewers Only) ───────────────────
        with st.expander("🔒 Delivery Audit Trail (Authorised Reviewers Only)"):
            if _cur_officer:
                st.success(f"🔓 Access Granted: {_cur_officer['name']} ({_cur_officer['role']})")
                _d_audit = get_delivery_audit_log().get_recent(30)
                if _d_audit:
                    st.caption(f"Showing last {len(_d_audit)} routing & status transition entries.")
                    st.json(_d_audit)
                else:
                    st.info("No routing audit entries yet.")
            else:
                _dpwd = st.text_input("Enter access code (or authenticate with Cyber Portal OTP in header above)", type="password", key="dm_audit_pwd")
                if _dpwd == "audit":
                    _d_audit = get_delivery_audit_log().get_recent(30)
                    if _d_audit:
                        st.caption(f"Showing last {len(_d_audit)} routing & status transition entries.")
                        st.json(_d_audit)
                    else:
                        st.info("No routing audit entries yet.")
                elif _dpwd:
                    st.error("Access denied. Please authenticate with Cyber Portal OTP or enter valid code.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "⚠️ All data displayed here is SYNTHETIC and generated solely for "
    "training predictive analytics models. It must not be used as legal evidence."
)