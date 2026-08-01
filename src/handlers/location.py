from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from src.db.base import SessionLocal
from src.db.models import City
from src.keyboards import MAIN_MENU_KB
from src.services.analytics import track
from src.services.cities import city_label, nearest_cities, search_cities
from src.services.locations import set_location

router = Router()

# Telegram отдаёт координаты только через reply-кнопку с request_location
# (inline-кнопки так не умеют), и только с телефона.
SHARE_LOCATION_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Отправить геопозицию", request_location=True)]
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


class SetCity(StatesGroup):
    waiting_for_city = State()


def _city_buttons(session, cities) -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(
                text=city_label(session, city),
                callback_data=f"pick_city:{city.id}",
            )
        ]
        for city in cities
    ]


@router.callback_query(F.data == "set_city")
async def ask_city(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetCity.waiting_for_city)
    if callback.message is not None:
        await callback.message.answer(
            "Где ты сейчас? Введи название города на любом языке — "
            "например, «Хайфа» или «Haifa» — или нажми кнопку внизу, "
            "чтобы отправить геопозицию (работает с телефона).",
            reply_markup=SHARE_LOCATION_KB,
        )
    await callback.answer()


@router.message(SetCity.waiting_for_city, F.location)
async def location_shared(message: Message) -> None:
    if message.location is None:
        return
    with SessionLocal() as session:
        cities = nearest_cities(
            session, message.location.latitude, message.location.longitude
        )
        buttons = _city_buttons(session, cities)
    if not buttons:
        await message.answer(
            "Не нашёл город в 50 км от этой точки. Введи название текстом."
        )
        return
    await message.answer(
        "Вот ближайшие города — выбери свой:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.message(SetCity.waiting_for_city, F.text)
async def city_typed(message: Message) -> None:
    with SessionLocal() as session:
        cities = search_cities(session, message.text or "")
        buttons = _city_buttons(session, cities)
    if not buttons:
        await message.answer(
            "Не нашёл такого города. Попробуй написать иначе — "
            "по-русски или по-английски."
        )
        return
    buttons.append(
        [InlineKeyboardButton(text="🔁 Поискать ещё", callback_data="set_city")]
    )
    await message.answer(
        "Вот что я нашёл — выбери свой город:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("pick_city:"))
async def city_picked(callback: CallbackQuery, state: FSMContext) -> None:
    city_id = int((callback.data or "pick_city:0").split(":", 1)[1])
    with SessionLocal.begin() as session:
        city = session.get(City, city_id)
        if city is None:
            label = None
        else:
            set_location(session, callback.from_user.id, city)
            track(
                session, "location_updated", callback.from_user.id, {"city_id": city_id}
            )
            label = city_label(session, city)
    if label is None:
        await callback.answer("Этого города больше нет в списке.", show_alert=True)
        return
    await state.clear()
    if callback.message is not None:
        # Убрать нижнюю reply-клавиатуру и показать inline-меню одним
        # сообщением Telegram не позволяет — поэтому два.
        await callback.message.answer(
            f"Сохранил! Твой город: {label}. Обновлено только что.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await callback.message.answer("Что дальше?", reply_markup=MAIN_MENU_KB)
    await callback.answer()
