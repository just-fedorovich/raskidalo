"""Настройки приватности (Этап 6, флоу 0.5.5).

level: 'friends' — локацию видят только взаимные друзья; 'none' — никто.
granularity: 'country_city' | 'country_only' | 'nothing' — что именно видно.
invisible_mode: невидимка — временный «выключатель» поверх level (ADR-14).

Строка настроек создаётся при регистрации (Этап 2); get_settings страхует
случай, когда её нет (старые записи), — создаёт с дефолтами ADR-1.
"""

from sqlalchemy.orm import Session

from src.db.models import VisibilitySettings

LEVELS = ("friends", "none")
GRANULARITIES = ("country_city", "country_only", "nothing")


def get_settings(session: Session, user_id: int) -> VisibilitySettings:
    """Настройки пользователя (user_id = telegram_id, правило 5.F)."""
    settings = session.get(VisibilitySettings, user_id)
    if settings is None:
        settings = VisibilitySettings(
            user_id=user_id,
            level="friends",
            granularity="country_city",
            invisible_mode=False,
        )
        session.add(settings)
        session.flush()
    return settings
