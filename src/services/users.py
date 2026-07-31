from sqlalchemy.orm import Session

from src.db.models import User, VisibilitySettings
from src.services.clock import utcnow


def _ensure_visibility(session: Session, telegram_id: int) -> None:
    """Создаёт настройки видимости с дефолтами ADR-2, если их ещё нет."""
    if session.get(VisibilitySettings, telegram_id) is None:
        session.add(VisibilitySettings(user_id=telegram_id))


def register_user(
    session: Session,
    telegram_id: int,
    first_name: str | None,
    username: str | None,
) -> bool:
    """Регистрация/возврат по флоу 0.5.1.

    Возвращает True, если пользователь новый (или реактивирован после
    /deleteme), и False, если уже активен.
    """
    user = session.get(User, telegram_id)

    if user is None:
        session.add(
            User(
                telegram_id=telegram_id,
                first_name=first_name,
                username=username,
                created_at_utc=utcnow(),
                deleted_at_utc=None,
            )
        )
        _ensure_visibility(session, telegram_id)
        return True

    if user.deleted_at_utc is not None:
        # Был удалён через /deleteme — заводим как нового (флоу 0.5.1, ветка 5).
        user.first_name = first_name
        user.username = username
        user.deleted_at_utc = None
        _ensure_visibility(session, telegram_id)
        return True

    # Активен: освежаем имя и username из Telegram (ADR-2).
    user.first_name = first_name
    user.username = username
    return False
