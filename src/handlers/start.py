from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.db.base import SessionLocal
from src.services.analytics import track
from src.services.users import register_user

router = Router()

NEW_USER_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📍 Указать город", callback_data="set_city")],
    ]
)

MAIN_MENU_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📍 Обновить город", callback_data="set_city")],
        [InlineKeyboardButton(text="🔍 Найти друга", callback_data="find_friend")],
        [InlineKeyboardButton(text="👥 Друзья в городе", callback_data="friends_in_city")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
    ]
)

STUB_CALLBACKS = {"set_city", "find_friend", "friends_in_city", "settings"}


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

    if is_new:
        name = tg_user.first_name or "друг"
        await message.answer(
            f"Привет, {name}! Это Раскидало — я показываю, в каких городах "
            "сейчас твои друзья. Чтобы начать, укажи свой текущий город.",
            reply_markup=NEW_USER_KB,
        )
    else:
        await message.answer(
            "С возвращением! Город пока не указан.",
            reply_markup=MAIN_MENU_KB,
        )


@router.callback_query(F.data.in_(STUB_CALLBACKS))
async def stub_buttons(callback: CallbackQuery) -> None:
    await callback.answer(
        "Эта кнопка заработает на следующих этапах 🛠", show_alert=True
    )
