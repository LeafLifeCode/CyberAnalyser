"""
portal_app.py
-------------
Privileged Cyber Portal — Port 8502.
Authority Identity & OTP Dispatcher for Delivery Model Action Routing (Port 8501).
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ui_icons import get_svg_icon
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

# ── Loading Screen ────────────────────────────────────────────────────────────
def _show_loading_screen():
    """Full-screen cyber splash shown once on first load (adapts to Light or Dark)."""
    components.html("""
    <script>
    (function() {
        var pDoc = (window.parent && window.parent.document) ? window.parent.document : document;
        var pWin = window.parent || window;
        if (pDoc.getElementById('pafcci-portal-loader')) return;

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
        style.id = 'pafcci-portal-loader-style';
        style.textContent = `
            #pafcci-portal-loader {
                position: fixed !important;
                top: 0 !important; left: 0 !important;
                width: 100vw !important; height: 100vh !important;
                background: ${bgColor} !important;
                z-index: 9999999 !important;
                display: flex !important;
                flex-direction: column !important;
                align-items: center !important;
                justify-content: center !important;
                transition: opacity 0.4s ease !important;
                font-family: 'Inter', -apple-system, sans-serif !important;
            }
            .p-load-logo {
                font-size: 2.6rem;
                font-weight: 800;
                letter-spacing: 0.14em;
                color: ${logoColor};
                text-shadow: ${logoShadow};
            }
            .p-load-sub {
                color: ${subColor};
                font-size: 0.82rem;
                margin-top: 14px;
                letter-spacing: 0.1em;
                text-transform: uppercase;
            }
            .p-load-bar {
                width: 220px;
                height: 4px;
                background: ${barTrack};
                border-radius: 4px;
                margin-top: 20px;
                overflow: hidden;
                position: relative;
            }
            .p-load-fill {
                position: absolute;
                top: 0; left: 0; height: 100%; width: 0%;
                background: ${barFill};
                box-shadow: ${barShadow};
                animation: pbar 1.1s cubic-bezier(0.4, 0, 0.2, 1) forwards;
            }
            @keyframes pbar {
                0% { width: 0%; }
                100% { width: 100%; }
            }
        `;
        pDoc.head.appendChild(style);

        var overlay = pDoc.createElement('div');
        overlay.id = 'pafcci-portal-loader';
        overlay.innerHTML = `
            <div class="p-load-logo">CYBER PORTAL</div>
            <div class="p-load-sub">INITIALIZING AUTHORITATIVE DIRECTORY...</div>
            <div class="p-load-bar"><div class="p-load-fill"></div></div>
        `;
        pDoc.body.appendChild(overlay);

        setTimeout(function() {
            overlay.style.opacity = '0';
            setTimeout(function() {
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
                if (style.parentNode) style.parentNode.removeChild(style);
            }, 450);
        }, 1100);
    })();
    </script>
    """, height=0, width=0)

# ── Sound & Dual-Theme Synchronization Helper ─────────────────────────────────
def _setup_audio_listeners():
    click_fp = BASE_DIR / "sound_click.mp3"
    save_fp = BASE_DIR / "sound_save.mp3"
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

# ── Dual-Theme Design System CSS ──────────────────────────────────────────────
st.markdown("""
<style>
/* ── Inter Font (Safely applied without breaking icon fonts!) ──────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stSidebar"],
h1, h2, h3, h4, h5, h6, p, label, button, input, textarea, select,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* ── PRESERVE ICON FONTS — Do NOT allow Inter to break material icons! ─────── */
[data-testid="stIconMaterial"], .material-symbols-rounded, .material-icons,
[data-testid="stSidebarCollapseButton"] span {
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

/* ── Cards / Panels / Containers ───────────────────────────────────────────── */
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
    padding: 8px 20px !important;
    background-color: var(--pafcci-bg-elevated) !important;
    color: var(--pafcci-text-secondary) !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
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

/* ── Officer Profile Button Styling in Sidebar ────────────────────────────── */
div[data-testid="stSidebar"] div[data-testid="stButton"] button {
    text-align: left !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-start !important;
    width: 100% !important;
    padding: 10px 14px !important;
    border-radius: 8px !important;
    margin-bottom: 8px !important;
    line-height: 1.35 !important;
    box-shadow: var(--pafcci-card-shadow) !important;
    transition: all 0.15s ease !important;
}

/* Status (Line 1) */
div[data-testid="stSidebar"] div[data-testid="stButton"] button code {
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    padding: 2px 8px !important;
    border-radius: 10px !important;
    background: var(--pafcci-bg-elevated) !important;
    border: 1px solid var(--pafcci-border) !important;
    color: var(--pafcci-text-secondary) !important;
    margin-bottom: 4px !important;
    font-family: 'Inter', sans-serif !important;
}

/* Name (Line 2 - larger font) */
div[data-testid="stSidebar"] div[data-testid="stButton"] button strong {
    font-size: 1.02rem !important;
    font-weight: 700 !important;
    color: var(--pafcci-text-primary) !important;
    display: block !important;
    margin-bottom: 2px !important;
    letter-spacing: -0.01em !important;
}

/* Designation (Line 3 - smaller font) */
div[data-testid="stSidebar"] div[data-testid="stButton"] button em {
    font-size: 0.78rem !important;
    font-style: normal !important;
    color: var(--pafcci-text-secondary) !important;
    display: block !important;
}

/* Inactive button */
div[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: var(--pafcci-bg-surface) !important;
    border: 1px solid var(--pafcci-border) !important;
    border-left: 4px solid var(--pafcci-border) !important;
}
div[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"]:hover {
    background-color: var(--pafcci-bg-elevated) !important;
    border-color: var(--pafcci-primary) !important;
    border-left-color: var(--pafcci-primary) !important;
    transform: translateX(2px) !important;
}

/* Active button (Primary) */
div[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {
    background-color: var(--pafcci-primary) !important;
    border: 1px solid var(--pafcci-primary-dark) !important;
    border-left: 4px solid var(--pafcci-primary-dark) !important;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25) !important;
}
div[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] strong {
    color: #FFFFFF !important;
}
div[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] em {
    color: var(--pafcci-primary-muted) !important;
}
div[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] code {
    background: rgba(255, 255, 255, 0.2) !important;
    border-color: rgba(255, 255, 255, 0.4) !important;
    color: #FFFFFF !important;
}

/* ── Standard Buttons ──────────────────────────────────────────────────────── */
button[kind="primary"], [data-testid="baseButton-primary"] {
    background-color: var(--pafcci-primary) !important;
    color: #FFFFFF !important;
    border: 1px solid var(--pafcci-primary-hover) !important;
    border-radius: 7px !important;
    font-weight: 600 !important;
    box-shadow: var(--pafcci-card-shadow) !important;
    transition: background 0.15s ease, transform 0.1s ease !important;
}
button[kind="primary"]:hover {
    background-color: var(--pafcci-primary-hover) !important;
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
button[kind="secondary"]:hover {
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

/* ── Metrics, Inputs, Tables ───────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background-color: var(--pafcci-bg-surface);
    border: 1px solid var(--pafcci-border);
    border-radius: 8px;
    padding: 12px 16px;
    box-shadow: var(--pafcci-card-shadow);
}
[data-testid="metric-container"] label {
    color: var(--pafcci-text-secondary) !important;
    font-size: 0.75rem !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: var(--pafcci-text-primary) !important;
    font-weight: 700 !important;
}
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

[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
div[data-baseweb="select"] > div {
    background-color: var(--pafcci-input-bg) !important;
    color: var(--pafcci-text-primary) !important;
    border: 1px solid var(--pafcci-border) !important;
    border-radius: 6px !important;
}
[data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus {
    border-color: var(--pafcci-primary) !important;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15) !important;
}

[data-testid="stAlert"][data-type="success"] {
    background-color: var(--pafcci-alert-success-bg) !important;
    border-left: 4px solid var(--pafcci-risk-low) !important;
    color: var(--pafcci-text-primary) !important;
}
[data-testid="stAlert"][data-type="error"] {
    background-color: var(--pafcci-alert-error-bg) !important;
    border-left: 4px solid var(--pafcci-risk-high) !important;
    color: var(--pafcci-text-primary) !important;
}
[data-testid="stAlert"][data-type="warning"] {
    background-color: var(--pafcci-alert-warn-bg) !important;
    border-left: 4px solid var(--pafcci-risk-medium) !important;
    color: var(--pafcci-text-primary) !important;
}
[data-testid="stAlert"][data-type="info"] {
    background-color: var(--pafcci-alert-info-bg) !important;
    border-left: 4px solid var(--pafcci-info) !important;
    color: var(--pafcci-text-primary) !important;
}

h1, h2, h3, h4, h5, h6 { color: var(--pafcci-text-primary) !important; font-weight: 700 !important; }
small, .stCaption, [data-testid="stCaptionContainer"] { color: var(--pafcci-text-secondary) !important; }
code {
    background-color: var(--pafcci-code-bg);
    color: var(--pafcci-code-text);
    border: 1px solid var(--pafcci-code-border);
    border-radius: 4px;
    padding: 2px 6px;
}
hr { border-color: var(--pafcci-border) !important; }
[data-testid="stModal"] > div {
    background-color: var(--pafcci-bg-surface) !important;
    border: 1px solid var(--pafcci-border) !important;
    border-radius: 10px !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15) !important;
}
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

/* ── Role accent colors ────────────────────────────────────────────────────── */
.role-lea    { background-color: rgba(99, 102, 241, 0.12); color: #6366F1; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700; }
.role-bank   { background-color: rgba(13, 148, 136, 0.12); color: #0D9488; border: 1px solid rgba(13, 148, 136, 0.3); border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700; }
.role-devops { background-color: rgba(100, 116, 139, 0.12); color: #64748B; border: 1px solid rgba(100, 116, 139, 0.3); border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700; }

/* ── Custom PAFCCI Component Classes ───────────────────────────────────────── */
.pafcci-banner {
    background: var(--pafcci-banner-bg) !important;
    padding: 18px 24px;
    border-radius: 10px;
    border: 1px solid var(--pafcci-border);
    border-left: 6px solid var(--pafcci-primary);
    margin-bottom: 20px;
    box-shadow: var(--pafcci-card-shadow);
}
.pafcci-badge-pill {
    font-size: 0.80rem;
    background: var(--pafcci-badge-bg);
    color: var(--pafcci-badge-text);
    border: 1px solid var(--pafcci-badge-border);
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 12px;
}
.pafcci-badge-lock {
    background: var(--pafcci-bg-surface);
    border: 1px solid var(--pafcci-border);
    color: var(--pafcci-text-secondary);
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    box-shadow: var(--pafcci-card-shadow);
}
.pafcci-dir-status {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--pafcci-bg-elevated);
    border: 1px solid var(--pafcci-border);
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 0.75rem;
    margin-bottom: 14px;
}
.pafcci-status-card-online {
    background: var(--pafcci-online-bg);
    border: 1px solid var(--pafcci-online-border);
    padding: 10px 14px;
    border-radius: 8px;
    text-align: center;
    box-shadow: var(--pafcci-card-shadow);
}
.pafcci-status-card-offline {
    background: var(--pafcci-offline-bg);
    border: 1px solid var(--pafcci-offline-border);
    padding: 10px 14px;
    border-radius: 8px;
    text-align: center;
    box-shadow: var(--pafcci-card-shadow);
}
.pafcci-otp-card {
    background: var(--pafcci-online-bg);
    border: 2px solid var(--pafcci-online-border);
    padding: 18px;
    border-radius: 8px;
    margin: 15px 0;
    box-shadow: var(--pafcci-card-shadow);
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

# ── Instant Audio Listener Setup ──────────────────────────────────────────────
_setup_audio_listeners()

# ── Session State Initialization ──────────────────────────────────────────────
if "selected_officer_key" not in st.session_state:
    st.session_state.selected_officer_key = list(AUTHORITY_USERS.keys())[0]
if "last_generated_otp" not in st.session_state:
    st.session_state.last_generated_otp = None
if "last_otp_user" not in st.session_state:
    st.session_state.last_otp_user = None
if "show_login_screen" not in st.session_state:
    st.session_state.show_login_screen = True
if "_portal_loaded" not in st.session_state:
    st.session_state._portal_loaded = False

# ── Initial Loading Splash ───────────────────────────────────────────────────
if not st.session_state._portal_loaded:
    _show_loading_screen()
    st.session_state._portal_loaded = True

# ── Banner Header ─────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="pafcci-banner">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 14px;">
                {get_svg_icon("shield", 34)}
                <div>
                    <h2 style="margin: 0; font-size: 1.45rem; display: flex; align-items: center; gap: 10px;">
                        CYBER PORTAL &nbsp;<span class="pafcci-badge-pill">PORT 8502</span>
                    </h2>
                    <p style="margin: 4px 0 0 0; font-size: 0.88rem;">
                        <strong>Authority Identity &amp; OTP Dispatcher:</strong> Secure one-time credentials for Action Routing &amp; Delivery Audit on Port 8501.
                    </p>
                </div>
            </div>
            <div>
                <span class="pafcci-badge-lock">
                    {get_svg_icon("lock", 14)} SINGLE SESSION LOCK
                </span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Fetch Live User Statuses ──────────────────────────────────────────────────
user_statuses = get_all_user_statuses()

# ── Left Menu / Sidebar: High-End Officer Directory ───────────────────────────
with st.sidebar:
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            {get_svg_icon("users", 20)}
            <h3 style="margin:0;font-size:1.1rem;">Authoritative Directory</h3>
        </div>
        <div style="font-size:0.75rem;color:var(--pafcci-text-secondary);margin-bottom:12px;">Select an officer to inspect live actions or issue an access OTP.</div>
        """,
        unsafe_allow_html=True,
    )

    # Status summary
    online_count = sum(1 for u in user_statuses.values() if u["status"] == "ONLINE")
    total_count = len(user_statuses)
    st.markdown(
        f"""
        <div class="pafcci-dir-status">
            <span style="color:var(--pafcci-text-secondary);">Directory Status</span>
            <span style="color:var(--pafcci-risk-low);font-weight:700;">● {online_count} Online &nbsp;&bull;&nbsp; <span style="color:var(--pafcci-text-secondary);font-weight:400;">{total_count - online_count} Offline</span></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Interactive Officer Directory
    for k, u in AUTHORITY_USERS.items():
        live = user_statuses[k]
        is_sel = (st.session_state.selected_officer_key == k)
        is_on = (live["status"] == "ONLINE")

        status_str = "● ONLINE" if is_on else "○ OFFLINE"

        btn_line1 = f"`{status_str}`"
        btn_line2 = f"**{u['name']}**"
        btn_line3 = f"*{u['role']}*"
        btn_label = "\n".join([btn_line1, btn_line2, btn_line3])

        if st.button(
            btn_label,
            key=f"officer_tab_{k}",
            type="primary" if is_sel else "secondary",
            use_container_width=True,
        ):
            if st.session_state.selected_officer_key != k:
                st.session_state.selected_officer_key = k
                st.rerun()

    st.markdown("---")
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
            {get_svg_icon("globe", 16)}
            <strong style="font-size:0.85rem;">Cross-Port Links</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("- **Cyber Portal:** `http://localhost:8502`")
    st.markdown("- **Delivery Model:** `http://localhost:8501` *(Tab 4)*")

    st.markdown("---")
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
            {get_svg_icon("terminal", 16)}
            <strong style="font-size:0.85rem;">Maintenance &amp; Logs</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    @st.dialog("Are you sure?")
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

    if st.button("Clear Data (Purge TXT & CSV)", type="secondary", use_container_width=True, key="clear_data_main_btn"):
        confirm_clear_dialog()

# ── Main Content Area ─────────────────────────────────────────────────────────
cur_user = user_statuses[st.session_state.selected_officer_key]
is_online = (cur_user["status"] == "ONLINE")

top_col1, top_col2 = st.columns([2.5, 1.5])

with top_col1:
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
            {get_svg_icon("user", 24)}
            <h3 style="margin:0;font-size:1.25rem;">Officer Profile: {cur_user['name']}</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"**Role:** `{cur_user['role']}` &nbsp;|&nbsp; "
        f"**Badge ID:** `{cur_user['badge_id']}` &nbsp;|&nbsp; "
        f"**Department:** *{cur_user['department']}*"
    )

with top_col2:
    if is_online:
        st.markdown(
            """
            <div class="pafcci-status-card-online">
                <span style="color: var(--pafcci-risk-low); font-weight: bold; font-size: 1.1rem;">● ONLINE</span>
                <div style="font-size: 0.8rem; color: var(--pafcci-text-secondary); margin-top: 4px;">Active in Delivery Model</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="pafcci-status-card-offline">
                <span style="color: var(--pafcci-text-secondary); font-weight: bold; font-size: 1.1rem;">○ OFFLINE</span>
                <div style="font-size: 0.8rem; color: var(--pafcci-text-disabled); margin-top: 4px;">No Active Session</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

# ── Tab Navigation for Selected Officer ───────────────────────────────────────
tab_otp, tab_actions, tab_session_logs = st.tabs([
    "OTP Dispatch & Access",
    f"Committed Actions ({cur_user['name']})",
    "Session Logs (TXT)",
])

# ── Tab 1: OTP Dispatch & Access ─────────────────────────────────────────────
with tab_otp:
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            {get_svg_icon("key", 20)}
            <h4 style="margin:0;font-size:1.05rem;">Generate Action Routing Access OTP</h4>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Generate a one-time 6-digit OTP for this authoritative user to unlock Action Routing decision panels and Delivery Audit on Port 8501.")

    if is_online:
        active_sess = cur_user.get("active_session", {})
        st.success(
            f"**{cur_user['name']}** currently holds an **ACTIVE SESSION**.\n\n"
            f"- **Active OTP:** `{active_sess.get('otp', '******')}`\n"
            f"- **Login Time:** `{active_sess.get('login_time', 'N/A')}`\n\n"
            "This user can already unlock Action Routing in Port 8501 using this OTP."
        )

        st.info("Single-User Rule Enforced: No more than one user can be logged into the same username at the same time.")

        if st.button("Force Sign Out Active Session", key=f"force_logout_{cur_user['username']}"):
            sign_out_user(cur_user["username"], commit_staged=False)
            st.warning(f"Session terminated for {cur_user['name']}. Status is now OFFLINE.")
            st.rerun()

    else:
        st.markdown(
            f"Click below to generate a fresh 6-digit access code for **{cur_user['name']}**. "
            "Once generated, status transitions to `ONLINE`."
        )

        if (
            st.session_state.last_generated_otp
            and st.session_state.last_otp_user == cur_user["username"]
        ):
            st.markdown(
                f"""
                <div class="pafcci-otp-card">
                    <div style="color: var(--pafcci-text-secondary); font-size: 0.95rem;">One-Time Password Generated for <b>{cur_user['name']}</b>:</div>
                    <div style="color: var(--pafcci-risk-low); font-family: monospace; font-size: 2.2rem; font-weight: bold; letter-spacing: 6px; margin: 10px 0;">
                        {st.session_state.last_generated_otp}
                    </div>
                    <div style="color: var(--pafcci-text-secondary); font-size: 0.85rem;">
                        Copy this OTP and paste it into <b>Port 8501 (Tab 4: Delivery Model &amp; Action Routing)</b> to unlock enforcement actions.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button("Return to Login Screen", key="return_login_btn", type="primary"):
                st.session_state.last_generated_otp = None
                st.session_state.last_otp_user = None
                st.rerun()

        else:
            if st.button(f"Generate OTP for {cur_user['name']}", type="primary", key=f"gen_otp_{cur_user['username']}"):
                try:
                    otp_code, sess_data = generate_otp_for_user(cur_user["username"])
                    st.session_state.last_generated_otp = otp_code
                    st.session_state.last_otp_user = cur_user["username"]
                    st.success(f"OTP generated successfully for {cur_user['name']}!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"OTP Generation Error: {exc}")

# ── Tab 2: Committed Actions for this Officer ────────────────────────────────
with tab_actions:
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            {get_svg_icon("report", 20)}
            <h4 style="margin:0;font-size:1.05rem;">Actions Committed by {cur_user['name']}</h4>
        </div>
        """,
        unsafe_allow_html=True,
    )
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
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            {get_svg_icon("terminal", 20)}
            <h4 style="margin:0;font-size:1.05rem;">Sign-In &amp; Sign-Out Ledger (Local TXT File)</h4>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Records every authentication and session termination event (`cyber_portal_session_log.txt`).")

    logs = get_recent_session_logs(max_lines=60)
    if not logs:
        st.info("No session log events recorded yet.")
    else:
        log_content = "\n".join(logs)
        st.text_area("Live Log Output", value=log_content, height=350, disabled=True)
