import difflib
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import City, Country

MAX_RESULTS = 5
GEO_RADIUS_KM = 50  # радиус поиска города по геопозиции (флоу 0.5.2)
GEO_MAX_CANDIDATES = 3

# Кэши в памяти. Строятся один раз при первом обращении: SQLite не
# сравнивает кириллицу без учёта регистра, а расстояния быстрее считать
# по готовому списку координат (~30 тыс. городов). После перезаливки
# справочника бота нужно перезапустить (правило Ш.8 Этапа 3).
_index: dict[str, list[int]] | None = None
_coords: list[tuple[int, float, float]] | None = None


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


def _get_coords(session: Session) -> list[tuple[int, float, float]]:
    global _coords
    if _coords is None:
        rows = session.execute(select(City.id, City.latitude, City.longitude))
        _coords = [
            (city_id, latitude, longitude)
            for city_id, latitude, longitude in rows
            if latitude is not None and longitude is not None
        ]
    return _coords


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между точками на сфере (формула гаверсинусов), км."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def city_label(session: Session, city: City) -> str:
    """«Хайфа, Израиль» — название города и страны по-русски."""
    country = session.get(Country, city.country_code)
    country_name = country.name_ru if country else city.country_code
    return f"{city.name_ru}, {country_name}"


def search_cities(session: Session, query: str) -> list[City]:
    """Поиск по любому написанию: точное -> префикс -> подстрока -> похожие."""
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


def nearest_cities(session: Session, latitude: float, longitude: float) -> list[City]:
    """До 3 ближайших городов в радиусе 50 км от точки (опция A флоу 0.5.2)."""
    scored: list[tuple[float, int]] = []
    for city_id, city_lat, city_lon in _get_coords(session):
        distance = _distance_km(latitude, longitude, city_lat, city_lon)
        if distance <= GEO_RADIUS_KM:
            scored.append((distance, city_id))
    scored.sort()
    cities = [session.get(City, city_id) for _, city_id in scored[:GEO_MAX_CANDIDATES]]
    return [city for city in cities if city is not None]
