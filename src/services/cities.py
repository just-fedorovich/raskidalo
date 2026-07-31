import difflib

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import City, Country

MAX_RESULTS = 5

_index: dict[str, list[int]] | None = None


def normalize(text: str) -> str:
    return text.strip().lower().replace("ё", "е")


def _get_index(session: Session) -> dict[str, list[int]]:
    global _index
    if _index is None:
        index: dict[str, list[int]] = {}
        rows = session.execute(
            select(City.id, City.name_ru, City.name_en)
        )
        for city_id, name_ru, name_en in rows:
            for name in (name_ru, name_en):
                if name:
                    index.setdefault(normalize(name), []).append(city_id)
        _index = index
    return _index


def city_label(session: Session, city: City) -> str:
    country = session.get(Country, city.country_code)
    country_name = country.name_ru if country else city.country_code
    return f"{city.name_ru}, {country_name}"


def search_cities(session: Session, query: str) -> list[City]:
    q = normalize(query)
    if len(q) < 2:
        return []
    index = _get_index(session)

    matched: list[str] = []
    if q in index:
        matched = [q]
    if not matched:
        matched = [name for name in index if name.startswith(q)]
    if not matched:
        matched = [name for name in index if q in name]
    if not matched:
        matched = difflib.get_close_matches(q, index, n=MAX_RESULTS, cutoff=0.75)

    city_ids: list[int] = []
    for name in sorted(matched, key=len):
        for city_id in index[name]:
            if city_id not in city_ids:
                city_ids.append(city_id)
    cities = [session.get(City, city_id) for city_id in city_ids[:MAX_RESULTS]]
    return [city for city in cities if city is not None]
