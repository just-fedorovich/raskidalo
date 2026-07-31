import asyncio

import sentry_sdk
from aiogram import Bot, Dispatcher

from src.config.settings import BOT_TOKEN, ENV, SENTRY_DSN
from src.handlers.start import router

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=ENV,
        # Ctrl+C — штатная остановка, не ошибка: в Sentry не репортим.
        ignore_errors=[KeyboardInterrupt],
    )


async def main() -> None:
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
