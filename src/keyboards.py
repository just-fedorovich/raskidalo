from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Единое главное меню бота. Кнопки-заглушки оживают по этапам:
# set_city — Этап 3, add_friend/my_friends — Этап 4,
# find_friend/friends_in_city — Этап 5, settings — Этап 6.

NEW_USER_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📍 Указать город", callback_data="set_city")],
    ]
)

MAIN_MENU_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📍 Обновить город", callback_data="set_city")],
        [
            InlineKeyboardButton(text="➕ Добавить друга", callback_data="add_friend"),
            InlineKeyboardButton(text="🤝 Мои друзья", callback_data="my_friends"),
        ],
        [
            InlineKeyboardButton(text="🔍 Найти друга", callback_data="find_friend"),
            InlineKeyboardButton(text="👥 Друзья в городе", callback_data="friends_in_city"),
        ],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
    ]
)
