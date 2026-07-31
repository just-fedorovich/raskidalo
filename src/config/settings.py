import os
from pathlib import Path

from dotenv import load_dotenv

# .env лежит на VeraCrypt-томе, не в репозитории (ADR-8).
# Если буква смонтированного диска отличается от R: — задай переменную окружения RASKIDALO_ENV_PATH.
ENV_PATH = Path(os.getenv("RASKIDALO_ENV_PATH", r"R:\raskidalo\.env"))
load_dotenv(ENV_PATH)

ENV = os.getenv("ENV", "dev")
BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN_DEV" if ENV == "dev" else "TELEGRAM_BOT_TOKEN_PROD"
)
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./raskidalo.sqlite")

# Секрет для анонимизации telegram_id в аналитике (Этап 2).
ANALYTICS_SALT = os.getenv("ANALYTICS_SALT", "")
