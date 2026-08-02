from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.db.base import SessionLocal
from src.db.models import City
from src.keyboards import MAIN_MENU_KB
from src.services.analytics import track
from src.services.cities import city_label, search_cities
from src.services.viewing import (
    FriendView,
    find_country,
    find_friends,
    friends_in_city,
    friends_in_country,
    my_city,
)

router = Router()


class FindFriend(StatesGroup):
    waiting_for_name = State()


class CityLookup(StatesGroup):
    waiting_for_city = State()


def _display(view: FriendView) -> str:
    name = view.user.first_name or "Без имени"
    if view.user.username:
        name = f"{name} (@{view.user.username})"
    return name


def _card(view: FriendView) -> str:
    lines = [f"👤 {_display(view)}"]
    if view.country_name is None:
        lines.append("📍 локация скрыта или не указана")
    else:
        if view.city_name is not None:
            lines.append(f"📍 {view.city_name}, {view.country_name}")
        else:
            lines.append(f"📍 {view.country_name}")
        lines.append(f"⏱ обновлено {view.updated_ago}")
    return "\n".join(lines)


def _city_report(session, me_telegram_id: int, city: City) -> str:
    views = friends_in_city(session, me_telegram_id, city)
    track(
        session,
        "city_lookup",
        me_telegram_id,
        {"scope": "city", "city_id": city.id, "found": len(views)},
    )
    label = city_label(session, city)
    if not views:
        return f"В городе {label} пока никого из твоих друзей."
    lines = [f"🏙 {label} — друзей: {len(views)}"]
    for v in views:
        lines.append(f"• {_display(v)} — ⏱ обновлено {v.updated_ago}")
    return "\n".join(lines)


def _country_report(session, me_telegram_id: int, country) -> str:
    views = friends_in_country(session, me_telegram_id, country.name_ru)
    track(
        session,
        "city_lookup",
        me_telegram_id,
        {"scope": "country", "found": len(views)},
    )
    if not views:
        return f"В стране {country.name_ru} пока никого из твоих друзей."
    lines = [f"🌍 {country.name_ru} — друзей: {len(views)}"]
    for v in views:
        place = f", {v.city_name}" if v.city_name else ""
        lines.append(f"• {_display(v)}{place} — ⏱ обновлено {v.updated_ago}")
    return "\n".join(lines)


# --- «Найти друга» (флоу 0.5.3) ---


@router.callback_query(F.data == "find_friend")
async def ask_name(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FindFriend.waiting_for_name)
    if callback.message is not None:
        await callback.message.answer("Кого ищем? Введи имя или @username друга.")
    await callback.answer()


@router.message(FindFriend.waiting_for_name, F.text)
async def name_typed(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await state.clear()
    with SessionLocal.begin() as session:
        views = find_friends(session, message.from_user.id, message.text or "")
        track(
            session,
            "friend_lookup",
            message.from_user.id,
            {"found": len(views)},
        )
        cards = [_card(v) for v in views]
    if not cards:
        await message.answer(
            "Не нашёл такого друга. Искать можно только среди взаимных "
            "друзей — по имени или @username.",
            reply_markup=MAIN_MENU_KB,
        )
        return
    await message.answer("\n\n".join(cards), reply_markup=MAIN_MENU_KB)


# --- «Друзья в городе» (флоу 0.5.4) ---


@router.callback_query(F.data == "friends_in_city")
async def ask_scope(callback: CallbackQuery) -> None:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📍 В моём городе", callback_data="fic_mine")],
            [InlineKeyboardButton(text="🌍 Указать другой", callback_data="fic_other")],
        ]
    )
    if callback.message is not None:
        await callback.message.answer("Где смотрим?", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "fic_mine")
async def in_my_city(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    with SessionLocal.begin() as session:
        city = my_city(session, callback.from_user.id)
        if city is None:
            text = "Сначала укажи свой город: кнопка «📍 Обновить город» в меню."
        else:
            text = _city_report(session, callback.from_user.id, city)
    await callback.message.answer(text, reply_markup=MAIN_MENU_KB)
    await callback.answer()


@router.callback_query(F.data == "fic_other")
async def ask_city_name(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CityLookup.waiting_for_city)
    if callback.message is not None:
        await callback.message.answer("Какой город или страна? Введи название.")
    await callback.answer()


@router.message(CityLookup.waiting_for_city, F.text)
async def lookup_typed(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    query = message.text or ""
    with SessionLocal.begin() as session:
        # Фикс UX-1: сначала точное совпадение со страной, потом города —
        # иначе нечёткий поиск городов перехватывает запрос
        # («Израиль» -> город Измаил).
        country = find_country(session, query)
        if country is not None:
            await state.clear()
            text = _country_report(session, message.from_user.id, country)
            await message.answer(text, reply_markup=MAIN_MENU_KB)
            return
        cities = search_cities(session, query)
        if len(cities) == 1:
            await state.clear()
            text = _city_report(session, message.from_user.id, cities[0])
            await message.answer(text, reply_markup=MAIN_MENU_KB)
            return
        if cities:
            buttons = [
                [
                    InlineKeyboardButton(
                        text=city_label(session, city),
                        callback_data=f"fic_city:{city.id}",
                    )
                ]
                for city in cities
            ]
            await message.answer(
                "Уточни, какой именно город:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            )
            return
    await message.answer(
        "Не нашёл ни города, ни страны с таким названием. Попробуй иначе."
    )


@router.callback_query(F.data.startswith("fic_city:"))
async def city_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    city_id = int((callback.data or "fic_city:0").split(":", 1)[1])
    await state.clear()
    with SessionLocal.begin() as session:
        city = session.get(City, city_id)
        text = (
            "Этого города больше нет в списке."
            if city is None
            else _city_report(session, callback.from_user.id, city)
        )
    if callback.message is not None:
        await callback.message.answer(text, reply_markup=MAIN_MENU_KB)
    await callback.answer()
