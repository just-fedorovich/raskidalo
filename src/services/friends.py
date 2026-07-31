"""Логика дружбы (Этап 4, ADR-12).

Одна строка friendships на пару: user_a_id — кто отправил заявку,
user_b_id — кому. status: pending (ждёт ответа) или mutual (друзья).
Отклонённая заявка удаляется — её можно отправить снова.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import Friendship, User
from src.services.clock import utcnow


def find_user_by_username(session: Session, username: str) -> User | None:
    """Активный пользователь по @username (без учёта регистра)."""
    uname = username.strip().lstrip("@").lower()
    if not uname:
        return None
    return session.scalar(
        select(User).where(
            func.lower(User.username) == uname,
            User.deleted_at_utc.is_(None),
        )
    )


def get_friendship(session: Session, user_id: int, other_id: int) -> Friendship | None:
    return session.get(Friendship, (user_id, other_id)) or session.get(
        Friendship, (other_id, user_id)
    )


def send_request(session: Session, from_id: int, to_id: int) -> str:
    """Отправить заявку. Результат:
    sent | auto_mutual | already_pending | already_mutual | self.
    """
    if from_id == to_id:
        return "self"
    existing = get_friendship(session, from_id, to_id)
    if existing is None:
        session.add(
            Friendship(
                user_a_id=from_id,
                user_b_id=to_id,
                status="pending",
                created_at_utc=utcnow(),
            )
        )
        return "sent"
    if existing.status == "mutual":
        return "already_mutual"
    if existing.user_a_id == from_id:
        return "already_pending"
    # Встречная заявка = взаимное согласие (ADR-12).
    existing.status = "mutual"
    return "auto_mutual"


def accept_request(session: Session, user_id: int, from_id: int) -> bool:
    """user_id принимает заявку, отправленную from_id."""
    friendship = session.get(Friendship, (from_id, user_id))
    if friendship is None or friendship.status != "pending":
        return False
    friendship.status = "mutual"
    return True


def decline_request(session: Session, user_id: int, from_id: int) -> bool:
    """user_id отклоняет заявку от from_id: строка удаляется."""
    friendship = session.get(Friendship, (from_id, user_id))
    if friendship is None or friendship.status != "pending":
        return False
    session.delete(friendship)
    return True


def incoming_requests(session: Session, user_id: int) -> list[User]:
    """Кто прислал user_id заявки, ожидающие ответа."""
    return list(
        session.scalars(
            select(User)
            .join(Friendship, Friendship.user_a_id == User.telegram_id)
            .where(
                Friendship.user_b_id == user_id,
                Friendship.status == "pending",
                User.deleted_at_utc.is_(None),
            )
        )
    )


def list_friends(session: Session, user_id: int) -> list[User]:
    """Все взаимные друзья user_id."""
    sent = select(Friendship.user_b_id).where(
        Friendship.user_a_id == user_id, Friendship.status == "mutual"
    )
    received = select(Friendship.user_a_id).where(
        Friendship.user_b_id == user_id, Friendship.status == "mutual"
    )
    ids = [*session.scalars(sent), *session.scalars(received)]
    if not ids:
        return []
    return list(
        session.scalars(
            select(User).where(
                User.telegram_id.in_(ids),
                User.deleted_at_utc.is_(None),
            )
        )
    )
