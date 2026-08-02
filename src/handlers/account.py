from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from src.db.base import SessionLocal
from src.services.account import delete_account
from src.services.analytics import track

router = Router()


class DeleteMe(StatesGroup):
    waiting_for_confirmation = State()


@router.message(Command("deleteme"))
async def cmd_deleteme(message: Message, state: FSMContext) -> None:
    await state.set_state(DeleteMe.waiting_for_confirmation)
    await message.answer(
        "⚠️ Это полностью удалит твой аккаунт: город, всех друзей и настройки. "
        "Отменить будет нельзя; повторный /start начнёт всё с чистого листа.\n\n"
        "Чтобы подтвердить, напиши слово: УДАЛИТЬ\n"
        "Передумал(а) — отправь любое другое сообщение."
    )


@router.message(DeleteMe.waiting_for_confirmation, F.text)
async def confirm_typed(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await state.clear()
    if (message.text or "").strip().upper() != "УДАЛИТЬ":
        await message.answer("Удаление отменено. Ничего не тронуто — жми /start.")
        return
    with SessionLocal.begin() as session:
        ok = delete_account(session, message.from_user.id)
        if ok:
            track(session, "account_deleted", message.from_user.id)
    if not ok:
        await message.answer("Аккаунт уже удалён. Вернуться — /start.")
        return
    await message.answer(
        "Аккаунт удалён. Спасибо, что попробовал(а) Раскидало! "
        "Захочешь вернуться — просто напиши /start."
    )
