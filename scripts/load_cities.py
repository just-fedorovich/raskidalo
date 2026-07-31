"""Разовая загрузка справочника стран и городов из GeoNames (ADR-10, ADR-11).

Запуск из корня репозитория: python -m scripts.load_cities
Повторный запуск безопасен: уже загруженные записи пропускаются.
Русские названия городов берутся из словаря alternateNamesV2 по метке
языка "ru": «первое кириллическое из alternatenames» давало белорусские
и чувашские варианты («Арэнбург», «Маскав») — см. ADR-11.
"""

import csv
import io
import sys
import urllib.request
import zipfile

from sqlalchemy import func, select

from src.db.base import SessionLocal
from src.db.models import City, Country

CITIES_URL = "https://download.geonames.org/export/dump/cities15000.zip"
COUNTRIES_URL = "https://download.geonames.org/export/dump/countryInfo.txt"
ALT_NAMES_URL = "https://download.geonames.org/export/dump/alternateNamesV2.zip"

RU_COUNTRY_NAMES = {
    "AE": "ОАЭ", "AM": "Армения", "AR": "Аргентина", "AT": "Австрия",
    "AU": "Австралия", "AZ": "Азербайджан", "BE": "Бельгия", "BG": "Болгария",
    "BR": "Бразилия", "BY": "Беларусь", "CA": "Канада", "CH": "Швейцария",
    "CN": "Китай", "CY": "Кипр", "CZ": "Чехия", "DE": "Германия",
    "DK": "Дания", "EE": "Эстония", "EG": "Египет", "ES": "Испания",
    "FI": "Финляндия", "FR": "Франция", "GB": "Великобритания", "GE": "Грузия",
    "GR": "Греция", "HR": "Хорватия", "HU": "Венгрия", "ID": "Индонезия",
    "IE": "Ирландия", "IL": "Израиль", "IN": "Индия", "IT": "Италия",
    "JP": "Япония", "KG": "Киргизия", "KR": "Южная Корея", "KZ": "Казахстан",
    "LT": "Литва", "LV": "Латвия", "MD": "Молдова", "ME": "Черногория",
    "MX": "Мексика", "MY": "Малайзия", "NL": "Нидерланды", "NO": "Норвегия",
    "NZ": "Новая Зеландия", "PL": "Польша", "PT": "Португалия", "RO": "Румыния",
    "RS": "Сербия", "RU": "Россия", "SE": "Швеция", "SG": "Сингапур",
    "SI": "Словения", "SK": "Словакия", "TH": "Таиланд", "TJ": "Таджикистан",
    "TR": "Турция", "UA": "Украина", "US": "США", "UZ": "Узбекистан",
    "VN": "Вьетнам",
}


def _download_to_temp(url: str) -> str:
    """Скачивает файл во временную папку, печатая прогресс каждые ~20 МБ."""
    print(f"Скачиваю {url} ...")

    def _progress(blocks: int, block_size: int, total: int) -> None:
        done = blocks * block_size
        if total > 0 and done % (20 * 1024 * 1024) < block_size:
            print(f"  ... {done // (1024 * 1024)} МБ из {total // (1024 * 1024)} МБ")

    path, _ = urllib.request.urlretrieve(url, reporthook=_progress)
    return path


def load_countries(session) -> set[str]:
    existing = set(session.scalars(select(Country.code)))
    with urllib.request.urlopen(COUNTRIES_URL, timeout=120) as response:
        raw = response.read().decode("utf-8-sig")
    codes: set[str] = set()
    for line in raw.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        code = parts[0].strip().upper()
        name_en = parts[4].strip()
        if len(code) != 2 or not code.isalpha():
            continue
        codes.add(code)
        if code in existing:
            continue
        session.add(
            Country(
                code=code,
                name_en=name_en[:64],
                name_ru=(RU_COUNTRY_NAMES.get(code, name_en))[:64],
            )
        )
    return codes


