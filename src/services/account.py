"""Полное удаление аккаунта (Этап 7, флоу 0.5.6, ADR-9).

Пользователь — soft delete (deleted_at_utc + затирание имени),
чтобы повторный /start мог реактивировать аккаунт (ветка Этапа 2).
Локация, настройки и дружбы — hard delete (privacy by default).
Аналитика не трогается — она анонимна (HMAC, ADR-1).
"""

from sqlalchemy import delete, or_
from sqlalchemy.orm import Session

from src.db.models import Friendship, Location, User, VisibilitySettings
from src.services.clock import utcnow


def delete_account(session: Session, user_id: int) -> bool:
    """False, если пользователь не найден или уже удалён."""
    user = session.get(User, user_id)
    if user is None or user.deleted_at_utc is not None:
        return False
    session.execute(delete(Location).where(Location.user_id == user_id))
    session.execute(
        delete(VisibilitySettings).where(VisibilitySettings.user_id == user_id)
    )
    session.execute(
        delete(Friendship).where(
            or_(
                Friendship.user_a_id == user_id,
                Friendship.user_b_id == user_id,
            )
        )
    )
    user.first_name = "Удалённый аккаунт"
    user.username = None
    user.deleted_at_utc = utcnow()
    return True
