from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.db.base import SessionLocal
from src.keyboards import MAIN_MENU_KB
from src.services.analytics import track
from src.services.settings import get_settings

router = Router()

LEVEL_LABELS = {"friends": "только друзья", "none": "никто"}
GRAN_LABELS = {
    "country_city": "страна и город",
    "country_only": "только страна",
    "nothing": "ничего",
}
NEXT_LEVEL = {"friends": "none", "none": "friends"}
NEXT_GRAN = {
    "country_city": "country_only",
    "country_only": "nothing",
    "nothing": "country_city",
}


def _menu(settings) -> tuple[str, InlineKeyboardMarkup]:
    level = LEVEL_LABELS.get(settings.level, settings.level)
    gran = GRAN_LABELS.get(settings.granularity, settings.granularity)
    invisible = "включён" if settings.invisible_mode else "выключен"
    text = (
        "⚙️ Настройки приватности\n\n"
        f"👀 Кто видит мою локацию: {level}\n"
        f"🗺 Что именно видно: {gran}\n"
        f"🕶 Режим невидимки: {invisible}\n\n"
        "Нажми на пункт, чтобы переключить."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"👀 Кто видит: {level}", callback_data="st_level"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🗺 Что видно: {gran}", callback_data="st_gran"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🕶 Невидимка: {invisible}", callback_data="st_invis"
                )
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="st_back")],
        ]
    )
    return text, kb


@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery) -> None:
    with SessionLocal.begin() as session:
        text, kb = _menu(get_settings(session, callback.from_user.id))
    if callback.message is not None:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


async def _switch(callback: CallbackQuery, field: str) -> None:
    with SessionLocal.begin() as session:
        settings = get_settings(session, callback.from_user.id)
        if field == "level":
            settings.level = NEXT_LEVEL.get(settings.level, "friends")
        elif field == "granularity":
            settings.granularity = NEXT_GRAN.get(settings.granularity, "country_city")
        else:
            settings.invisible_mode = not settings.invisible_mode
        track(session, "settings_changed", callback.from_user.id, {"field": field})
        text, kb = _menu(settings)
    if callback.message is not None:
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception:
            # Сообщение слишком старое для редактирования — шлём новое.
            await callback.message.answer(text, reply_markup=kb)
    await callback.answer("Сохранено ✅")


@router.callback_query(F.data == "st_level")
async def switch_level(callback: CallbackQuery) -> None:
    await _switch(callback, "level")


@router.callback_query(F.data == "st_gran")
async def switch_granularity(callback: CallbackQuery) -> None:
    await _switch(callback, "granularity")


@router.callback_query(F.data == "st_invis")
async def switch_invisible(callback: CallbackQuery) -> None:
    await _switch(callback, "invisible_mode")


@router.callback_query(F.data == "st_back")
async def back_to_menu(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await callback.message.answer("Что дальше?", reply_markup=MAIN_MENU_KB)
    await callback.answer()
