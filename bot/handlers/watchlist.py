"""Watchlist management handlers."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.menus import cancel_keyboard, main_menu, watchlist_keyboard
from bot.services.binance import BinanceClient, BinanceError, SymbolNotFoundError
from bot.states import WatchlistStates
from bot.storage import WatchlistStorage

router = Router(name="watchlist")


@router.callback_query(F.data == "action:watchlist")
async def show_watchlist(call: CallbackQuery, watchlist: WatchlistStorage) -> None:
    if not call.message or not call.from_user:
        await call.answer()
        return
    items = watchlist.get(call.from_user.id)
    if not items:
        await call.message.answer(
            "<b>⭐ Избранное пусто</b>\n\n"
            "Добавь монеты из карточки анализа кнопкой ☆ или нажми ниже.",
            reply_markup=watchlist_keyboard([]),
        )
    else:
        await call.message.answer(
            f"<b>⭐ Избранное ({len(items)}/{watchlist.MAX_PER_USER})</b>\n\n"
            "Жми на тикер, чтобы пересканировать, или ❌ чтобы удалить.",
            reply_markup=watchlist_keyboard(items),
        )
    await call.answer()


@router.callback_query(F.data == "action:wl_add")
async def wl_add_prompt(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WatchlistStates.waiting_for_symbol)
    if call.message:
        await call.message.answer(
            "Введи тикер для добавления в избранное (например, <code>BTC</code>).",
            reply_markup=cancel_keyboard(),
        )
    await call.answer()


@router.message(WatchlistStates.waiting_for_symbol)
async def wl_add_input(
    message: Message,
    state: FSMContext,
    binance: BinanceClient,
    watchlist: WatchlistStorage,
) -> None:
    if not message.text or not message.from_user:
        await message.answer("Жду тикер текстом.", reply_markup=cancel_keyboard())
        return
    raw = message.text.strip()
    await state.clear()
    try:
        symbol = await binance.resolve_symbol(raw)
    except SymbolNotFoundError:
        await message.answer(
            f"❌ Монета <b>{raw}</b> не найдена.", reply_markup=main_menu()
        )
        return
    except BinanceError:
        await message.answer(
            "⚠️ Сеть недоступна, попробуй позже.", reply_markup=main_menu()
        )
        return
    try:
        added = watchlist.add(message.from_user.id, symbol)
    except ValueError as e:
        await message.answer(f"⚠️ {e}", reply_markup=main_menu())
        return
    items = watchlist.get(message.from_user.id)
    if added:
        text = f"✅ <b>{symbol}</b> добавлен в избранное."
    else:
        text = f"<b>{symbol}</b> уже в избранном."
    await message.answer(text, reply_markup=watchlist_keyboard(items))


@router.callback_query(F.data.startswith("wl_add:"))
async def wl_add_from_card(
    call: CallbackQuery, watchlist: WatchlistStorage
) -> None:
    if not call.data or not call.from_user or not call.message:
        await call.answer()
        return
    symbol = call.data.split(":", 1)[1]
    try:
        added = watchlist.add(call.from_user.id, symbol)
    except ValueError as e:
        await call.answer(f"⚠️ {e}", show_alert=True)
        return
    if added:
        await call.answer(f"⭐ {symbol} добавлен")
    else:
        await call.answer(f"{symbol} уже в избранном")


@router.callback_query(F.data.startswith("wl_remove:"))
async def wl_remove(
    call: CallbackQuery, watchlist: WatchlistStorage
) -> None:
    if not call.data or not call.from_user or not call.message:
        await call.answer()
        return
    symbol = call.data.split(":", 1)[1]
    removed = watchlist.remove(call.from_user.id, symbol)
    items = watchlist.get(call.from_user.id)
    if removed:
        await call.answer(f"❌ {symbol} удалён")
        await call.message.answer(
            f"<b>⭐ Избранное ({len(items)}/{watchlist.MAX_PER_USER})</b>",
            reply_markup=watchlist_keyboard(items),
        )
    else:
        await call.answer(f"{symbol} не было в избранном")
