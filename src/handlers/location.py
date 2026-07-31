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
from src.services.analytics import track
from src.services.cities import city_label, search_cities
from src.services.locations import set_location

router = Router()

AFTER_SAVE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти друга", callback_data="find_friend")],
        [InlineKeyboardButton(text="👥 Друзья в городе", callback_data="friends_in_city")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
    ]
)


class SetCity(StatesGroup):
    waiting_for_city = State()


@router.callback_query(F.data == "set_city")
async def ask_city(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetCity.waiting_for_city)
    if callback.message is not None:
        await callback.message.answer(
            "Где ты сейчас? Введи название города на любом языке — "
            "например, «Хайфа» или «Haifa»."
        )
    await callback.answer()


@router.message(SetCity.waiting_for_city, F.text)
async def city_typed(message: Message) -> None:
    with SessionLocal() as session:
        cities = search_cities(session, message.text or "")
        buttons = [
            [
                InlineKeyboardButton(
                    text=city_label(session, city),
                    callback_data=f"pick_city:{city.id}",
                )
            ]
            for city in cities
        ]
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
        await callback.message.answer(
            f"Сохранил! Твой город: {label}. Обновлено только что.",
            reply_markup=AFTER_SAVE_KB,
        )
    await callback.answer()
