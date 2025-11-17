import os
from dotenv import load_dotenv

load_dotenv()

def env_int_list(name):
    raw = os.getenv(name) or ""
    return [int(x) for x in raw.split(",") if x.strip()]

BOT_TOKEN = os.getenv("8236617508:AAHf2qGfsd7xBmjj3WipAivPssOtjd5Cs-s") or ""

ADMIN_IDS = env_int_list("ADMIN_IDS") or [5253025422]

try:
    PROOF_CHANNEL_ID = int(os.getenv("PROOF_CHANNEL_ID") or "-1003334917965")
except ValueError:
    PROOF_CHANNEL_ID = -1003334917965

MANDATORY_CHANNEL_IDS = env_int_list("MANDATORY_CHANNEL_IDS") or [-1003334917965]

DATABASE_URL = os.getenv("DATABASE_URL") or ""

MIN_WITHDRAW = 10000
DAILY_WITHDRAW_LIMIT = int(os.getenv("DAILY_WITHDRAW_LIMIT") or 0)
BROADCAST_BATCH = int(os.getenv("BROADCAST_BATCH") or 700)
