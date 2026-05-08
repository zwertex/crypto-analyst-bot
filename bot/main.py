"""Bot entry point."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import load_settings
from bot.handlers import scan as scan_handlers
from bot.handlers import start as start_handlers
from bot.handlers import watchlist as watchlist_handlers
from bot.services.binance import BinanceClient
from bot.storage import WatchlistStorage

logger = logging.getLogger(__name__)


async def _set_default_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            types.BotCommand(command="start", description="Запустить бота / меню"),
            types.BotCommand(command="scan", description="Сканировать монету"),
            types.BotCommand(command="menu", description="Главное меню"),
            types.BotCommand(command="help", description="Как читать сигналы"),
        ]
    )


def _allowed_only(allowed_ids: list[int]):
    """Build a middleware that drops updates from users not in the allow-list."""
    if not allowed_ids:
        return None
    allowed = set(allowed_ids)

    async def middleware(handler, event, data):  # type: ignore[no-untyped-def]
        user = data.get("event_from_user")
        if user is None or user.id in allowed:
            return await handler(event, data)
        logger.info("rejected update from user_id=%s (not in allowlist)", user.id)
        return None

    return middleware


async def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    binance = BinanceClient()
    watchlist = WatchlistStorage()

    dp["binance"] = binance
    dp["watchlist"] = watchlist

    if mw := _allowed_only(settings.allowed_user_ids):
        dp.message.middleware(mw)
        dp.callback_query.middleware(mw)

    dp.include_router(start_handlers.router)
    dp.include_router(scan_handlers.router)
    dp.include_router(watchlist_handlers.router)

    await _set_default_commands(bot)
    try:
        # warm up symbol cache so first /scan is fast
        try:
            await binance.get_exchange_symbols()
        except Exception as e:
            logger.warning("could not preload symbols: %s", e)
        logger.info("bot is starting polling")
        await dp.start_polling(bot)
    finally:
        await binance.aclose()
        await bot.session.close()


def cli() -> None:
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)


if __name__ == "__main__":
    cli()