def read_cities(country_codes: set[str], existing: set[int]) -> dict[int, tuple]:
    """cities15000: id -> (страна, name_en, name_local, широта, долгота, таймзона)."""
    path = _download_to_temp(CITIES_URL)
    csv.field_size_limit(min(sys.maxsize, 10_000_000))
    cities: dict[int, tuple] = {}
    with zipfile.ZipFile(path) as z, z.open("cities15000.txt") as f:
        reader = csv.reader(
            io.TextIOWrapper(f, encoding="utf-8"),
            delimiter="\t",
            quoting=csv.QUOTE_NONE,
        )
        for row in reader:
            if len(row) < 18:
                continue
            try:
                city_id = int(row[0])
            except ValueError:
                continue
            if city_id in existing:
                continue
            code = row[8].strip().upper()
            if code not in country_codes:
                continue
            name_local = (row[1] or "").strip() or None
            name_en = (row[2] or row[1] or "").strip() or f"city-{city_id}"
            cities[city_id] = (
                code,
                name_en,
                name_local,
                float(row[4]),
                float(row[5]),
                (row[17] or "UTC").strip() or "UTC",
            )
    return cities


def read_russian_names(city_ids: set[int]) -> dict[int, str]:
    """Русские названия из alternateNamesV2 по метке языка "ru".

    Архив ~200 МБ, поэтому файл читается потоково — в память попадают
    только названия наших городов. Приоритет: официальное название
    (isPreferredName) -> не сокращённое -> самое короткое. Исторические
    и разговорные варианты пропускаются.
    """
    path = _download_to_temp(ALT_NAMES_URL)
    best: dict[int, tuple] = {}
    with zipfile.ZipFile(path) as z, z.open("alternateNamesV2.txt") as f:
        for line in io.TextIOWrapper(f, encoding="utf-8"):
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4 or parts[2] != "ru":
                continue
            try:
                geoname_id = int(parts[1])
            except ValueError:
                continue
            if geoname_id not in city_ids:
                continue
            name = parts[3].strip()
            if not name or len(name) > 128:
                continue
            if (len(parts) > 6 and parts[6] == "1") or (
                len(parts) > 7 and parts[7] == "1"
            ):
                continue  # разговорное или историческое название
            is_preferred = len(parts) > 4 and parts[4] == "1"
            is_short = len(parts) > 5 and parts[5] == "1"
            rank = (0 if is_preferred else 1, 1 if is_short else 0, len(name), name)
            if geoname_id not in best or rank < best[geoname_id]:
                best[geoname_id] = rank
    return {gid: rank[3] for gid, rank in best.items()}


def main() -> None:
    with SessionLocal.begin() as session:
        codes = load_countries(session)
        existing = set(session.scalars(select(City.id)))
        cities = read_cities(codes, existing)
        print(f"Стран: {len(codes)}; новых городов к загрузке: {len(cities)}")
        ru_names = read_russian_names(set(cities))
        print(f"Русских названий найдено: {len(ru_names)}")
        for city_id, (code, name_en, name_local, lat, lon, tz) in cities.items():
            session.add(
                City(
                    id=city_id,
                    country_code=code,
                    name_ru=ru_names.get(city_id, name_en)[:128],
                    name_en=name_en[:128],
                    name_local=(name_local[:128] if name_local else None),
                    latitude=lat,
                    longitude=lon,
                    timezone_iana=tz,
                )
            )
        ru_count = session.scalar(
            select(func.count()).select_from(City).where(City.country_code == "RU")
        )
    urllib.request.urlcleanup()
    print(f"Готово. Городов RU в базе: {ru_count}")
    with SessionLocal() as session:
        for name_en in ("Moscow", "Orenburg", "Haifa"):
            for c in session.query(City).filter(City.name_en == name_en):
                print(f"самопроверка: {c.name_en} ({c.country_code}) -> {c.name_ru}")
    if not ru_count:
        raise SystemExit("ОШИБКА: в базе 0 городов RU. Пришли весь вывод в чат.")


if __name__ == "__main__":
    main()
