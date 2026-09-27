"""
app.py  — PAFCCI Synthetic Complaint Live Generator & Risk Engine Dashboard
=============================================================================
Streamlit dashboard for Complaint Generation (Phase 0) & Risk Engine Variance Model (Component 2).

Run:
    streamlit run app.py
"""

import base64
import json
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

import pydeck as pdk
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from ui_icons import get_svg_icon, get_svg_data_uri

_APP_DIR = Path(__file__).resolve().parent

def is_dark_theme() -> bool:
    """Detect if Streamlit is currently running in dark mode."""
    try:
        if hasattr(st, "context") and hasattr(st.context, "theme"):
            theme_obj = st.context.theme
            t = theme_obj.get("type") if isinstance(theme_obj, dict) else getattr(theme_obj, "type", None)
            if t == "dark":
                return True
            if t == "light":
                return False
    except Exception:
        pass
    return False

def get_risk_cell_style(val: str) -> str:
    """Return styling for dataframe risk level cells adapting cleanly to dark vs light mode."""
    if is_dark_theme():
        return {
            "CRITICAL": "background-color: rgba(220, 38, 38, 0.28); color: #FCA5A5; font-weight: bold;",
            "HIGH":     "background-color: rgba(234, 88, 12, 0.28); color: #FDBA74; font-weight: bold;",
            "MEDIUM":   "background-color: rgba(217, 119, 6, 0.28); color: #FDE68A; font-weight: bold;",
            "LOW":      "background-color: rgba(22, 163, 74, 0.28); color: #86EFAC; font-weight: bold;",
        }.get(val, "")
    return {
        "CRITICAL": "background-color: #FEE2E2; color: #DC2626; font-weight: bold;",
        "HIGH":     "background-color: #FFEDD5; color: #C2410C; font-weight: bold;",
        "MEDIUM":   "background-color: #FEF3C7; color: #B45309; font-weight: bold;",
        "LOW":      "background-color: #DCFCE7; color: #15803D; font-weight: bold;",
    }.get(val, "")

def _setup_audio_listeners():
    """Inject instant client-side audio listener and dual-theme real-time synchronizer.
    Plays sound_save.mp3 on START and STOP.
    Plays sound_click.mp3 on any other button interaction.
    Synchronizes [data-theme="dark"|"light"] across DOM elements based on Streamlit menu.
    """
    click_fp = _APP_DIR / "sound_click.mp3"
    save_fp = _APP_DIR / "sound_save.mp3"
    if not (click_fp.exists() and save_fp.exists()):
        return

    click_b64 = base64.b64encode(click_fp.read_bytes()).decode()
    save_b64 = base64.b64encode(save_fp.read_bytes()).decode()

    js_code = f"""
    <script>
    (function() {{
        try {{
            var clickData = "data:audio/mp3;base64,{click_b64}";
            var saveData = "data:audio/mp3;base64,{save_b64}";

            var targetDoc = (window.parent && window.parent.document) ? window.parent.document : document;
            var targetWin = window.parent || window;

            // ── Real-Time Dual-Theme Synchronizer ─────────────────────────────
            function detectTheme() {{
                try {{
                    var pathKey = 'stActiveTheme-' + (targetWin.location.pathname || '/');
                    var v2Key = pathKey + '-v2';
                    var raw = targetWin.localStorage.getItem(v2Key) || targetWin.localStorage.getItem(pathKey);
                    if (raw) {{
                        var parsed = JSON.parse(raw);
                        if (parsed && parsed.name === 'Dark') return 'dark';
                        if (parsed && parsed.name === 'Light') return 'light';
                    }}
                }} catch (e) {{}}

                try {{
                    var elem = targetDoc.querySelector('.stApp') || targetDoc.querySelector('[data-testid="stAppViewContainer"]') || targetDoc.body;
                    if (elem) {{
                        var bg = targetWin.getComputedStyle(elem).backgroundColor;
                        if (bg) {{
                            var m = bg.match(/\\d+/g);
                            if (m && m.length >= 3) {{
                                var lum = (parseInt(m[0])*299 + parseInt(m[1])*587 + parseInt(m[2])*114) / 1000;
                                return lum < 128 ? 'dark' : 'light';
                            }}
                        }}
                    }}
                }} catch (e) {{}}

                if (targetWin.matchMedia && targetWin.matchMedia('(prefers-color-scheme: dark)').matches) {{
                    return 'dark';
                }}
                return 'light';
            }}

            function syncTheme() {{
                try {{
                    var mode = detectTheme();
                    var root = targetDoc.documentElement;
                    var body = targetDoc.body;
                    var app = targetDoc.querySelector('[data-testid="stAppViewContainer"]');

                    if (root && root.getAttribute('data-theme') !== mode) root.setAttribute('data-theme', mode);
                    if (body && body.getAttribute('data-theme') !== mode) body.setAttribute('data-theme', mode);
                    if (app && app.getAttribute('data-theme') !== mode) app.setAttribute('data-theme', mode);
                }} catch(e) {{}}
            }}

            syncTheme();
            targetWin.addEventListener('storage', syncTheme);
            if (!targetWin._pafcciThemeSyncInterval) {{
                targetWin._pafcciThemeSyncInterval = setInterval(syncTheme, 300);
            }}

            // ── Audio Feedback Listeners ──────────────────────────────────────
            var origClickAudio = new Audio(clickData);
            var origSaveAudio = new Audio(saveData);
            origClickAudio.volume = 0.8;
            origSaveAudio.volume = 0.8;

            targetDoc._pafcciRealSaveAudio = origSaveAudio;
            targetDoc._pafcciRealClickAudio = origClickAudio;

            targetDoc._pafcciClickAudio = {{
                cloneNode: function() {{
                    if (Date.now() < (targetDoc._pafcciSuppressClickUntil || 0)) {{
                        return {{ play: function() {{ return Promise.resolve(); }} }};
                    }}
                    return origClickAudio.cloneNode();
                }}
            }};
            targetDoc._pafcciSaveAudio = {{
                cloneNode: function() {{
                    return origSaveAudio.cloneNode();
                }}
            }};

            if (targetDoc._pafcciAudioHandler) {{
                targetDoc.removeEventListener('click', targetDoc._pafcciAudioHandler, true);
            }}

            targetDoc._pafcciAudioHandler = function(evt) {{
                try {{
                    var selector = 'button, [role="button"], [role="tab"], input[type="button"], input[type="submit"], a[download], [data-testid*="Button"], [data-testid*="button"], [data-baseweb="tab"]';
                    var elem = evt.target.closest(selector);
                    if (!elem) {{
                        if (evt.target.tagName === 'BUTTON' || evt.target.getAttribute('role') === 'button') {{
                            elem = evt.target;
                        }}
                    }}
                    if (elem) {{
                        var text = (elem.innerText || elem.textContent || elem.getAttribute('aria-label') || '').trim().toUpperCase();
                        var html = (elem.outerHTML || '').toUpperCase();
                        var isStartOrStop = text.indexOf('START') !== -1 || text.indexOf('STOP') !== -1 ||
                                            html.indexOf('ENGINE_START_BTN') !== -1 || html.indexOf('ENGINE_STOP_BTN') !== -1;
                        if (isStartOrStop) {{
                            targetDoc._pafcciSuppressClickUntil = Date.now() + 400;
                            var s = origSaveAudio.cloneNode();
                            s.play().catch(function(e) {{}});
                        }} else {{
                            if (Date.now() >= (targetDoc._pafcciSuppressClickUntil || 0)) {{
                                var c = origClickAudio.cloneNode();
                                c.play().catch(function(e) {{}});
                            }}
                        }}
                    }}
                }} catch (err) {{}}
            }};

            targetDoc.addEventListener('click', targetDoc._pafcciAudioHandler, true);
        }} catch (err) {{}}
    }})();
    </script>
    """
    components.html(js_code, height=0, width=0)

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

