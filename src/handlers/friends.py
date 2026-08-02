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
from src.db.models import User
from src.keyboards import MAIN_MENU_KB
from src.services.analytics import track
from src.services.friends import (
    accept_request,
    decline_request,
    find_user_by_username,
    incoming_requests,
    list_friends,
    remove_friend,
    send_request,
)

router = Router()


class AddFriend(StatesGroup):
    waiting_for_username = State()


def _display(first_name, username) -> str:
    name = first_name or "Без имени"
    return f"{name} (@{username})" if username else name


def _request_kb(from_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять", callback_data=f"fr_accept:{from_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить", callback_data=f"fr_decline:{from_id}"
                ),
            ]
        ]
    )


@router.callback_query(F.data == "add_friend")
async def ask_username(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddFriend.waiting_for_username)
    if callback.message is not None:
        await callback.message.answer(
            "Кого добавить? Пришли @username друга — как в его профиле Telegram."
        )
    await callback.answer()


@router.message(AddFriend.waiting_for_username, F.text)
async def username_typed(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    my_id = message.from_user.id
    target_id = None
    target_label = None
    with SessionLocal.begin() as session:
        target = find_user_by_username(session, message.text or "")
        if target is None:
            result = "not_found"
        else:
            target_id = target.telegram_id
            target_label = _display(target.first_name, target.username)
            result = send_request(session, my_id, target_id)
            if result == "sent":
                track(session, "friend_request_sent", my_id)
            elif result == "auto_mutual":
                track(session, "friend_request_accepted", my_id)

    if result == "not_found":
        await message.answer(
            "Такого пользователя в Раскидало пока нет — для бота этот контакт "
            "офлайн. Пришли другу ссылку на бота, а мне — другой @username. "
            "Выйти из режима добавления: /start."
        )
        return

    await state.clear()
    me_label = _display(message.from_user.first_name, message.from_user.username)
    if result == "self":
        await message.answer(
            "Себя добавить в друзья нельзя 🙂", reply_markup=MAIN_MENU_KB
        )
    elif result == "already_mutual":
        await message.answer(
            f"Вы с {target_label} уже друзья ✅", reply_markup=MAIN_MENU_KB
        )
    elif result == "already_pending":
        await message.answer(
            f"Заявка для {target_label} уже отправлена — ждём ответа.",
            reply_markup=MAIN_MENU_KB,
        )
    elif result == "auto_mutual":
        await message.answer(
            f"Встречная заявка! Вы с {target_label} теперь друзья ✅",
            reply_markup=MAIN_MENU_KB,
        )
        try:
            await message.bot.send_message(
                target_id, f"🤝 Вы с {me_label} теперь друзья!"
            )
        except Exception:
            pass
    else:  # sent
        try:
            await message.bot.send_message(
                target_id,
                f"👋 {me_label} хочет добавить тебя в друзья в Раскидало.",
                reply_markup=_request_kb(my_id),
            )
            note = f"Заявка отправлена — {target_label} получит уведомление."
        except Exception:
            note = (
                f"Заявка сохранена, но уведомление до {target_label} не дошло — "
                "заявка видна в «🤝 Мои друзья»."
            )
        await message.answer(note, reply_markup=MAIN_MENU_KB)


@router.callback_query(F.data == "my_friends")
async def my_friends(callback: CallbackQuery) -> None:
    buttons: list[list[InlineKeyboardButton]] = []
    with SessionLocal() as session:
        friends = list_friends(session, callback.from_user.id)
        incoming = incoming_requests(session, callback.from_user.id)
        lines = ["🤝 Твои друзья:"]
        if friends:
            lines += [f"• {_display(u.first_name, u.username)}" for u in friends]
            lines.append("")
            lines.append("Убрать кого-то из друзей — кнопкой ниже:"
            )
            for u in friends:
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"🗑 {_display(u.first_name, u.username)}",
                            callback_data=f"fr_remove:{u.telegram_id}",
                        )
                    ]
                )
        else:
            lines.append("пока никого — жми «➕ Добавить друга».")
        if incoming:
            lines.append("")
            lines.append("📨 Заявки тебе — прими или отклони кнопками:")
            for u in incoming:
                lines.append(f"• {_display(u.first_name, u.username)}")
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"✅ {u.first_name or 'Принять'}",
                            callback_data=f"fr_accept:{u.telegram_id}",
                        ),
                        InlineKeyboardButton(
                            text="❌", callback_data=f"fr_decline:{u.telegram_id}"
                        ),
                    ]
                )
    if callback.message is not None:
        kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else MAIN_MENU_KB
        await callback.message.answer("\n".join(lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("fr_accept:"))
async def cb_accept(callback: CallbackQuery) -> None:
    from_id = int((callback.data or "fr_accept:0").split(":", 1)[1])
    with SessionLocal.begin() as session:
        ok = accept_request(session, callback.from_user.id, from_id)
        if ok:
            track(session, "friend_request_accepted", callback.from_user.id)
    if not ok:
        await callback.answer("Заявка уже неактуальна.", show_alert=True)
        return
    await callback.answer("Готово!")
    if callback.message is not None:
        await callback.message.answer("Вы теперь друзья 🤝", reply_markup=MAIN_MENU_KB)
    try:
        await callback.bot.send_message(from_id, "🤝 Твоя заявка в друзья принята!")
    except Exception:
        pass


@router.callback_query(F.data.startswith("fr_decline:"))
async def cb_decline(callback: CallbackQuery) -> None:
    from_id = int((callback.data or "fr_decline:0").split(":", 1)[1])
    with SessionLocal.begin() as session:
        ok = decline_request(session, callback.from_user.id, from_id)
        if ok:
            track(session, "friend_request_declined", callback.from_user.id)
    await callback.answer("Заявка отклонена." if ok else "Заявка уже неактуальна.")


# --- Удаление из друзей (Этап 6, флоу 0.5.7) ---
# Важно: "fr_remove_yes:" не начинается с "fr_remove:" (дальше идёт "_",
# а не ":"), поэтому обработчики не конфликтуют.


@router.callback_query(F.data.startswith("fr_remove_yes:"))
async def cb_remove_yes(callback: CallbackQuery) -> None:
    other_id = int((callback.data or "fr_remove_yes:0").split(":", 1)[1])
    with SessionLocal.begin() as session:
        ok = remove_friend(session, callback.from_user.id, other_id)
        if ok:
            track(session, "friend_removed", callback.from_user.id)
    await callback.answer("Удалено." if ok else "Вы уже не друзья.")
    if ok and callback.message is not None:
        await callback.message.answer(
            "Готово: вы больше не друзья. Второй стороне уведомление "
            "не отправляется.",
            reply_markup=MAIN_MENU_KB,
        )


@router.callback_query(F.data.startswith("fr_remove:"))
async def cb_remove_confirm(callback: CallbackQuery) -> None:
    other_id = int((callback.data or "fr_remove:0").split(":", 1)[1])
    with SessionLocal() as session:
        other = session.get(User, other_id)
        label = (
            _display(other.first_name, other.username)
            if other is not None
            else "этого пользователя"
        )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=f"fr_remove_yes:{other_id}",
                ),
                InlineKeyboardButton(text="❌ Отмена", callback_data="my_friends"),
            ]
        ]
    )
    if callback.message is not None:
        await callback.message.answer(
            f"Удалить {label} из друзей? Дружба разорвётся у обоих; "
            "уведомление не придёт. Повторную заявку можно отправить позже.",
            reply_markup=kb,
        )
    await callback.answer()
