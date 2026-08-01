"""Просмотр друзей (Этап 5, флоу 0.5.3 и 0.5.4).

Показываются только mutual-друзья. Приватность (VisibilitySettings):
- invisible_mode или level='none' -> локация скрыта полностью;
- granularity='country_only' -> видна только страна;
- granularity='nothing' -> локация скрыта, но сам друг в поиске виден.
"""

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.db.models import (
    City,
    Country,
    Friendship,
    Location,
    User,
    VisibilitySettings,
)
from src.services.cities import normalize
from src.services.clock import time_ago

MAX_CARDS = 10  # лимит карточек «Где X?»; пагинация отложена до реальных жалоб


@dataclass
class FriendView:
    user: User
    country_name: str | None  # None -> локация скрыта или не указана
    city_name: str | None     # None -> скрыт город или вся локация
    city_id: int | None
    updated_ago: str | None


def _me(session: Session, telegram_id: int) -> User | None:
    return session.execute(
        select(User).where(User.telegram_id == telegram_id)
    ).scalar_one_or_none()


def _friend_ids(session: Session, me_id: int) -> list[int]:
    rows = session.execute(
        select(Friendship).where(
            Friendship.status == "mutual",
            or_(Friendship.user_a_id == me_id, Friendship.user_b_id == me_id),
        )
    ).scalars()
    return [f.user_b_id if f.user_a_id == me_id else f.user_a_id for f in rows]


def _view(session: Session, user: User) -> FriendView:
    vis = session.get(VisibilitySettings, user.telegram_id)
    if vis is not None and (vis.invisible_mode or vis.level == "none"):
        return FriendView(user, None, None, None, None)
    location = session.get(Location, user.telegram_id)
    if location is None or (vis is not None and vis.granularity == "nothing"):
        return FriendView(user, None, None, None, None)
    country = session.get(Country, location.country_code)
    country_name = country.name_ru if country else location.country_code
    city_name = None
    city_id = None
    if location.city_id and (vis is None or vis.granularity == "country_city"):
        city = session.get(City, location.city_id)
        if city is not None:
            city_name = city.name_ru
            city_id = city.id
    return FriendView(
        user, country_name, city_name, city_id, time_ago(location.updated_at_utc)
    )


def _friend_views(session: Session, me_telegram_id: int) -> list[FriendView]:
    me = _me(session, me_telegram_id)
    if me is None:
        return []
    ids = _friend_ids(session, me.telegram_id)
    if not ids:
        return []
    users = session.execute(select(User).where(User.telegram_id.in_(ids))).scalars()
    return [_view(session, u) for u in users]


def my_city(session: Session, telegram_id: int) -> City | None:
    """Город самого пользователя — для кнопки «В моём городе»."""
    me = _me(session, telegram_id)
    if me is None:
        return None
    location = session.get(Location, me.telegram_id)
    if location is None or location.city_id is None:
        return None
    return session.get(City, location.city_id)


def find_friends(session: Session, me_telegram_id: int, query: str) -> list[FriendView]:
    """«Где X?» — поиск по имени или @username среди mutual-друзей."""
    q = normalize(query).lstrip("@")
    if not q:
        return []
    views = [
        v
        for v in _friend_views(session, me_telegram_id)
        if q in normalize(v.user.first_name or "")
        or q in normalize(v.user.username or "")
    ]
    return views[:MAX_CARDS]


def friends_in_city(session: Session, me_telegram_id: int, city: City) -> list[FriendView]:
    """«Кто в городе Y?» — друг виден, только если его город не скрыт."""
    return [
        v
        for v in _friend_views(session, me_telegram_id)
        if v.city_id == city.id
    ]


def friends_in_country(
    session: Session, me_telegram_id: int, country_name: str
) -> list[FriendView]:
    """Список друзей в стране — включая тех, у кого видна только страна."""
    return [
        v
        for v in _friend_views(session, me_telegram_id)
        if v.country_name == country_name
    ]


def find_country(session: Session, query: str) -> Country | None:
    """Страна по точному названию по-русски или по-английски."""
    q = normalize(query)
    if len(q) < 2:
        return None
    for country in session.execute(select(Country)).scalars():
        if q in (normalize(country.name_ru or ""), normalize(country.name_en or "")):
            return country
    return None