# ── Phosphor Icons CDN ────────────────────────────────────────────────────────
st.markdown(
    '<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css">'
    '<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/bold/style.css">',
    unsafe_allow_html=True,
)

# ── CSS Theming ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Inter Font (Applied safely to text elements, protecting icon fonts!) ──── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stSidebar"],
h1, h2, h3, h4, h5, h6, p, label, button, input, textarea, select,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* ── PRESERVE ICON FONTS — Do NOT allow Inter to break material icons! ─────── */
[data-testid="stIconMaterial"], .material-symbols-rounded, .material-icons,
[data-testid="stSidebarCollapseButton"] span, [data-testid="stSidebarCollapseButton"] button {
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
}

/* ── Dual Theme Variables: Light Mode Palette ──────────────────────────────── */
:root, [data-theme="light"] {
    --pafcci-bg-base: #F7F9FC;
    --pafcci-bg-surface: #FFFFFF;
    --pafcci-bg-elevated: #F0F4FA;
    --pafcci-border: #DDE3EC;
    --pafcci-border-subtle: #EDF2F7;
    --pafcci-primary: #2563EB;
    --pafcci-primary-hover: #1D4ED8;
    --pafcci-primary-dark: #1E40AF;
    --pafcci-primary-muted: #DBEAFE;
    --pafcci-text-primary: #111827;
    --pafcci-text-secondary: #5B6B82;
    --pafcci-text-disabled: #A3AEC2;
    --pafcci-risk-high: #DC2626;
    --pafcci-risk-medium: #D97706;
    --pafcci-risk-low: #16A34A;
    --pafcci-info: #0284C7;
    --pafcci-icon-color: #2563EB;
    --pafcci-card-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
    --pafcci-banner-bg: linear-gradient(90deg, #FFFFFF, #F0F4FA);
    --pafcci-badge-bg: #DBEAFE;
    --pafcci-badge-text: #2563EB;
    --pafcci-badge-border: #93C5FD;
    --pafcci-online-bg: #F0FDF4;
    --pafcci-online-border: #16A34A;
    --pafcci-online-text: #16A34A;
    --pafcci-offline-bg: #F0F4FA;
    --pafcci-offline-border: #DDE3EC;
    --pafcci-offline-text: #5B6B82;
    --pafcci-code-bg: #F0F4FA;
    --pafcci-code-text: #2563EB;
    --pafcci-code-border: #DDE3EC;
    --pafcci-input-bg: #FFFFFF;
    --pafcci-table-even-bg: #F7F9FC;
    --pafcci-table-hover-bg: #DBEAFE;
    --pafcci-alert-success-bg: #F0FDF4;
    --pafcci-alert-error-bg: #FEF2F2;
    --pafcci-alert-warn-bg: #FFFBEB;
    --pafcci-alert-info-bg: #F0F9FF;
    --pafcci-risk-critical-bg: #FEE2E2;
    --pafcci-risk-critical-text: #DC2626;
    --pafcci-risk-high-bg: #FFEDD5;
    --pafcci-risk-high-text: #C2410C;
    --pafcci-risk-medium-bg: #FEF3C7;
    --pafcci-risk-medium-text: #B45309;
    --pafcci-risk-low-bg: #DCFCE7;
    --pafcci-risk-low-text: #15803D;
    --pafcci-img-filter: brightness(0) saturate(100%) invert(31%) sepia(94%) saturate(2132%) hue-rotate(213deg) brightness(96%) contrast(96%);
}

/* ── Dual Theme Variables: Cyber Dark Mode Palette ─────────────────────────── */
[data-theme="dark"] {
    --pafcci-bg-base: #0B1120;
    --pafcci-bg-surface: #111827;
    --pafcci-bg-elevated: #1A2333;
    --pafcci-border: #2A3548;
    --pafcci-border-subtle: #1F293D;
    --pafcci-primary: #3B82F6;
    --pafcci-primary-hover: #60A5FA;
    --pafcci-primary-dark: #1D4ED8;
    --pafcci-primary-muted: rgba(59, 130, 246, 0.2);
    --pafcci-text-primary: #F3F4F6;
    --pafcci-text-secondary: #94A3B8;
    --pafcci-text-disabled: #64748B;
    --pafcci-risk-high: #EF4444;
    --pafcci-risk-medium: #F59E0B;
    --pafcci-risk-low: #10B981;
    --pafcci-info: #38BDF8;
    --pafcci-icon-color: #86F0E2;
    --pafcci-card-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    --pafcci-banner-bg: linear-gradient(90deg, #111827, #1A2333);
    --pafcci-badge-bg: rgba(134, 240, 226, 0.15);
    --pafcci-badge-text: #86F0E2;
    --pafcci-badge-border: rgba(134, 240, 226, 0.4);
    --pafcci-online-bg: rgba(16, 185, 129, 0.12);
    --pafcci-online-border: #10B981;
    --pafcci-online-text: #10B981;
    --pafcci-offline-bg: #1A2333;
    --pafcci-offline-border: #2A3548;
    --pafcci-offline-text: #94A3B8;
    --pafcci-code-bg: #1A2333;
    --pafcci-code-text: #86F0E2;
    --pafcci-code-border: #2A3548;
    --pafcci-input-bg: #111827;
    --pafcci-table-even-bg: #0E1626;
    --pafcci-table-hover-bg: #1E293B;
    --pafcci-alert-success-bg: rgba(16, 185, 129, 0.12);
    --pafcci-alert-error-bg: rgba(239, 68, 68, 0.12);
    --pafcci-alert-warn-bg: rgba(245, 158, 11, 0.12);
    --pafcci-alert-info-bg: rgba(56, 189, 248, 0.12);
    --pafcci-risk-critical-bg: rgba(220, 38, 38, 0.28);
    --pafcci-risk-critical-text: #FCA5A5;
    --pafcci-risk-high-bg: rgba(234, 88, 12, 0.28);
    --pafcci-risk-high-text: #FDBA74;
    --pafcci-risk-medium-bg: rgba(217, 119, 6, 0.28);
    --pafcci-risk-medium-text: #FDE68A;
    --pafcci-risk-low-bg: rgba(22, 163, 74, 0.28);
    --pafcci-risk-low-text: #86EFAC;
    --pafcci-img-filter: brightness(0) saturate(100%) invert(88%) sepia(21%) saturate(928%) hue-rotate(113deg) brightness(98%) contrast(93%);
}

@media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
        --pafcci-bg-base: #0B1120;
        --pafcci-bg-surface: #111827;
        --pafcci-bg-elevated: #1A2333;
        --pafcci-border: #2A3548;
        --pafcci-border-subtle: #1F293D;
        --pafcci-primary: #3B82F6;
        --pafcci-primary-hover: #60A5FA;
        --pafcci-primary-dark: #1D4ED8;
        --pafcci-primary-muted: rgba(59, 130, 246, 0.2);
        --pafcci-text-primary: #F3F4F6;
        --pafcci-text-secondary: #94A3B8;
        --pafcci-text-disabled: #64748B;
        --pafcci-risk-high: #EF4444;
        --pafcci-risk-medium: #F59E0B;
        --pafcci-risk-low: #10B981;
        --pafcci-info: #38BDF8;
        --pafcci-icon-color: #86F0E2;
        --pafcci-card-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        --pafcci-banner-bg: linear-gradient(90deg, #111827, #1A2333);
        --pafcci-badge-bg: rgba(134, 240, 226, 0.15);
        --pafcci-badge-text: #86F0E2;
        --pafcci-badge-border: rgba(134, 240, 226, 0.4);
        --pafcci-online-bg: rgba(16, 185, 129, 0.12);
        --pafcci-online-border: #10B981;
        --pafcci-online-text: #10B981;
        --pafcci-offline-bg: #1A2333;
        --pafcci-offline-border: #2A3548;
        --pafcci-offline-text: #94A3B8;
        --pafcci-code-bg: #1A2333;
        --pafcci-code-text: #86F0E2;
        --pafcci-code-border: #2A3548;
        --pafcci-input-bg: #111827;
        --pafcci-table-even-bg: #0E1626;
        --pafcci-table-hover-bg: #1E293B;
        --pafcci-alert-success-bg: rgba(16, 185, 129, 0.12);
        --pafcci-alert-error-bg: rgba(239, 68, 68, 0.12);
        --pafcci-alert-warn-bg: rgba(245, 158, 11, 0.12);
        --pafcci-alert-info-bg: rgba(56, 189, 248, 0.12);
        --pafcci-risk-critical-bg: rgba(220, 38, 38, 0.28);
        --pafcci-risk-critical-text: #FCA5A5;
        --pafcci-risk-high-bg: rgba(234, 88, 12, 0.28);
        --pafcci-risk-high-text: #FDBA74;
        --pafcci-risk-medium-bg: rgba(217, 119, 6, 0.28);
        --pafcci-risk-medium-text: #FDE68A;
        --pafcci-risk-low-bg: rgba(22, 163, 74, 0.28);
        --pafcci-risk-low-text: #86EFAC;
        --pafcci-img-filter: brightness(0) saturate(100%) invert(88%) sepia(21%) saturate(928%) hue-rotate(113deg) brightness(98%) contrast(93%);
    }
}

/* ── Base & Background ─────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: var(--pafcci-bg-base) !important;
    color: var(--pafcci-text-primary) !important;
}
[data-testid="stSidebar"] {
    background-color: var(--pafcci-bg-surface) !important;
    border-right: 1px solid var(--pafcci-border) !important;
}
[data-testid="stSidebar"] * {
    color: var(--pafcci-text-primary);
}

/* ── Hide native sidebar padding & layout ──────────────────────────────────── */
[data-testid="stMain"] {
    margin-left: 0 !important;
    padding: 0.5rem 0.5rem !important;
}

/* ── Right Controls Panel Sticky Container (Column 2) ──────────────────────── */
div[data-testid="column"]:nth-child(2) > div {
    background: var(--pafcci-bg-surface) !important;
    border: 1px solid var(--pafcci-border) !important;
    border-radius: 10px !important;
    padding: 16px 14px !important;
    position: sticky !important;
    top: 0.5rem !important;
    max-height: calc(100vh - 1rem) !important;
    overflow-y: auto !important;
    box-shadow: var(--pafcci-card-shadow) !important;
}

/* ── Cards / Panels / Containers ───────────────────────────────────────────── */
/* Style tiny icons inside expander headers */
[data-testid="stExpander"] summary img {
    width: 14px !important;
    height: 14px !important;
    vertical-align: -2px !important;
    margin-right: 8px !important;
    display: inline-block !important;
    filter: var(--pafcci-img-filter);
}

[data-testid="stExpander"], [data-testid="stForm"],
div[class*="stTabs"] > div[role="tabpanel"] {
    background-color: var(--pafcci-bg-surface) !important;
    border: 1px solid var(--pafcci-border) !important;
    border-radius: 8px !important;
    box-shadow: var(--pafcci-card-shadow) !important;
}

/* ── Zero Gap Between Horizontal Tabs ───────────────────────────────────────── */
div[role="tablist"] {
    gap: 0px !important;
    border-bottom: 1px solid var(--pafcci-border) !important;
}
[data-testid="stTabs"] [role="tab"] {
    margin-right: 0px !important;
    margin-left: 0px !important;
    border-radius: 6px 6px 0 0 !important;
    border: 1px solid var(--pafcci-border) !important;
    border-right: none !important;
    padding: 8px 18px !important;
    background-color: var(--pafcci-bg-elevated) !important;
    color: var(--pafcci-text-secondary) !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.01em !important;
    transition: all 0.15s ease !important;
}
[data-testid="stTabs"] [role="tab"]:last-child {
    border-right: 1px solid var(--pafcci-border) !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    background-color: var(--pafcci-bg-surface) !important;
    color: var(--pafcci-primary) !important;
    border-color: var(--pafcci-border) !important;
    border-bottom: 2px solid var(--pafcci-primary) !important;
    font-weight: 600 !important;
}

/* ── Component Buttons in Sidebar: [ {icon} {Title} ] ───────────────────── */
div[data-testid="stSidebar"] div[data-testid="stButton"] button {
    text-align: left !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    width: 100% !important;
    padding: 11px 14px !important;
    border-radius: 8px !important;
    margin-bottom: 8px !important;
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
    box-shadow: var(--pafcci-card-shadow) !important;
    transition: all 0.15s ease !important;
}

/* Outline drawn icon inside button */
div[data-testid="stSidebar"] div[data-testid="stButton"] button img {
    width: 20px !important;
    height: 20px !important;
    margin-right: 10px !important;
    vertical-align: middle !important;
    display: inline-block !important;
    flex-shrink: 0 !important;
    filter: var(--pafcci-img-filter);
}

/* Inactive button */
div[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: var(--pafcci-bg-surface) !important;
    border: 1px solid var(--pafcci-border) !important;
    color: var(--pafcci-text-primary) !important;
}
div[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"]:hover {
    background-color: var(--pafcci-bg-elevated) !important;
    border-color: var(--pafcci-primary) !important;
    color: var(--pafcci-primary) !important;
    transform: translateX(2px) !important;
}

/* Active button (Primary) */
div[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {
    background-color: var(--pafcci-primary) !important;
    border: 1px solid var(--pafcci-primary-hover) !important;
    color: #FFFFFF !important;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25) !important;
}
div[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] img {
    filter: brightness(0) invert(1) !important;
}

/* ── Buttons ───────────────────────────────────────────────────────────────── */
button[kind="primary"], [data-testid="baseButton-primary"] {
    background-color: var(--pafcci-primary) !important;
    color: #FFFFFF !important;
    border: 1px solid var(--pafcci-primary-hover) !important;
    border-radius: 7px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    box-shadow: var(--pafcci-card-shadow) !important;
    transition: background 0.15s ease, transform 0.1s ease !important;
}
button[kind="primary"]:hover, [data-testid="baseButton-primary"]:hover {
    background-color: var(--pafcci-primary-hover) !important;
    border-color: var(--pafcci-primary-dark) !important;
    transform: translateY(-1px) !important;
}
button[kind="primary"]:active {
    background-color: var(--pafcci-primary-dark) !important;
    transform: translateY(0) !important;
}

button[kind="secondary"], [data-testid="baseButton-secondary"] {
    background-color: var(--pafcci-bg-surface) !important;
    color: var(--pafcci-text-primary) !important;
    border: 1px solid var(--pafcci-border) !important;
    border-radius: 7px !important;
    font-weight: 500 !important;
    box-shadow: var(--pafcci-card-shadow) !important;
    transition: all 0.15s ease !important;
}
button[kind="secondary"]:hover, [data-testid="baseButton-secondary"]:hover {
    background-color: var(--pafcci-bg-elevated) !important;
    border-color: var(--pafcci-primary) !important;
    color: var(--pafcci-primary) !important;
}
button[kind="secondary"]:active {
    background-color: var(--pafcci-primary-muted) !important;
}
button:disabled {
    opacity: 0.45 !important;
    cursor: not-allowed !important;
    background-color: var(--pafcci-bg-elevated) !important;
    color: var(--pafcci-text-disabled) !important;
    border-color: var(--pafcci-border) !important;
}

/* ── Metrics & KPI cards ───────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background-color: var(--pafcci-bg-surface);
    border: 1px solid var(--pafcci-border);
    border-radius: 8px;
    padding: 12px 16px;
    box-shadow: var(--pafcci-card-shadow);
    transition: border-color 0.2s;
}
[data-testid="metric-container"]:hover {
    border-color: var(--pafcci-primary);
}
[data-testid="metric-container"] label {
    color: var(--pafcci-text-secondary) !important;
    font-size: 0.75rem !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: var(--pafcci-text-primary) !important;
    font-weight: 700 !important;
}

/* ── Dataframes / Tables ───────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid var(--pafcci-border) !important;
    border-radius: 6px;
}
.stDataFrame thead th {
    background-color: var(--pafcci-bg-elevated) !important;
    color: var(--pafcci-text-primary) !important;
    font-weight: 600 !important;
}
.stDataFrame tbody tr:nth-child(even) {
    background-color: var(--pafcci-table-even-bg) !important;
}
.stDataFrame tbody tr:hover {
    background-color: var(--pafcci-table-hover-bg) !important;
}
.stDataFrame tbody td {
    color: var(--pafcci-text-primary);
    border-color: var(--pafcci-border);
}

/* ── Inputs / Selects ──────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] select, div[data-baseweb="select"] > div {
    background-color: var(--pafcci-input-bg) !important;
    color: var(--pafcci-text-primary) !important;
    border: 1px solid var(--pafcci-border) !important;
    border-radius: 7px !important;
}
[data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus {
    border-color: var(--pafcci-primary) !important;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15) !important;
}

/* ── Sliders ───────────────────────────────────────────────────────────────── */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background-color: var(--pafcci-primary) !important;
}

/* ── Alerts / Banners ──────────────────────────────────────────────────────── */
[data-testid="stAlert"][data-type="success"]  { background-color: var(--pafcci-alert-success-bg) !important; border-left: 4px solid var(--pafcci-risk-low) !important; color: var(--pafcci-text-primary) !important; }
[data-testid="stAlert"][data-type="error"]    { background-color: var(--pafcci-alert-error-bg) !important; border-left: 4px solid var(--pafcci-risk-high) !important; color: var(--pafcci-text-primary) !important; }
[data-testid="stAlert"][data-type="warning"]  { background-color: var(--pafcci-alert-warn-bg) !important; border-left: 4px solid var(--pafcci-risk-medium) !important; color: var(--pafcci-text-primary) !important; }
[data-testid="stAlert"][data-type="info"]     { background-color: var(--pafcci-alert-info-bg) !important; border-left: 4px solid var(--pafcci-info) !important; color: var(--pafcci-text-primary) !important; }

/* ── Text hierarchy ────────────────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 { color: var(--pafcci-text-primary) !important; font-weight: 700 !important; letter-spacing: -0.01em; }
small, .stCaption, [data-testid="stCaptionContainer"] { color: var(--pafcci-text-secondary) !important; }
code {
    background-color: var(--pafcci-code-bg);
    color: var(--pafcci-code-text);
    border: 1px solid var(--pafcci-code-border);
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 0.85em;
}

/* ── Dividers ──────────────────────────────────────────────────────────────── */
hr { border-color: var(--pafcci-border) !important; }

/* ── Radio / Checkbox ──────────────────────────────────────────────────────── */
[data-testid="stRadio"] label { color: var(--pafcci-text-primary) !important; }
[data-testid="stRadio"] [data-baseweb="radio"] [data-checked="true"] span { background-color: var(--pafcci-primary) !important; }
[data-testid="stCheckbox"] [data-baseweb="checkbox"] { border-color: var(--pafcci-primary) !important; }

/* ── SMS / Evidence boxes ──────────────────────────────────────────────────── */
.sms-box {
    background: var(--pafcci-bg-elevated);
    border: 1px solid var(--pafcci-border);
    border-radius: 8px;
    padding: 12px;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    white-space: pre-wrap;
    color: var(--pafcci-text-primary);
    max-height: 400px;
    overflow-y: auto;
}
.evidence-box {
    background: var(--pafcci-alert-success-bg);
    border-left: 4px solid var(--pafcci-risk-low);
    border: 1px solid var(--pafcci-border);
    padding: 10px;
    font-family: monospace;
    font-size: 13px;
    color: var(--pafcci-text-primary);
    border-radius: 4px;
}

/* ── Risk colors ───────────────────────────────────────────────────────────── */
.risk-CRITICAL { color: var(--pafcci-risk-high); font-weight: bold; }
.risk-HIGH     { color: var(--pafcci-risk-medium); font-weight: bold; }
.risk-MEDIUM   { color: var(--pafcci-info); font-weight: bold; }
.risk-LOW      { color: var(--pafcci-risk-low); font-weight: bold; }

/* ── Role accent pills ─────────────────────────────────────────────────────── */
.role-lea    { background-color: rgba(99, 102, 241, 0.12); color: #6366F1; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700; }
.role-bank   { background-color: rgba(13, 148, 136, 0.12); color: #0D9488; border: 1px solid rgba(13, 148, 136, 0.3); border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700; }
.role-devops { background-color: rgba(100, 116, 139, 0.12); color: #64748B; border: 1px solid rgba(100, 116, 139, 0.3); border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700; }

/* ── Pydeck map ────────────────────────────────────────────────────────────── */
.stPydeckChart, iframe[title="pydeck.Deck"], div[data-testid="stDeckGlJsonContainer"] {
    background-color: var(--pafcci-bg-surface) !important;
    border-radius: 8px;
    border: 1px solid var(--pafcci-border);
}

/* ── Dialog modals ─────────────────────────────────────────────────────────── */
[data-testid="stModal"] > div {
    background-color: var(--pafcci-bg-surface) !important;
    border: 1px solid var(--pafcci-border) !important;
    border-radius: 10px !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15) !important;
}

/* ── Scrollbar ─────────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--pafcci-bg-base); }
::-webkit-scrollbar-thumb { background: var(--pafcci-border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--pafcci-text-disabled); }

/* ── Inline SVG & Image Filter ─────────────────────────────────────────────── */
svg.pafcci-icon { stroke: var(--pafcci-icon-color) !important; }
svg text,
.vega-embed svg text,
[data-testid="stVegaLiteChart"] svg text,
[data-testid="stDataFrame"] svg text {
    stroke: none !important;
}
[data-testid="stVegaLiteChart"] svg rect:not(.mark-rect) {
    stroke: none !important;
}
img[src^="data:image/svg+xml"] { filter: var(--pafcci-img-filter); }
button[kind="primary"] img[src^="data:image/svg+xml"], [data-testid="baseButton-primary"] img[src^="data:image/svg+xml"] {
    filter: brightness(0) invert(1) !important;
}

/* ── Audio iframe concealment ──────────────────────────────────────────────── */
iframe[title*="components"] {
    display: none !important;
    height: 0px !important;
    width: 0px !important;
    position: absolute !important;
    border: none !important;
}
</style>
""", unsafe_allow_html=True)


# ── Loading Screen ────────────────────────────────────────────────────────────
def _show_loading_screen():
    """Full-screen cyber splash shown once on first load (adapts to Dark or Light theme)."""
    components.html("""
    <script>
    (function() {
        var pDoc = (window.parent && window.parent.document) ? window.parent.document : document;
        var pWin = window.parent || window;
        if (pDoc.getElementById('pafcci-loading-screen')) return;

        var isDark = true;
        try {
            var pathKey = 'stActiveTheme-' + (pWin.location.pathname || '/');
            var v2Key = pathKey + '-v2';
            var raw = pWin.localStorage.getItem(v2Key) || pWin.localStorage.getItem(pathKey);
            if (raw) {
                var parsed = JSON.parse(raw);
                if (parsed && parsed.name === 'Light') isDark = false;
            } else if (pWin.matchMedia && pWin.matchMedia('(prefers-color-scheme: light)').matches) {
                isDark = false;
            }
        } catch(e) {}

        var bgColor = isDark ? '#0B1120' : '#F7F9FC';
        var logoColor = isDark ? '#86F0E2' : '#2563EB';
        var logoShadow = isDark ? '0 0 24px rgba(134,240,226,0.35)' : '0 4px 16px rgba(37,99,235,0.2)';
        var subColor = isDark ? '#94A3B8' : '#5B6B82';
        var barTrack = isDark ? '#1A2333' : '#DDE3EC';
        var barFill = isDark ? 'linear-gradient(90deg, #3B82F6, #86F0E2)' : 'linear-gradient(90deg, #2563EB, #60A5FA)';
        var barShadow = isDark ? '0 0 10px #86F0E2' : '0 0 10px rgba(37,99,235,0.35)';

        var style = pDoc.createElement('style');
        style.id = 'pafcci-loading-style';
        style.textContent = `
            #pafcci-loading-screen {
                position: fixed !important;
                top: 0 !important; left: 0 !important;
                width: 100vw !important; height: 100vh !important;
                background: ${bgColor} !important;
                z-index: 9999999 !important;
                display: flex !important;
                flex-direction: column !important;
                align-items: center !important;
                justify-content: center !important;
                transition: opacity 0.5s ease !important;
                font-family: 'Inter', sans-serif !important;
            }
            .pafcci-load-logo {
                font-size: 2.8rem;
                font-weight: 800;
                letter-spacing: 0.14em;
                color: ${logoColor};
                text-shadow: ${logoShadow};
                animation: pafcci-pulse 1.4s ease-in-out infinite alternate;
            }
            .pafcci-load-tag {
                font-size: 0.72rem;
                color: ${subColor};
                letter-spacing: 0.22em;
                text-transform: uppercase;
                margin-top: 6px;
                font-weight: 600;
            }
            .pafcci-load-sub {
                color: ${subColor};
                font-size: 0.85rem;
                margin-top: 22px;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }
            .pafcci-load-bar-wrap {
                width: 260px;
                height: 4px;
                background: ${barTrack};
                border-radius: 4px;
                margin-top: 16px;
                overflow: hidden;
                position: relative;
            }
            .pafcci-load-bar-inner {
                position: absolute;
                top: 0; left: 0; height: 100%; width: 0%;
                background: ${barFill};
                box-shadow: ${barShadow};
                animation: pafcci-bar-fill 1.2s cubic-bezier(0.4, 0, 0.2, 1) forwards;
            }
            @keyframes pafcci-pulse {
                from { transform: scale(0.98); opacity: 0.8; }
                to { transform: scale(1.02); opacity: 1; text-shadow: ${logoShadow}; }
            }
            @keyframes pafcci-bar-fill {
                0% { width: 0%; }
                60% { width: 75%; }
                100% { width: 100%; }
            }
        `;
        pDoc.head.appendChild(style);

        var overlay = pDoc.createElement('div');
        overlay.id = 'pafcci-loading-screen';
        overlay.innerHTML = `
            <div class="pafcci-load-logo">PAFCCI</div>
            <div class="pafcci-load-tag">I4C &middot; MHA &middot; Cybercrime Intelligence</div>
            <div class="pafcci-load-sub">INITIALIZING INTELLIGENCE PLATFORM...</div>
            <div class="pafcci-load-bar-wrap"><div class="pafcci-load-bar-inner"></div></div>
        `;
        pDoc.body.appendChild(overlay);

        setTimeout(function() {
            overlay.style.opacity = '0';
            setTimeout(function() {
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
                if (style.parentNode) style.parentNode.removeChild(style);
            }, 550);
        }, 1300);
    })();
    </script>
    """, height=0, width=0)

# ── Instant Audio Listener Setup ──────────────────────────────────────────────
_setup_audio_listeners()


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
if "active_tab"    not in st.session_state: st.session_state.active_tab    = 0
if "_app_loaded"   not in st.session_state: st.session_state._app_loaded   = False

# ── Initial Loading Splash ───────────────────────────────────────────────────
if not st.session_state._app_loaded:
    _show_loading_screen()
    st.session_state._app_loaded = True

store = get_store()
use_llm = False  # Fast Direct Mode — hardcoded offline mode

# ── Left Sidebar: Component Selection Navigation Rail ────────────────────────
with st.sidebar:
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;padding:4px 0 12px 0;border-bottom:1px solid var(--pafcci-border);margin-bottom:14px;">
            {get_svg_icon("shield", 30)}
            <div>
                <div style="color:var(--pafcci-primary);font-size:1.15rem;font-weight:800;letter-spacing:0.08em;line-height:1.2;">PAFCCI</div>
                <div style="color:var(--pafcci-text-secondary);font-size:0.68rem;letter-spacing:0.04em;">CYBERCRIME INTELLIGENCE</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div style="font-size:0.70rem;font-weight:700;letter-spacing:0.08em;color:var(--pafcci-primary);text-transform:uppercase;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
            {get_svg_icon("crosshair", 14)} COMPONENT SELECTION
        </div>
        """,
        unsafe_allow_html=True
    )

    # 4 Component Selection Buttons [ {icon} {Title} ]
    _components = [
        (0, "Victim Report Generator", "report"),
        (1, "Variance Anomaly Model", "variance"),
        (2, "ATM Risk Heatmap", "heatmap"),
        (3, "Delivery & Action Routing", "delivery"),
    ]

    for _idx, _title, _icon_name in _components:
        _is_cur = (st.session_state.active_tab == _idx)
        _icon_uri = get_svg_data_uri(_icon_name, 20, "#FFFFFF" if _is_cur else "#2563EB")
        _btn_label = f"![icon]({_icon_uri})  {_title}"

        if st.button(
            _btn_label,
            key=f"nav_comp_btn_{_idx}",
            type="primary" if _is_cur else "secondary",
            use_container_width=True,
        ):
            if st.session_state.active_tab != _idx:
                st.session_state.active_tab = _idx
                st.rerun()

    st.markdown("---")

    # Platform Telemetry Pill
    _eng_st = '<span style="color:var(--pafcci-risk-low);font-weight:700;">● RUNNING</span>' if st.session_state.running else '<span style="color:var(--pafcci-risk-high);font-weight:700;">○ STOPPED</span>'
    st.markdown(
        f"""
        <div style="background:var(--pafcci-bg-elevated);border:1px solid var(--pafcci-border);border-radius:8px;padding:10px 12px;font-size:0.75rem;">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="color:var(--pafcci-text-secondary);">Engine Status:</span>
                {_eng_st}
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="color:var(--pafcci-text-secondary);">Cycles Run:</span>
                <span style="color:var(--pafcci-primary);font-weight:700;">{st.session_state.cycle_count}</span>
            </div>
            <div style="display:flex;justify-content:space-between;">
                <span style="color:var(--pafcci-text-secondary);">Events in Store:</span>
                <span style="color:var(--pafcci-primary);font-weight:700;">{store.count()}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    if st.button("Reset Store & Engines", type="secondary", use_container_width=True, key="sidebar_reset_btn"):
        from generator.tools.attacker_tools import _initialise_pool
        store.clear()
        _initialise_pool(0)
        reset_model()
        reset_engines()
        reset_drift_detector()
        reset_appeals_manager()
        reset_delivery_audit_log()
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

# ── Main Two-Column Layout: [Active Workspace (73%) | Engine Controls (27%)] ───
col_main, col_ctrl = st.columns([0.73, 0.27], gap="medium")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RIGHT COLUMN — Generator & Engine Controls (Sticky Panel)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with col_ctrl:
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            {get_svg_icon("cpu", 22)}
            <h3 style="margin:0;font-size:1.05rem;color:var(--pafcci-text-primary);text-transform:uppercase;letter-spacing:0.04em;">Engine Controls</h3>
        </div>
        <div style="font-size:0.72rem;color:var(--pafcci-text-secondary);margin-bottom:10px;">Live Stream Settings &middot; Synthetic Data Only</div>
        """,
        unsafe_allow_html=True
    )

    # ── START, STOP & RUN ONE CYCLE (Positioned right below Engine Controls!) ─
    _c1, _c2 = st.columns(2)
    with _c1:
        if st.button("▶ START", use_container_width=True,
                     disabled=st.session_state.running,
                     type="primary"):
            st.session_state.running = True
            st.session_state.error_msg = ""
            st.rerun()
    with _c2:
        if st.button("⏹ STOP", use_container_width=True,
                     disabled=not st.session_state.running):
            st.session_state.running = False
            st.rerun()

    if st.button("⚡ Run One Cycle Now", use_container_width=True):
        st.session_state.running = False
        st.session_state._run_once = True
        st.rerun()

    st.divider()

    # ── COLLAPSIBLE DROPDOWN MENUS (EXPANDERS) FOR SETTINGS ──────────────────
    with st.expander(f"![icon]({get_svg_data_uri('users', 14)})  Attacker Settings", expanded=False):
        num_attackers   = st.slider("Active Attackers",         1, 20,  3)
        phone_churn     = st.slider("Phone Churn Rate",        0.0, 1.0, 0.20, 0.05)
        ip_churn        = st.slider("IP/VPN Churn Rate",       0.0, 1.0, 0.20, 0.05)

    with st.expander(f"![icon]({get_svg_data_uri('credit_card', 14)})  Transaction Settings", expanded=False):
        amount_mean     = st.number_input("Mean Fraud Amount (INR)", 1000, 500000, 70000, 1000)
        amount_var      = st.slider("Amount Variance",           0.05, 1.0, 0.30, 0.05)
        freq_before_atm = st.slider("Transactions before ATM",    1, 20,   3)

    with st.expander(f"![icon]({get_svg_data_uri('branch', 14)})  Mule Chain Settings", expanded=False):
        mule_depth      = st.slider("Max Mule Chain Depth (hops)",   2,  7,   3)

    with st.expander(f"![icon]({get_svg_data_uri('bank', 14)})  ATM / Withdrawal Settings", expanded=False):
        atm_bias        = st.selectbox("ATM Location Bias", ["Urban", "Semi-Urban", "Rural", "Random"])
        report_to_w_min = st.slider("Report to Withdrawal Min (min)",  1, 60,  10)
        report_to_w_max = st.slider("Report to Withdrawal Max (min)", 10, 240, 30)

    with st.expander(f"![icon]({get_svg_data_uri('clock', 14)})  Timing Settings", expanded=False):
        tick_interval   = st.slider("Interval Between Cycles (sec)", 10, 300, 20, 10)

# ── Build Config from Sliders ─────────────────────────────────────────────────
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

with col_main:
    # ── Main Title ────────────────────────────────────────────────────────────────
    st.markdown(f'<div style="display:flex;align-items:center;gap:10px;">{get_svg_icon("shield", 32)}<h1 style="margin:0;font-size:1.85rem;">PAFCCI &mdash; Cybercrime Predictive Analytics Platform</h1></div>', unsafe_allow_html=True)
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

    # ── Active Component Routing ────────────────────────────────────────────────
    _active = st.session_state.active_tab

    # ==============================================================================
    # TAB 1: VICTIM REPORT GENERATOR
    # ==============================================================================
    if _active == 0:
        st.markdown(f'<h3>{get_svg_icon("chat", 22)} Latest SMS Prompts</h3>', unsafe_allow_html=True)
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

        st.markdown(f'<h3>{get_svg_icon("table", 22)} Live Event Log ({store.count()} events)</h3>', unsafe_allow_html=True)
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
    elif _active == 1:
        st.markdown(f'<h3>{get_svg_icon("variance", 22)} Risk Engine &mdash; Variance Model Anomaly Detection</h3>', unsafe_allow_html=True)
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
                st.markdown(f'<h4>{get_svg_icon("flag", 20)} Flagged Entities ({len(aggregated)} total &mdash; sorted by confidence)</h4>', unsafe_allow_html=True)

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

                    st.markdown(f'<h4>{get_svg_icon("variance", 20)} Deposit Behavior Timeline &mdash; {selected["entity_id"]}</h4>', unsafe_allow_html=True)
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
                    st.markdown(f'<h4>{get_svg_icon("globe", 20)} IP Velocity Anomaly &mdash; {selected["entity_id"]}</h4>', unsafe_allow_html=True)
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
                    st.markdown(f'<h4>{get_svg_icon("phone_slash", 20)} IP/Phone Binding Anomaly &mdash; {selected["entity_id"]}</h4>', unsafe_allow_html=True)
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

                    colour_var_risk = get_risk_cell_style

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
    elif _active == 2:
        st.markdown(f'<h3>{get_svg_icon("heatmap", 22)} Risk Heatmap &mdash; ATM Withdrawal Prediction</h3>', unsafe_allow_html=True)
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
                    f"<div style='background:var(--pafcci-bg-elevated);border:1px solid {_col};"
                    f"border-left:4px solid {_col};border-radius:6px;padding:14px;"
                    f"font-family:\"Courier New\",monospace;font-size:12px;color:var(--pafcci-text-primary);"
                    f"white-space:pre;overflow-x:auto;'>{_console_text}</div>",
                    unsafe_allow_html=True,
                )

                st.divider()

                # ── pydeck Map ────────────────────────────────────────────────────
                st.markdown(f'<h4>{get_svg_icon("heatmap", 20)} ATM Risk Heatmap</h4>', unsafe_allow_html=True)

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

                _map_style = (
                    "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
                    if is_dark_theme()
                    else "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
                )

                _deck = pdk.Deck(
                    layers=[_scatter_layer],
                    initial_view_state=_view,
                    tooltip={"text": "{tooltip_label}\nRisk: {risk_level}"},
                    map_style=_map_style,
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

                    _colour_rl = get_risk_cell_style

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
    elif _active == 3:
        st.markdown(f'<h3>{get_svg_icon("delivery", 22)} Delivery Model &amp; Action Routing</h3>', unsafe_allow_html=True)
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
            dm1.metric("Civilian Advisories", len(_civ_alerts))
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
                    <div style='background:var(--pafcci-bg-surface);border:1px solid var(--pafcci-primary);border-left:5px solid var(--pafcci-primary);padding:12px 18px;border-radius:8px;margin-bottom:12px;box-shadow:var(--pafcci-card-shadow);'>
                        <h5 style='margin:0 0 4px 0;color:var(--pafcci-primary);'>🔐 Action Routing & Delivery Audit — Authoritative Access Required</h5>
                        <p style='margin:0;font-size:0.86rem;color:var(--pafcci-text-secondary);'>
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
                    <div style='background:var(--pafcci-online-bg);border:1px solid var(--pafcci-online-border);border-left:5px solid var(--pafcci-online-border);padding:12px 18px;border-radius:8px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;box-shadow:var(--pafcci-card-shadow);'>
                        <div>
                            <span style='color:var(--pafcci-online-text);font-weight:bold;font-size:1.05rem;'>🟢 {_cur_officer['name']}</span>
                            <span style='color:var(--pafcci-text-secondary);font-size:0.88rem;margin-left:8px;'>({_cur_officer['role']} · {_cur_officer['badge_id']})</span>
                        </div>
                        <div>
                            <span style='background:var(--pafcci-bg-surface);color:var(--pafcci-online-text);padding:4px 10px;border-radius:6px;font-size:0.85rem;border:1px solid var(--pafcci-online-border);'>
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
                    if st.button("Commit Changes", type="primary", use_container_width=True, key="dm_commit_btn"):
                        if len(st.session_state.dm_staged_actions) == 0:
                            st.info("No uncommitted actions to commit.")
                        else:
                            cnt = commit_authority_actions(_cur_officer["name"], st.session_state.dm_staged_actions)
                            st.session_state.dm_staged_actions = []
                            st.success(f"Successfully committed {cnt} action(s) to cyber_portal_authority_actions.csv!")
                            st.rerun()
                with scol_c:
                    if st.button("Sign Out", type="secondary", use_container_width=True, key="dm_signout_init_btn"):
                        if len(st.session_state.dm_staged_actions) > 0:
                            st.session_state.dm_show_signout_confirm = True
                            st.rerun()
                        else:
                            sign_out_user(_cur_officer["username"], commit_staged=False)
                            st.session_state.dm_auth_officer = None
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
                "Civilian Advisories",
                "Authority Review Queue",
                "Bank Fraud Queues",
                "Recourse & Appeals",
            ])

            # ── Sub-tab 1: Civilian Advisories ─────────────────────────────────────
            with dtab_civ:
                st.markdown(f'<h4>{get_svg_icon("delivery", 22)} Regional Civilian Safety Advisories</h4>', unsafe_allow_html=True)
                st.caption(
                    "Issued only when regional aggregate risk exceeds threshold. "
                    "**STRICT PRIVACY GUARANTEE**: Contains generic regional guidance only — NO phone numbers, IPs, or accounts."
                )
                if not _civ_alerts:
                    st.info("No regions currently exceed the regional risk threshold, or alerts are currently suppressed by active 24h cooldown.")
                else:
                    for alert in _civ_alerts:
                        st.markdown(
                            f"<div style='background:var(--pafcci-bg-surface);border:1px solid var(--pafcci-border);border-left:5px solid #ff8800;"
                            f"padding:14px;border-radius:6px;margin-bottom:12px;box-shadow:var(--pafcci-card-shadow);'>"
                            f"<h5 style='margin:0 0 8px 0;color:#ff8800;'>{alert['region']} (Regional Risk Score: {alert['regional_risk_score']:.3f})</h5>"
                            f"<pre style='font-family:monospace;white-space:pre-wrap;color:var(--pafcci-text-primary);margin:0;'>{alert['alert_text']}</pre>"
                            f"<div style='margin-top:8px;font-size:11px;color:var(--pafcci-text-secondary);'>"
                            f"🔒 Privacy Guard: No per-entity data disclosed · ⏱️ 24h Cooldown Active until {(datetime.now(IST)+timedelta(hours=24)).strftime('%H:%M IST')}"
                            f"</div></div>",
                            unsafe_allow_html=True,
                        )

            # ── Sub-tab 2: Authority Queue (Phone/IP) — Sliding Table Layout ────────
            with dtab_auth:
                st.markdown(f'<h4>{get_svg_icon("shield", 20)} Cyber Crime Authority &mdash; Manual Review Queue</h4>', unsafe_allow_html=True)
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
                            f"<div style='background:var(--pafcci-bg-surface);border:1px solid {_badge_color};"
                            f"border-left:5px solid {_badge_color};padding:14px;border-radius:6px;margin-bottom:12px;box-shadow:var(--pafcci-card-shadow);'>"
                            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                            f"<h5 style='margin:0;color:var(--pafcci-text-primary);'>{_s_item['tracking_id']} | {_s_item['entity_type'].upper()}: {_s_item['entity_id']}</h5>"
                            f"<span style='background:{_badge_color};color:#000;padding:4px 10px;border-radius:4px;font-weight:bold;font-size:12px;'>"
                            f"{_s_status.upper()}</span></div>"
                            f"<div style='font-size:12px;color:var(--pafcci-text-secondary);margin-top:6px;'>"
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
                            if st.button("Block / Blacklist", key=f"auth_act_{_s_item['tracking_id']}", disabled=not bool(_cur_officer), use_container_width=True):
                                _reviewer = _cur_officer["name"] if _cur_officer else "OFFICER-001"
                                _appeals_mgr.update_status(_s_item["tracking_id"], "actioned", reviewer_id=_reviewer, notes=notes_input or "Officer approved block action.")
                                st.session_state.dm_staged_actions.append({
                                    "tracking_id": _s_item["tracking_id"],
                                    "action_type": "BLOCK",
                                    "entity_id": _s_item["entity_id"],
                                    "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                                })
                                st.success(f"Staged action: BLOCK on {_s_item['tracking_id']}. Click 'Commit Changes' above or commit on sign out.")
                                st.rerun()
                        with bcol2:
                            if st.button("Whitelist Entity", key=f"auth_white_{_s_item['tracking_id']}", disabled=not bool(_cur_officer), use_container_width=True):
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
                            if st.button("Resolve Dispute", key=f"auth_res_{_s_item['tracking_id']}", disabled=(not bool(_cur_officer) or _s_status != "appealed"), use_container_width=True):
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
                st.markdown(f'<h4>{get_svg_icon("bank", 20)} Bank Fraud Investigation Console</h4>', unsafe_allow_html=True)
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
                            f"<div style='background:var(--pafcci-bg-surface);border:1px solid {_b_color};"
                            f"border-left:5px solid {_b_color};padding:14px;border-radius:6px;margin-bottom:12px;box-shadow:var(--pafcci-card-shadow);'>"
                            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                            f"<h5 style='margin:0;color:var(--pafcci-text-primary);'>{_b_item['tracking_id']} | Account: {_b_item['entity_id']}</h5>"
                            f"<span style='background:{_b_color};color:#000;padding:4px 10px;border-radius:4px;font-weight:bold;font-size:12px;'>"
                            f"{_b_status.upper()}</span></div>"
                            f"<div style='font-size:12px;color:var(--pafcci-text-secondary);margin-top:6px;'>"
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
                            if st.button("Freeze Credits & Request KYC", key=f"bk_frz_{_b_item['tracking_id']}", disabled=not bool(_cur_officer), use_container_width=True):
                                _reviewer = _cur_officer["name"] if _cur_officer else f"RISK-OFFICER-{_sel_bank[:3]}"
                                _appeals_mgr.update_status(_b_item["tracking_id"], "actioned", reviewer_id=_reviewer, notes=bk_notes or "Credits frozen.")
                                st.session_state.dm_staged_actions.append({
                                    "tracking_id": _b_item["tracking_id"],
                                    "action_type": "DEBIT_FREEZE",
                                    "entity_id": _b_item["entity_id"],
                                    "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                                })
                                st.success(f"Staged action: DEBIT_FREEZE on {_b_item['tracking_id']}. Click 'Commit Changes' above or commit on sign out.")
                                st.rerun()
                        with bcol2:
                            if st.button("Dismiss Flag", key=f"bk_dis_{_b_item['tracking_id']}", disabled=not bool(_cur_officer), use_container_width=True):
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
                            if st.button("Resolve Dispute", key=f"bk_res_{_b_item['tracking_id']}", disabled=(not bool(_cur_officer) or _b_status != "appealed"), use_container_width=True):
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
                st.markdown(f'<h4>{get_svg_icon("scales", 20)} Recourse &amp; Dispute Appeals Console</h4>', unsafe_allow_html=True)
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
