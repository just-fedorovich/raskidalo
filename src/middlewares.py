"""Минимальный антиспам (Этап 7): не чаще одного апдейта в секунду.

Слишком частые сообщения и нажатия тихо игнорируются.
Счётчики живут в памяти процесса, БД не трогается.
"""

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

WINDOW_SECONDS = 1.0


class ThrottleMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._last: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None:
            now = time.monotonic()
            if now - self._last.get(user.id, 0.0) < WINDOW_SECONDS:
                return None
            self._last[user.id] = now
        return await handler(event, data)
