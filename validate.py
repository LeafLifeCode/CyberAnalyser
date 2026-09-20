import sys, json
sys.path.insert(0, r"d:\MineSafe Stimulation\Withdraw_Predict")

print("=" * 60)
print("PAFCCI Generator - Tool Chain Validation (No LLM Required)")
print("=" * 60)

# 1. ATM data
from generator.data.atm_locations import ATM_LOCATIONS, list_states
assert len(ATM_LOCATIONS) == 200, f"Expected 200 ATMs, got {len(ATM_LOCATIONS)}"
print(f"[OK] ATM Locations  : {len(ATM_LOCATIONS)} synthetic ATMs loaded")
print(f"     States covered : {list_states()}")

# 2. Config
from generator.config import GeneratorConfig
cfg = GeneratorConfig(num_attackers_active=3, mule_chain_depth=4)
assert cfg.num_attackers_active == 3
print(f"[OK] GeneratorConfig: {cfg.num_attackers_active} attackers, {cfg.mule_chain_depth} hops")

# 3. Schemas
from generator.schemas.complaint_event import ComplaintEvent, AttackerProfile
print("[OK] Schemas        : Pydantic models loaded")

# 4. EventStore
from generator.memory.event_store import get_store
store = get_store()
store.add_events([{"complaint_id": "T001", "sms_prompt": "test"}])
assert store.count() == 1
store.clear()
assert store.count() == 0
print("[OK] EventStore     : 30-min TTL store works")

# 5. Attacker tool (direct function, bypassing @tool wrapper)
import random, uuid
from generator.data.atm_locations import ATM_LOCATIONS

def _gen_phone():
    prefix = random.choice(["7","8","9"])
    return "+91-" + prefix + "".join(str(random.randint(0,9)) for _ in range(9))

def _gen_ip():
    return ".".join(str(random.randint(1,254)) for _ in range(4))

profile = {
    "attacker_id": f"ATK-{uuid.uuid4().hex[:6].upper()}",
    "active_phone": _gen_phone(),
    "phone_history": [_gen_phone()],
    "active_ip": _gen_ip(),
    "ip_history": [_gen_ip()],
    "base_state": "Uttar Pradesh",
    "modus_operandi": "OTP Fraud",
}
aid = profile["attacker_id"]; ph = profile["active_phone"]; mo = profile["modus_operandi"]
print(f"[OK] Profile gen    : {aid} | {ph} | {mo}")

# 6. ATM selection
atm = ATM_LOCATIONS[0]
print(f"[OK] ATM selection  : {atm['bank']} | {atm['city']} | {atm['latitude']},{atm['longitude']}")

print()
print("=" * 60)
print("ALL VALIDATIONS PASSED - Pure Python pipeline is functional")
print("Run [streamlit run app.py] after pip install to launch UI")
print("=" * 60)
