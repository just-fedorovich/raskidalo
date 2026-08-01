from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from src.db.base import SessionLocal
from src.db.models import City, Location
from src.keyboards import MAIN_MENU_KB, NEW_USER_KB
from src.services.analytics import track
from src.services.cities import city_label
from src.services.clock import time_ago
from src.services.users import register_user

router = Router()

# Заглушки до Этапов 5–6: set_city живёт в location.py,
# add_friend / my_friends — в friends.py.
STUB_CALLBACKS = {"settings"}


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    with SessionLocal.begin() as session:
        is_new = register_user(
            session, tg_user.id, tg_user.first_name, tg_user.username
        )
        if is_new:
            track(session, "user_registered", tg_user.id)
        city_line = "Город пока не указан."
        location = session.get(Location, tg_user.id)
        if location is not None:
            city = session.get(City, location.city_id)
            if city is not None:
                city_line = (
                    f"Твой город: {city_label(session, city)}, "
                    f"обновлено {time_ago(location.updated_at_utc)}."
                )

    if is_new:
        name = tg_user.first_name or "друг"
        await message.answer(
            f"Привет, {name}! Это Раскидало — я показываю, в каких городах "
            "сейчас твои друзья. Чтобы начать, укажи свой текущий город.",
            reply_markup=NEW_USER_KB,
        )
    else:
        await message.answer(
            f"С возвращением! {city_line}",
            reply_markup=MAIN_MENU_KB,
        )


@router.callback_query(F.data.in_(STUB_CALLBACKS))
async def stub_buttons(callback: CallbackQuery) -> None:
    await callback.answer(
        "Эта кнопка заработает на следующих этапах 🛠", show_alert=True
    )

