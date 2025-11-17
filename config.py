import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("8236617508:AAHf2qGfsd7xBmjj3WipAivPssOtjd5Cs-s")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
PROOF_CHANNEL_ID = int(os.getenv("PROOF_CHANNEL_ID", "0"))
MANDATORY_CHANNEL_IDS = [int(x) for x in os.getenv("MANDATORY_CHANNEL_IDS", "").split(",") if x.strip()]
DATABASE_URL = os.getenv("DATABASE_URL")
MIN_WITHDRAW = 10000
DAILY_WITHDRAW_LIMIT = int(os.getenv("DAILY_WITHDRAW_LIMIT", "0"))
BROADCAST_BATCH = 700
