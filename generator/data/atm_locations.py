"""
generator/data/atm_locations.py
--------------------------------
200 SYNTHETIC, CONSTANT ATM locations across India.
Seeded with random.seed(42) so coordinates NEVER change between runs.
All entries are labelled SYNTHETIC — not real ATM addresses.
"""

import random

random.seed(42)

# (city, state, base_lat, base_lon, num_atms_in_cluster)
_CITY_CLUSTERS = [
    ("Mumbai",      "Maharashtra",    19.0760,  72.8777, 25),
    ("Delhi",       "Delhi",          28.6139,  77.2090, 25),
    ("Bangalore",   "Karnataka",      12.9716,  77.5946, 20),
    ("Chennai",     "Tamil Nadu",     13.0827,  80.2707, 20),
    ("Hyderabad",   "Telangana",      17.3850,  78.4867, 15),
    ("Kolkata",     "West Bengal",    22.5726,  88.3639, 15),
    ("Pune",        "Maharashtra",    18.5204,  73.8567, 10),
    ("Ahmedabad",   "Gujarat",        23.0225,  72.5714, 10),
    ("Jaipur",      "Rajasthan",      26.9124,  75.7873, 10),
    ("Lucknow",     "Uttar Pradesh",  26.8467,  80.9462, 10),
    ("Kochi",       "Kerala",         9.9312,   76.2673, 10),
    ("Bhopal",      "Madhya Pradesh", 23.2599,  77.4126, 10),
    ("Chandigarh",  "Punjab",         30.7333,  76.7794, 10),
    ("Patna",       "Bihar",          25.5941,  85.1376, 10),
]  # Total ATMs: 25+25+20+20+15+15+10*8 = 200

_BANKS = [
    "SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "PNB",
    "Bank of Baroda", "Canara Bank", "Kotak Mahindra", "Yes Bank",
    "Union Bank of India", "IndusInd Bank", "IDBI Bank",
]
_ATM_TYPES = ["On-site Branch ATM", "Off-site ATM", "White Label ATM"]
_AREA_LABELS = ["Market Area", "Railway Station", "Bus Stand", "Mall",
                "Residential Area", "Industrial Zone", "Hospital Road",
                "College Road", "IT Park", "Main Road"]

# Build the fixed 200-entry list
ATM_LOCATIONS: list[dict] = []
_atm_idx = 0

for city, state, base_lat, base_lon, count in _CITY_CLUSTERS:
    for j in range(count):
        # Inland coordinate bounds to prevent coastal ATMs landing in the sea/water
        if city == "Chennai":
            lat = round(base_lat + random.uniform(-0.06, 0.06), 6)
            lon = round(base_lon + random.uniform(-0.08, 0.00), 6)  # West / Inland of Marina Coast
        elif city == "Kochi":
            lat = round(base_lat + random.uniform(-0.05, 0.05), 6)
            lon = round(base_lon + random.uniform(0.01, 0.08), 6)   # East / Inland of Ernakulam/Vembanad
        elif city == "Mumbai":
            lat = round(base_lat + random.uniform(-0.06, 0.06), 6)
            lon = round(base_lon + random.uniform(0.01, 0.08), 6)   # East / Inland of Arabian Sea
        else:
            lat = round(base_lat + random.uniform(-0.06, 0.06), 6)
            lon = round(base_lon + random.uniform(-0.06, 0.06), 6)

        bank = random.choice(_BANKS)
        area = random.choice(_AREA_LABELS)
        ATM_LOCATIONS.append({
            "atm_id":    f"ATM-{_atm_idx:03d}",
            "bank":      bank,
            "location":  f"{bank}, {area}, {city}",
            "city":      city,
            "state":     state,
            "latitude":  lat,
            "longitude": lon,
            "atm_type":  random.choice(_ATM_TYPES),
            "synthetic": True,
        })
        _atm_idx += 1

assert len(ATM_LOCATIONS) == 200, f"Expected 200 ATMs, got {len(ATM_LOCATIONS)}"

# Convenient lookup helpers
def get_all_atms() -> list[dict]:
    return ATM_LOCATIONS

def get_atms_by_state(state: str) -> list[dict]:
    return [a for a in ATM_LOCATIONS if a["state"] == state]

def get_random_atm(seed: int | None = None) -> dict:
    rng = random.Random(seed)
    return rng.choice(ATM_LOCATIONS)

def list_states() -> list[str]:
    return sorted({a["state"] for a in ATM_LOCATIONS})
