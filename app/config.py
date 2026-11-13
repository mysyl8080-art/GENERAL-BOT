from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    database_path: str = os.getenv("DATABASE_PATH", "data/bot.sqlite3")
    admin_ids: tuple[int, ...] = tuple(int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit())
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    telegram_payment_token: str = os.getenv("TELEGRAM_PAYMENT_TOKEN", "")
    gold_api_key: str = os.getenv("GOLD_API_KEY", "")
    timezone: str = os.getenv("TIMEZONE", "Africa/Cairo")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "19"))
    temp_dir: str = os.getenv("TEMP_DIR", "/tmp/telegram-superbot")
    price_check_minutes: int = int(os.getenv("PRICE_CHECK_MINUTES", "30"))

settings = Settings()
Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
Path(settings.temp_dir).mkdir(parents=True, exist_ok=True)

def validate() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN غير مضبوط. أنشئ بوتًا من @BotFather وضع الرمز في متغير BOT_TOKEN.")
    if settings.max_upload_mb < 1 or settings.max_upload_mb > 19:
        raise RuntimeError("MAX_UPLOAD_MB يجب أن يكون بين 1 و19 مع Telegram Bot API العام.")
