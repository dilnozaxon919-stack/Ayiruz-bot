import os
from dotenv import load_dotenv

load_dotenv()

# Telegram bot tokeni (@BotFather dan olinadi) — Render'da Environment Variable sifatida qo'yiladi
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Supabase Postgres ulanish manzili (Supabase -> Project Settings -> Database -> Connection string -> URI)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Admin(lar) Telegram ID raqami(lari), vergul bilan ajratilgan: masalan "111111,222222"
ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

# Har bir referal uchun beriladigan UC miqdori
REFERRAL_BONUS = float(os.getenv("REFERRAL_BONUS", "1.5"))

# Eng kam chiqarib olish miqdori (UC)
MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "30"))

# Render bepul tarifda serverni "uyg'oq" ushlab turish uchun ochiladigan port
PORT = int(os.getenv("PORT", "10000"))
