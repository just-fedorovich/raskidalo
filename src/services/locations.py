from sqlalchemy.orm import Session

from src.db.models import City, Location
from src.services.clock import utcnow


def set_location(session: Session, telegram_id: int, city: City) -> None:
    """Upsert текущей локации пользователя (флоу 0.5.2)."""
    location = session.get(Location, telegram_id)
    if location is None:
        location = Location(user_id=telegram_id)
        session.add(location)
    location.country_code = city.country_code
    location.city_id = city.id
    location.updated_at_utc = utcnow()
