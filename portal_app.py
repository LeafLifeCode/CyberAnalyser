"""
portal_app.py
-------------
Privileged Cyber Portal — Port 8502.
Authority Identity & OTP Dispatcher for Delivery Model Action Routing (Port 8501).

FEATURES:
  - 6 Authoritative Roles with live 🟢 ONLINE / ⚪ OFFLINE left-menu indicators.
  - Generates secure 6-digit OTP to access Action Routing & Delivery Audit.
  - Returns to login view showing who is active.
  - Single-session lock: No duplicate logins on the same username.
  - Inspecting any officer tab in the left menu displays their committed actions ({Authority_name: Tracker_ID}).
  - 'Clear Data' button at the bottom of the left menu to purge TXT session logs & CSV action logs.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from cyber_portal.bridge import (
    AUTHORITY_USERS,
    generate_otp_for_user,
    get_all_user_statuses,
    get_authority_actions,
    get_recent_session_logs,
    clear_all_data,
    sign_out_user,
)

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cyber Portal (Port 8502) — Authority OTP Dispatcher",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session State Initialization ──────────────────────────────────────────────
if "selected_officer_key" not in st.session_state:
    st.session_state.selected_officer_key = list(AUTHORITY_USERS.keys())[0]
if "last_generated_otp" not in st.session_state:
    st.session_state.last_generated_otp = None
if "last_otp_user" not in st.session_state:
    st.session_state.last_otp_user = None
if "show_login_screen" not in st.session_state:
    st.session_state.show_login_screen = True

# ── Banner Header ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="background: linear-gradient(90deg, #0d1b2a, #1b263b); padding: 16px 22px; border-radius: 10px; border-left: 6px solid #00cc88; margin-bottom: 20px;">
        <h2 style="color: #ffffff; margin: 0; font-size: 1.45rem; display: flex; align-items: center; gap: 10px;">
            🛡️ CYBER PORTAL &nbsp;<span style="font-size: 0.85rem; background: #00cc88; color: black; font-weight: bold; padding: 2px 10px; border-radius: 15px;">PORT 8502</span>
        </h2>
        <p style="color: #cbd5e1; margin: 5px 0 0 0; font-size: 0.90rem;">
            <strong>Authority Identity & OTP Dispatcher:</strong> Generates secure one-time credentials for Action Routing & Delivery Audit on Port 8501.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Fetch Live User Statuses ──────────────────────────────────────────────────
user_statuses = get_all_user_statuses()

# ── Left Menu / Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 👥 Authoritative Directory")
    st.caption("Select an officer to inspect live actions or issue an access OTP.")

    officer_keys = list(AUTHORITY_USERS.keys())

    # Build radio options with live ONLINE / OFFLINE badges
    formatted_options = {}
    for k in officer_keys:
        u = user_statuses[k]
        badge = "🟢 ONLINE" if u["status"] == "ONLINE" else "⚪ OFFLINE"
        formatted_options[k] = f"{badge}  {u['name']}"

    chosen_officer_key = st.radio(
        "Authority Officers",
        options=officer_keys,
        format_func=lambda k: formatted_options[k],
        key="sidebar_officer_radio",
        label_visibility="collapsed",
    )

    st.session_state.selected_officer_key = chosen_officer_key

    st.markdown("---")
    st.markdown("### 🌐 Cross-Port Links")
    st.markdown("- **Cyber Portal:** `http://localhost:8502`")
    st.markdown("- **Delivery Model:** `http://localhost:8501` *(Tab 4)*")

    st.markdown("---")
    # Bottom Clear Data Button with "Are you sure?" pop-up
    st.markdown("#### ⚙️ Maintenance & Logs")

    @st.dialog("⚠️ Are you sure?")
    def confirm_clear_dialog():
        st.warning("This action will permanently purge all session logs (TXT), authority actions (CSV), and reset all active OTP locks.")
        st.write("Do you want to proceed with clearing all data?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, Clear Data", type="primary", use_container_width=True, key="confirm_clear_yes_btn"):
                res = clear_all_data()
                st.session_state.last_generated_otp = None
                st.session_state.last_otp_user = None
                st.session_state.show_login_screen = True
                st.success(f"Purged: {res['message']}")
                st.rerun()
        with c2:
            if st.button("No, Cancel", type="secondary", use_container_width=True, key="confirm_clear_cancel_btn"):
                st.rerun()

    if st.button("🗑️ Clear Data (Purge TXT & CSV)", type="secondary", use_container_width=True, key="clear_data_main_btn"):
        confirm_clear_dialog()

# ── Main Content Area ─────────────────────────────────────────────────────────
cur_user = user_statuses[st.session_state.selected_officer_key]
is_online = (cur_user["status"] == "ONLINE")

top_col1, top_col2 = st.columns([2.5, 1.5])

with top_col1:
    st.markdown(f"### 👤 Officer Profile: {cur_user['name']}")
    st.markdown(
        f"**Role:** `{cur_user['role']}` &nbsp;|&nbsp; "
        f"**Badge ID:** `{cur_user['badge_id']}` &nbsp;|&nbsp; "
        f"**Department:** *{cur_user['department']}*"
    )

with top_col2:
    if is_online:
        st.markdown(
            """
            <div style="background: #064e3b; border: 1px solid #00cc88; padding: 10px 14px; border-radius: 8px; text-align: center;">
                <span style="color: #00cc88; font-weight: bold; font-size: 1.1rem;">🟢 ONLINE</span>
                <div style="font-size: 0.8rem; color: #a7f3d0; margin-top: 4px;">Active in Delivery Model</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="background: #1e293b; border: 1px solid #475569; padding: 10px 14px; border-radius: 8px; text-align: center;">
                <span style="color: #94a3b8; font-weight: bold; font-size: 1.1rem;">⚪ OFFLINE</span>
                <div style="font-size: 0.8rem; color: #cbd5e1; margin-top: 4px;">No Active Session</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

# ── Tab Navigation for Selected Officer ───────────────────────────────────────
tab_otp, tab_actions, tab_session_logs = st.tabs([
    "🔑 OTP Dispatch & Access",
    f"📋 Committed Actions ({cur_user['name']})",
    "📜 Live System Session Logs (TXT)",
])

# ── Tab 1: OTP Dispatch & Access ─────────────────────────────────────────────
with tab_otp:
    st.markdown("#### 🔐 Generate Action Routing Access OTP")
    st.caption("Generate a one-time 6-digit OTP for this authoritative user to unlock Action Routing decision panels and Delivery Audit on Port 8501.")

    if is_online:
        active_sess = cur_user.get("active_session", {})
        st.success(
            f"✅ **{cur_user['name']}** currently holds an **ACTIVE SESSION**.\n\n"
            f"- **Active OTP:** `{active_sess.get('otp', '******')}`\n"
            f"- **Login Time:** `{active_sess.get('login_time', 'N/A')}`\n\n"
            "This user can already unlock Action Routing in Port 8501 using this OTP."
        )

        st.info("📌 **Single-User Rule Enforced:** No more than one user can be logged into the same username at the same time.")

        if st.button("🚪 Force Sign Out Active Session", key=f"force_logout_{cur_user['username']}"):
            sign_out_user(cur_user["username"], commit_staged=False)
            st.warning(f"Session terminated for {cur_user['name']}. Status is now OFFLINE.")
            st.rerun()

    else:
        # User is offline -> Can generate OTP
        st.markdown(
            f"Click below to generate a fresh 6-digit access code for **{cur_user['name']}**. "
            "Once generated, status transitions to `🟢 ONLINE`."
        )

        # If we just generated an OTP in this view
        if (
            st.session_state.last_generated_otp
            and st.session_state.last_otp_user == cur_user["username"]
        ):
            st.markdown(
                f"""
                <div style="background: #0f2b1d; border: 2px solid #00cc88; padding: 18px; border-radius: 8px; margin: 15px 0;">
                    <div style="color: #a7f3d0; font-size: 0.95rem;">One-Time Password Generated for <b>{cur_user['name']}</b>:</div>
                    <div style="color: #00ffaa; font-family: monospace; font-size: 2.2rem; font-weight: bold; letter-spacing: 6px; margin: 10px 0;">
                        {st.session_state.last_generated_otp}
                    </div>
                    <div style="color: #cbd5e1; font-size: 0.85rem;">
                        👉 Copy this OTP and paste it into <b>Port 8501 (Tab 4: Delivery Model & Action Routing)</b> to unlock enforcement actions.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button("↩️ Return to Login Screen", key="return_login_btn", type="primary"):
                st.session_state.last_generated_otp = None
                st.session_state.last_otp_user = None
                st.rerun()

        else:
            if st.button(f"⚡ Generate OTP for {cur_user['name']}", type="primary", key=f"gen_otp_{cur_user['username']}"):
                try:
                    otp_code, sess_data = generate_otp_for_user(cur_user["username"])
                    st.session_state.last_generated_otp = otp_code
                    st.session_state.last_otp_user = cur_user["username"]
                    st.success(f"OTP generated successfully for {cur_user['name']}!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"❌ OTP Generation Error: {exc}")

# ── Tab 2: Committed Actions for this Officer ────────────────────────────────
with tab_actions:
    st.markdown(f"#### 📋 Actions Committed by {cur_user['name']}")
    st.caption("Reflects changes made at Delivery Model & Action Routing by this logged-in user (from `cyber_portal_authority_actions.csv`).")

    user_actions = get_authority_actions(authority_name=cur_user["name"])

    if not user_actions:
        st.info(f"No actions committed yet by {cur_user['name']}. Perform actions in Port 8501 and commit to view them here.")
    else:
        df_act = pd.DataFrame(user_actions)
        st.markdown(f"**Total Actions Logged:** `{len(df_act)}`")
        st.dataframe(df_act, use_container_width=True)

        st.caption("Logged in local CSV: `cyber_portal_authority_actions.csv`")

# ── Tab 3: Live System Session Logs ──────────────────────────────────────────
with tab_session_logs:
    st.markdown("#### 📜 Sign-In & Sign-Out Ledger (Local TXT File)")
    st.caption("Records every authentication and session termination event (`cyber_portal_session_log.txt`).")

    logs = get_recent_session_logs(max_lines=60)
    if not logs:
        st.info("No session log events recorded yet.")
    else:
        log_content = "\n".join(logs)
        st.text_area("Live Log Output", value=log_content, height=350, disabled=True)
