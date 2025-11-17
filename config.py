import os
from dotenv import load_dotenv

load_dotenv()  

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in (os.getenv("ADMIN_IDS") or "").split(",") if x.strip()]
PROOF_CHANNEL_ID = int(os.getenv("PROOF_CHANNEL_ID") or "0")
MANDATORY_CHANNEL_IDS = [int(x) for x in (os.getenv("MANDATORY_CHANNEL_IDS") or "").split(",") if x.strip()]
DATABASE_URL = os.getenv("DATABASE_URL", "")
