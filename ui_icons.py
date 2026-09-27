"""
ui_icons.py — Crisp inline SVG outline icons in PAFCCI Primary Blue (#2563EB).
Guaranteed 100% offline, zero external font dependencies, no missing-glyph boxes ([]).
"""

import base64

_PATHS = {
    # Shield (PAFCCI security brand)
    "shield": (
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
        '<path d="m9 12 2 2 4-4"/>'
    ),
    # Document / Report (Component 1)
    "report": (
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="16" y1="13" x2="8" y2="13"/>'
        '<line x1="16" y1="17" x2="8" y2="17"/>'
        '<line x1="10" y1="9" x2="8" y2="9"/>'
    ),
    # Chart / Activity / Variance (Component 2a)
    "variance": (
        '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>'
    ),
    # Map Pin / Heatmap (Component 2b)
    "heatmap": (
        '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>'
        '<circle cx="12" cy="10" r="3"/>'
    ),
    # Megaphone / Broadcast (Component 4)
    "delivery": (
        '<path d="m3 11 18-5v12L3 14v-3z"/>'
        '<path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>'
    ),
    # CPU / Processor / Engine
    "cpu": (
        '<rect x="4" y="4" width="16" height="16" rx="2"/>'
        '<rect x="9" y="9" width="6" height="6"/>'
        '<line x1="9" y1="1" x2="9" y2="4"/>'
        '<line x1="15" y1="1" x2="15" y2="4"/>'
        '<line x1="9" y1="20" x2="9" y2="23"/>'
        '<line x1="15" y1="20" x2="15" y2="23"/>'
        '<line x1="20" y1="9" x2="23" y2="9"/>'
        '<line x1="20" y1="14" x2="23" y2="14"/>'
        '<line x1="1" y1="9" x2="4" y2="9"/>'
        '<line x1="1" y1="14" x2="4" y2="14"/>'
    ),
    # Users / Attacker / Directory
    "users": (
        '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="4"/>'
        '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>'
        '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
    ),
    # Credit card / Transaction settings
    "credit_card": (
        '<rect width="20" height="14" x="2" y="5" rx="2"/>'
        '<line x1="2" x2="22" y1="10" y2="10"/>'
    ),
    # Mule Chain Branch
    "branch": (
        '<line x1="6" y1="3" x2="6" y2="15"/>'
        '<circle cx="18" cy="6" r="3"/>'
        '<circle cx="6" cy="18" r="3"/>'
        '<path d="M18 9a9 9 0 0 1-9 9"/>'
    ),
    # Clock / Timing
    "clock": (
        '<circle cx="12" cy="12" r="10"/>'
        '<polyline points="12 6 12 12 16 14"/>'
    ),
    # Single User Profile
    "user": (
        '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>'
        '<circle cx="12" cy="7" r="4"/>'
    ),
    # Key / OTP Access
    "key": (
        '<circle cx="7.5" cy="15.5" r="5.5"/>'
        '<path d="m21 2-9.6 9.6"/>'
        '<path d="m15.5 7.5 3 3"/>'
        '<path d="m18.5 4.5 3 3"/>'
    ),
    # Bank institution / ATM
    "bank": (
        '<line x1="2" y1="20" x2="22" y2="20"/>'
        '<line x1="12" y1="2" x2="2" y2="7"/>'
        '<line x1="12" y1="2" x2="22" y2="7"/>'
        '<line x1="2" y1="7" x2="22" y2="7"/>'
        '<line x1="5" y1="10" x2="5" y2="17"/>'
        '<line x1="9" y1="10" x2="9" y2="17"/>'
        '<line x1="15" y1="10" x2="15" y2="17"/>'
        '<line x1="19" y1="10" x2="19" y2="17"/>'
    ),
    # Flag / Flagged entity
    "flag": (
        '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/>'
        '<line x1="4" y1="22" x2="4" y2="15"/>'
    ),
    # Globe / IP Network
    "globe": (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="2" y1="12" x2="22" y2="12"/>'
        '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
    ),
    # Phone / Mobile
    "phone": (
        '<rect x="5" y="2" width="14" height="20" rx="2" ry="2"/>'
        '<line x1="12" y1="18" x2="12.01" y2="18"/>'
    ),
    # Phone Slash (Binding anomaly)
    "phone_slash": (
        '<line x1="1" y1="1" x2="23" y2="23"/>'
        '<path d="M17 2H7a2 2 0 0 0-2 2v14"/>'
        '<path d="M19 8v12a2 2 0 0 1-2 2H7"/>'
    ),
    # Scales / Appeals & Dispute
    "scales": (
        '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>'
        '<path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>'
        '<path d="M7 21h10"/>'
        '<path d="M12 3v18"/>'
        '<path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>'
    ),
    # Terminal / Logs
    "terminal": (
        '<polyline points="4 17 10 11 4 5"/>'
        '<line x1="12" y1="19" x2="20" y2="19"/>'
    ),
    # Padlock
    "lock": (
        '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    ),
    # Chat / SMS
    "chat": (
        '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'
    ),
    # Table / Matrix
    "table": (
        '<rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<line x1="3" y1="9" x2="21" y2="9"/>'
        '<line x1="3" y1="15" x2="21" y2="15"/>'
        '<line x1="9" y1="3" x2="9" y2="21"/>'
        '<line x1="15" y1="3" x2="15" y2="21"/>'
    ),
    # Radar / Crosshair
    "crosshair": (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="22" y1="12" x2="18" y2="12"/>'
        '<line x1="6" y1="12" x2="2" y2="12"/>'
        '<line x1="12" y1="6" x2="12" y2="2"/>'
        '<line x1="12" y1="22" x2="12" y2="18"/>'
    ),
}

def get_svg_icon(name: str, size: int = 20, color: str = "currentColor") -> str:
    """Returns an inline SVG string for the specified icon name.
    Defaults to 'currentColor' for automatic adaptation across Dark and Light themes.
    """
    path_content = _PATHS.get(name, _PATHS["shield"])
    return (
        f'<svg class="pafcci-icon" xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        f'style="vertical-align:middle;display:inline-block;flex-shrink:0;">{path_content}</svg>'
    )

def get_svg_data_uri(name: str, size: int = 20, color: str = "#2563EB") -> str:
    """Returns a base64 data:image/svg+xml URI suitable for markdown ![icon](uri)."""
    svg_str = get_svg_icon(name, size, color)
    b64 = base64.b64encode(svg_str.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"
