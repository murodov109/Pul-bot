import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in (os.getenv("ADMIN_IDS") or "").split(",") if x.strip()]
PROOF_CHANNEL_ID = int(os.getenv("PROOF_CHANNEL_ID") or "0")
MANDATORY_CHANNEL_IDS = [int(x) for x in (os.getenv("MANDATORY_CHANNEL_IDS") or "").split(",") if x.strip()]
DATABASE_URL = os.getenv("DATABASE_URL", "")

MIN_WITHDRAW = int(os.getenv("MIN_WITHDRAW") or 10000)  # minimal yechish miqdori (so'm)
try:
    DAILY_WITHDRAW_LIMIT = int(os.getenv("DAILY_WITHDRAW_LIMIT") or 0)
except (TypeError, ValueError):
    DAILY_WITHDRAW_LIMIT = 0

try:
    BROADCAST_BATCH = int(os.getenv("BROADCAST_BATCH") or 700)
except (TypeError, ValueError):
    BROADCAST_BATCH = 700

def env_int_list(name, default=None):
    raw = os.getenv(name) or ""
    if raw.strip() == "":
        return default if default is not None else []
    return [int(x) for x in raw.split(",") if x.strip()]
