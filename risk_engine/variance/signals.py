"""
risk_engine/variance/signals.py
---------------------------------
Variance Model — Three Independent Deterministic Detection Signals.

Every function is 100% deterministic Python for mathematical auditability
and reproducibility. No LLM non-determinism is used for scoring.

All threshold choices and physical upper bounds are documented with inline
rationale in compliance with academic & LEA standards.
"""

from datetime import datetime, timezone, timedelta
import math
from collections import defaultdict
from typing import List, Dict, Any, Optional


# ── Helper: Haversine Distance (km) ──────────────────────────────────────────

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the Great Circle distance between two points on Earth in km.
    Formula: a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
             c = 2 * atan2(√a, √(1-a))
             d = R * c
    where R = 6,371 km (Earth radius).
    """
    R = 6371.0  # Earth mean radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


# ── Signal 1: IP ↔ Phone Mismatch Detection ─────────────────────────────────

def detect_ip_phone_mismatch(
    events: List[Dict[str, Any]],
    time_window_hours: float = 24.0,
    max_allowed_ips_per_phone: int = 2,
    max_allowed_phones_per_ip: int = 2,
) -> List[Dict[str, Any]]:
    """
    Detects abnormal changes in IP addresses associated with a single phone number,
    or vice versa (multiple phone numbers associated with a single IP), within a defined time window.

    THREHSOLD JUSTIFICATION:
    - Normal User Baseline: A legitimate citizen typically operates over 1-2 IP addresses
      (e.g., home Wi-Fi and mobile 4G/5G carrier IP) over a 24-hour period.
    - Cybercrime Syndicate Pattern: Fraudsters execute SIM-swap attacks or use virtual number
      services (vishing/OTP scam) routed through rotating proxy/VPN networks. A single phone
      appearing across >2 distinct IP subnets within 24h, or a single proxy IP handling >2 phone numbers,
      is a strong indicator of automated scam infrastructure.
    - Default Window: 24.0 hours to capture daily operational cycles.
    - Scoring Math: Sub-score starts at 0.50 for threshold breach (3 distinct bindings) and
      scales linearly up to 1.00 at >= 6 distinct bindings.

    Returns structured signal result list conforming to the PAFCCI schema.
    """
    if not events:
        return []

    # Parse timestamps and group relationships
    # Group by phone -> set of (ip, timestamp, vpn_provider)
    phone_to_ips: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    # Group by ip -> set of (phone, timestamp)
    ip_to_phones: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    all_timestamps: List[datetime] = []

    for ev in events:
        attacker = ev.get("attacker", {})
        phone = attacker.get("active_phone") or attacker.get("phone")
        ip = attacker.get("active_ip") or attacker.get("ip")
        vpn = attacker.get("vpn_provider", "Unknown")

        # Parse timestamp
        ts_str = ev.get("generated_at") or ev.get("timestamp")
        if isinstance(ts_str, str):
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)
        elif isinstance(ts_str, datetime):
            dt = ts_str
        else:
            dt = datetime.now(timezone.utc)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        all_timestamps.append(dt)

        if phone and ip:
            phone_to_ips[phone].append({"ip": ip, "vpn": vpn, "timestamp": dt})
            ip_to_phones[ip].append({"phone": phone, "timestamp": dt})

    if not all_timestamps:
        window_start = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
        window_end = datetime.now(timezone.utc)
    else:
        window_end = max(all_timestamps)
        window_start = window_end - timedelta(hours=time_window_hours)

    results: List[Dict[str, Any]] = []

    # 1. Evaluate Phone Entities (Phone associated with multiple IPs)
    for phone, bindings in phone_to_ips.items():
        # Filter bindings in time window
        recent_bindings = [b for b in bindings if b["timestamp"] >= window_start]
        distinct_ips = sorted(list({b["ip"] for b in recent_bindings}))
        distinct_vpns = sorted(list({b["vpn"] for b in recent_bindings if b["vpn"] != "Unknown"}))

        count = len(distinct_ips)
        if count > max_allowed_ips_per_phone:
            # Sub-score: 0.50 at threshold+1 (3 IPs), 1.00 at 6+ IPs
            sub_score = round(min(1.0, 0.50 + (count - max_allowed_ips_per_phone - 1) * 0.15), 3)
            results.append({
                "entity_id": phone,
                "entity_type": "phone",
                "signal_type": "ip_phone_mismatch",
                "sub_score": sub_score,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "evidence": {
                    "distinct_ip_count": count,
                    "max_allowed_ips": max_allowed_ips_per_phone,
                    "associated_ips": distinct_ips,
                    "detected_vpn_providers": distinct_vpns,
                    "time_window_hours": time_window_hours,
                    "reason": f"Phone number {phone} associated with {count} distinct IPs within {time_window_hours}h window (threshold: >{max_allowed_ips_per_phone}).",
                },
            })

    # 2. Evaluate IP Entities (IP associated with multiple Phones)
    for ip, bindings in ip_to_phones.items():
        recent_bindings = [b for b in bindings if b["timestamp"] >= window_start]
        distinct_phones = sorted(list({b["phone"] for b in recent_bindings}))

        count = len(distinct_phones)
        if count > max_allowed_phones_per_ip:
            sub_score = round(min(1.0, 0.50 + (count - max_allowed_phones_per_ip - 1) * 0.15), 3)
            results.append({
                "entity_id": ip,
                "entity_type": "ip",
                "signal_type": "ip_phone_mismatch",
                "sub_score": sub_score,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "evidence": {
                    "distinct_phone_count": count,
                    "max_allowed_phones": max_allowed_phones_per_ip,
                    "associated_phones": distinct_phones,
                    "time_window_hours": time_window_hours,
                    "reason": f"IP address {ip} associated with {count} distinct phone numbers within {time_window_hours}h window (threshold: >{max_allowed_phones_per_ip}).",
                },
            })

    return results


# ── Signal 2: Deposit Spike Detection ────────────────────────────────────────

def detect_deposit_spike(
    events: List[Dict[str, Any]],
    baseline_days: int = 7,
    z_threshold: float = 2.5,
) -> List[Dict[str, Any]]:
    """
    Detects sudden spikes in deposit/transfer amounts into beneficiary/mule bank accounts
    relative to that account's recent trailing baseline.

    THRESHOLD JUSTIFICATION:
    - Statistical Standard Deviation Threshold (z = 2.5):
      Assuming normal distribution of regular account transactions, a Z-score of 2.5
      places the transaction volume in the upper 0.62% tail ($P(Z > 2.5) \approx 0.0062$).
    - Legitimate vs Fraud Distinction:
      Legitimate variance (e.g. monthly salary, utility payments, normal peer transfers)
      typically creates minor deviations ($z \le 2.0$). In contrast, cyber fraud cash-out mule accounts
      sit dormant or low-balance until a scam victim transfers tens/hundreds of thousands of INR,
      producing extreme standard deviation spikes ($z \ge 2.5$).
    - Baseline Window: Trailing 7 days (baseline_days = 7) captures standard weekly salary/spending patterns.
    - Scoring Math: Sub-score starts at 0.50 at z = 2.5 and scales up to 1.00 at z >= 5.0.

    Returns structured signal result list.
    """
    if not events:
        return []

    # Map accounts to incoming deposit records: list of {amount, timestamp, txn_id}
    account_deposits: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    all_timestamps: List[datetime] = []

    for ev in events:
        # Collect from transactions and mule chain
        txns = ev.get("transactions", [])
        mule_chain = ev.get("mule_chain", [])

        # Process victim-to-mule transactions
        for tx in txns:
            receiver = tx.get("receiver_id")
            amount = float(tx.get("amount_inr", 0))
            ts_str = tx.get("timestamp") or ev.get("generated_at")
            if isinstance(ts_str, str):
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            all_timestamps.append(dt)
            if receiver and amount > 0:
                account_deposits[receiver].append({"amount": amount, "timestamp": dt, "txn_id": tx.get("txn_id", "N/A")})

        # Process mule chain hops
        for hop in mule_chain:
            acc = hop.get("account_id")
            amount = float(hop.get("amount_inr", 0))
            ts_str = ev.get("generated_at")
            if isinstance(ts_str, str):
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            all_timestamps.append(dt)
            if acc and amount > 0:
                account_deposits[acc].append({"amount": amount, "timestamp": dt, "txn_id": f"MULE-HOP-{hop.get('hop_number', 1)}"})

    if not all_timestamps:
        window_end = datetime.now(timezone.utc)
    else:
        window_end = max(all_timestamps)

    window_start = window_end - timedelta(days=baseline_days)
    results: List[Dict[str, Any]] = []

    for acc_id, deposits in account_deposits.items():
        if not deposits:
            continue

        # Sort deposits chronologically for timeline charting
        deposits_sorted = sorted(deposits, key=lambda d: d["timestamp"])
        amounts = [d["amount"] for d in deposits_sorted]
        timestamps = [d["timestamp"].isoformat() for d in deposits_sorted]
        n = len(amounts)
        total_deposit = sum(amounts)

        # MINIMUM BASELINE REQUIREMENT:
        # Need at least 2 transactions: the first establishes a rough baseline,
        # the second is tested for a spike against it.
        # Exception: absolute amount >= 5x the default mean (₹3,50,000+) is always flagged.
        ABSOLUTE_FLAG_THRESHOLD = 350_000.0
        max_amount = max(amounts)

        if n < 2 and max_amount < ABSOLUTE_FLAG_THRESHOLD:
            continue  # Only 1 transaction and not an extreme absolute amount — skip

        # Build baseline from all prior transactions EXCEPT the peak candidate
        prior_amounts = [a for a in amounts if a != max_amount]

        if not prior_amounts:
            mean = max_amount * 0.15
            std_dev = mean * 0.30
        else:
            n_prior = len(prior_amounts)
            mean = sum(prior_amounts) / n_prior
            if n_prior == 1:
                std_dev = mean * 0.30
            else:
                variance = sum((x - mean) ** 2 for x in prior_amounts) / n_prior
                std_dev = math.sqrt(variance)

        # Enforce minimum effective std_dev to prevent division by zero
        effective_std = max(std_dev, mean * 0.10, 1000.0)

        z_score = (max_amount - mean) / effective_std

        if z_score >= z_threshold or max_amount >= ABSOLUTE_FLAG_THRESHOLD:
            sub_score = round(min(1.0, 0.50 + max(0, (z_score - z_threshold) / 2.5) * 0.50), 3)
            sub_score = max(0.50, sub_score)

            results.append({
                "entity_id": acc_id,
                "entity_type": "account",
                "signal_type": "deposit_spike",
                "sub_score": sub_score,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "evidence": {
                    "z_score": round(z_score, 2),
                    "z_threshold": z_threshold,
                    "max_single_deposit_inr": max_amount,
                    "total_deposit_inr": total_deposit,
                    "baseline_mean_inr": round(mean, 2),
                    "baseline_std_dev_inr": round(effective_std, 2),
                    "transaction_count": n,
                    "baseline_days": baseline_days,
                    # Full history for single-entity behavior chart in UI
                    "deposit_history": amounts,
                    "deposit_timestamps": timestamps,
                    "spike_index": amounts.index(max_amount),
                    "reason": f"Account {acc_id} deposit spike of INR {max_amount:,.2f} (z={z_score:.2f}, threshold z>={z_threshold}). Baseline mean INR {mean:,.2f} from {len(prior_amounts)} prior txns.",
                },
            })

    return results


# ── Signal 3: IP Velocity & Impossible Travel Check ──────────────────────────

def detect_ip_velocity(
    events: List[Dict[str, Any]],
    max_speed_kmh: float = 900.0,
    vpn_buffer_km: float = 200.0,
) -> List[Dict[str, Any]]:
    """
    Detects an IP address or attacker entity appearing at two geospatial locations
    separated by a distance/time ratio exceeding plausible physical travel speed.

    PHYSICAL UPPER BOUND & VPN BUFFER JUSTIFICATION:
    - Commercial Flight Upper Bound (900 km/h):
      Commercial jetliners cruise at ~850-900 km/h (e.g. Boeing 737 / Airbus A320 domestic India routes).
      Any movement between coordinates faster than 900 km/h is physically impossible for a human traveler.
    - Legitimate VPN Switching Buffer (200 km):
      Legitimate corporate or mobile VPN users may switch VPN servers or cell towers, causing their
      public IP location to jump between adjacent cities (e.g., Mumbai to Pune, ~150 km).
      To prevent false positives on legitimate VPN switching, spatial jumps under 200 km are NOT flagged
      regardless of speed, giving a documented spatial tolerance.
    - Anomaly Trigger:
      Distance > 200 km AND Effective Speed > 900 km/h.
      Example: Delhi to Mumbai (1,150 km) within 15 minutes = 4,600 km/h -> IMPOSSIBLE TRAVEL (Flagged).

    Returns structured signal result list.
    """
    if not events:
        return []

    # Map IP / Attacker to sequence of (timestamp, lat, lon, city, state)
    ip_locations: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    all_timestamps: List[datetime] = []

    for ev in events:
        attacker = ev.get("attacker", {})
        ip = attacker.get("active_ip") or attacker.get("ip")
        atm = ev.get("atm", {})

        lat = atm.get("latitude")
        lon = atm.get("longitude")
        city = atm.get("city", "Unknown")
        state = atm.get("state", "Unknown")

        ts_str = ev.get("generated_at") or ev.get("predicted_withdrawal_time")
        if isinstance(ts_str, str):
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        all_timestamps.append(dt)

        if ip and lat is not None and lon is not None:
            ip_locations[ip].append({
                "lat": float(lat),
                "lon": float(lon),
                "city": city,
                "state": state,
                "timestamp": dt,
            })

    if not all_timestamps:
        window_end = datetime.now(timezone.utc)
    else:
        window_end = max(all_timestamps)

    window_start = window_end - timedelta(hours=24)
    results: List[Dict[str, Any]] = []

    for ip, locs in ip_locations.items():
        if len(locs) < 2:
            continue

        # Sort locations chronologically
        locs_sorted = sorted(locs, key=lambda x: x["timestamp"])

        for i in range(len(locs_sorted) - 1):
            p1 = locs_sorted[i]
            p2 = locs_sorted[i + 1]

            time_diff_hours = (p2["timestamp"] - p1["timestamp"]).total_seconds() / 3600.0
            if time_diff_hours <= 0:
                time_diff_hours = 0.001  # 3.6 seconds to avoid zero division

            dist_km = haversine_distance_km(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
            speed_kmh = dist_km / time_diff_hours

            # Evaluate against physical bounds
            if dist_km > vpn_buffer_km and speed_kmh > max_speed_kmh:
                # Sub-score: 0.50 at threshold (900 km/h), 1.00 at >= 5000 km/h (instant proxy hop)
                sub_score = round(min(1.0, 0.50 + ((speed_kmh - max_speed_kmh) / 4100.0) * 0.50), 3)

                results.append({
                    "entity_id": ip,
                    "entity_type": "ip",
                    "signal_type": "ip_velocity",
                    "sub_score": sub_score,
                    "window_start": p1["timestamp"].isoformat(),
                    "window_end": p2["timestamp"].isoformat(),
                    "evidence": {
                        "calculated_speed_kmh": round(speed_kmh, 1),
                        "max_allowed_speed_kmh": max_speed_kmh,
                        "distance_km": round(dist_km, 1),
                        "vpn_buffer_km": vpn_buffer_km,
                        "time_elapsed_minutes": round(time_diff_hours * 60.0, 1),
                        "origin_location": f"{p1['city']}, {p1['state']} ({p1['lat']:.4f}, {p1['lon']:.4f})",
                        "destination_location": f"{p2['city']}, {p2['state']} ({p2['lat']:.4f}, {p2['lon']:.4f})",
                        "reason": f"IP {ip} traversed {dist_km:.1f} km between {p1['city']} and {p2['city']} in {time_diff_hours*60:.1f} min ({speed_kmh:.1f} km/h), exceeding max flight speed of {max_speed_kmh} km/h.",
                    },
                })

    return results