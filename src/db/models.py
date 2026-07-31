from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class User(Base):
    __tablename__ = "users"
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str | None] = mapped_column(String(64))
    username: Mapped[str | None] = mapped_column(String(32))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime)
    deleted_at_utc: Mapped[datetime | None] = mapped_column(DateTime)


class Country(Base):
    __tablename__ = "countries"
    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name_ru: Mapped[str] = mapped_column(String(64))
    name_en: Mapped[str] = mapped_column(String(64))


class City(Base):
    __tablename__ = "cities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"))
    name_ru: Mapped[str] = mapped_column(String(128))
    name_en: Mapped[str] = mapped_column(String(128))
    name_local: Mapped[str | None] = mapped_column(String(128))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    timezone_iana: Mapped[str] = mapped_column(String(64))


class Location(Base):
    __tablename__ = "locations"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.telegram_id"), primary_key=True
    )
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime)


class Friendship(Base):
    __tablename__ = "friendships"
    user_a_id: Mapped[int] = mapped_column(
        ForeignKey("users.telegram_id"), primary_key=True
    )
    user_b_id: Mapped[int] = mapped_column(
        ForeignKey("users.telegram_id"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at_utc: Mapped[datetime] = mapped_column(DateTime)


class VisibilitySettings(Base):
    __tablename__ = "visibility_settings"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.telegram_id"), primary_key=True
    )
    level: Mapped[str] = mapped_column(String(16), default="friends")
    granularity: Mapped[str] = mapped_column(String(16), default="country_city")
    invisible_mode: Mapped[bool] = mapped_column(Boolean, default=False)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(32))
    user_id_anon: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime)