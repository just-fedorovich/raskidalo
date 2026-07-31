import hashlib
import hmac

from sqlalchemy.orm import Session

from src.config.settings import ANALYTICS_SALT
from src.db.models import AnalyticsEvent
from src.services.clock import utcnow


def anon_user_id(telegram_id: int) -> str:
    """Анонимный идентификатор: HMAC-SHA256 от telegram_id с секретной солью."""
    return hmac.new(
        ANALYTICS_SALT.encode(), str(telegram_id).encode(), hashlib.sha256
    ).hexdigest()


def track(
    session: Session,
    event_type: str,
    telegram_id: int,
    payload: dict | None = None,
) -> None:
    session.add(
        AnalyticsEvent(
            event_type=event_type,
            user_id_anon=anon_user_id(telegram_id),
            payload_json=payload,
            created_at_utc=utcnow(),
        )
    )
