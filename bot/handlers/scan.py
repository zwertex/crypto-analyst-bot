"""Scan flow: button → ask for coin → validate → analyze → render."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.menus import (
    analysis_actions,
    cancel_keyboard,
    main_menu,
    scan_prompt_keyboard,
)
from bot.services.binance import BinanceClient, BinanceError, SymbolNotFoundError
from bot.services.formatter import render_analysis
from bot.services.signals import analyze
from bot.states import ScanStates
from bot.storage import WatchlistStorage

logger = logging.getLogger(__name__)

router = Router(name="scan")


SCAN_PROMPT = (
    "<b>🔍 Сканер</b>\n\n"
    "Введи тикер монеты — например <code>BTC</code>, <code>ETH</code>, "
    "<code>solusdt</code>, <code>doge/usdt</code>.\n\n"
    "Или выбери из быстрых вариантов ниже:"
)

TIMEFRAMES = ("1h", "4h", "1d")


def _watchlist(data) -> WatchlistStorage:
    """Type-safe access to the shared watchlist from FSMContext.bot.workflow_data."""
    if not isinstance(data, WatchlistStorage):
        raise RuntimeError("watchlist storage not configured")
    return data


@router.message(Command("scan"))
async def cmd_scan(message: Message, state: FSMContext) -> None:
    await state.set_state(ScanStates.waiting_for_symbol)
    await message.answer(SCAN_PROMPT, reply_markup=scan_prompt_keyboard())


@router.callback_query(F.data == "action:scan")
async def cb_scan(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ScanStates.waiting_for_symbol)
    if call.message:
        await call.message.answer(SCAN_PROMPT, reply_markup=scan_prompt_keyboard())
    await call.answer()


@router.callback_query(F.data.startswith("quick:"))
async def cb_quick(
    call: CallbackQuery,
    state: FSMContext,
    binance: BinanceClient,
    watchlist: WatchlistStorage,
) -> None:
    if not call.data or not isinstance(call.message, Message) or not call.from_user:
        await call.answer()
        return
    raw = call.data.split(":", 1)[1]
    await state.clear()
    await call.answer(f"Сканирую {raw}…")
    await _run_analysis(call.message, raw, binance, watchlist, call.from_user.id)


@router.callback_query(F.data.startswith("refresh:"))
async def cb_refresh(
    call: CallbackQuery,
    binance: BinanceClient,
    watchlist: WatchlistStorage,
) -> None:
    if not call.data or not isinstance(call.message, Message) or not call.from_user:
        await call.answer()
        return
    sym = call.data.split(":", 1)[1]
    await call.answer("Обновляю…")
    await _run_analysis(call.message, sym, binance, watchlist, call.from_user.id)


@router.message(ScanStates.waiting_for_symbol)
async def msg_symbol_input(
    message: Message,
    state: FSMContext,
    binance: BinanceClient,
    watchlist: WatchlistStorage,
) -> None:
    if not message.text or not message.from_user:
        await message.answer(
            "Жду тикер текстом, например <code>BTC</code>.",
            reply_markup=cancel_keyboard(),
        )
        return
    raw = message.text.strip()
    if len(raw) > 30:
        await message.answer("Слишком длинный тикер. Попробуй короче (например, BTC).")
        return
    await state.clear()
    await _run_analysis(message, raw, binance, watchlist, message.from_user.id)


async def _run_analysis(
    target: Message,
    raw_symbol: str,
    binance: BinanceClient,
    watchlist: WatchlistStorage,
    user_id: int,
) -> None:
    """Resolve symbol, fetch data, build signal, render and reply."""
    progress = await target.answer(f"🔎 Ищу <b>{raw_symbol}</b> на Binance…")
    try:
        symbol = await binance.resolve_symbol(raw_symbol)
    except SymbolNotFoundError:
        await progress.edit_text(
            f"❌ Монета <b>{raw_symbol}</b> не найдена на Binance.\n\n"
            "Проверь тикер и попробуй ещё раз. Поддерживаются спот-пары "
            "(USDT/USDC/BUSD/BTC/ETH).",
            reply_markup=main_menu(),
        )
        return
    except BinanceError as e:
        logger.warning("binance error during resolve: %s", e)
        await progress.edit_text(
            "⚠️ Не удалось связаться с Binance. Попробуй ещё раз через минуту.",
            reply_markup=main_menu(),
        )
        return

    await progress.edit_text(f"📊 Считаю индикаторы для <b>{symbol}</b>…")

    try:
        ticker = await binance.get_ticker_24h(symbol)
        candles_by_tf = {}
        for tf in TIMEFRAMES:
            limit = 300 if tf != "1d" else 250
            candles_by_tf[tf] = await binance.get_klines(symbol, tf, limit=limit)
        funding = await binance.get_funding_rate(symbol)
    except BinanceError as e:
        logger.warning("binance error during data fetch: %s", e)
        await progress.edit_text(
            "⚠️ Не удалось получить данные свечей. Попробуй ещё раз.",
            reply_markup=main_menu(),
        )
        return

    try:
        result = analyze(
            symbol=symbol,
            candles_by_tf=candles_by_tf,
            last_price=ticker.last_price,
            price_change_pct_24h=ticker.price_change_pct,
            funding_rate=funding,
        )
    except ValueError as e:
        logger.warning("analyze error for %s: %s", symbol, e)
        await progress.edit_text(
            f"⚠️ Недостаточно данных по {symbol} для анализа ({e}).",
            reply_markup=main_menu(),
        )
        return

    text = render_analysis(result)
    in_wl = symbol in watchlist.get(user_id)
    await progress.edit_text(text, reply_markup=analysis_actions(symbol, in_wl))
