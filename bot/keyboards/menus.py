"""Inline keyboards used by the bot."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Сканировать монету", callback_data="action:scan")],
            [
                InlineKeyboardButton(text="⭐ Избранное", callback_data="action:watchlist"),
                InlineKeyboardButton(text="🔥 Топ монет", callback_data="action:top"),
            ],
            [
                InlineKeyboardButton(text="ℹ️ Как читать", callback_data="action:help"),
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="action:settings"),
            ],
        ]
    )


def scan_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="BTC", callback_data="quick:BTC"),
                InlineKeyboardButton(text="ETH", callback_data="quick:ETH"),
                InlineKeyboardButton(text="SOL", callback_data="quick:SOL"),
                InlineKeyboardButton(text="BNB", callback_data="quick:BNB"),
            ],
            [
                InlineKeyboardButton(text="XRP", callback_data="quick:XRP"),
                InlineKeyboardButton(text="DOGE", callback_data="quick:DOGE"),
                InlineKeyboardButton(text="TON", callback_data="quick:TON"),
                InlineKeyboardButton(text="ADA", callback_data="quick:ADA"),
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="action:home")],
        ]
    )


def analysis_actions(symbol: str, in_watchlist: bool) -> InlineKeyboardMarkup:
    star_text = "★ В избранном" if in_watchlist else "☆ В избранное"
    star_action = "wl_remove" if in_watchlist else "wl_add"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh:{symbol}"),
                InlineKeyboardButton(text=star_text, callback_data=f"{star_action}:{symbol}"),
            ],
            [
                InlineKeyboardButton(text="🔍 Другая монета", callback_data="action:scan"),
                InlineKeyboardButton(text="🏠 В меню", callback_data="action:home"),
            ],
        ]
    )


def watchlist_keyboard(symbols: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for sym in symbols:
        rows.append(
            [
                InlineKeyboardButton(text=f"📈 {sym}", callback_data=f"refresh:{sym}"),
                InlineKeyboardButton(text="❌", callback_data=f"wl_remove:{sym}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ Добавить", callback_data="action:wl_add")])
    rows.append([InlineKeyboardButton(text="🏠 В меню", callback_data="action:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✖️ Отмена", callback_data="action:home")],
        ]
    )
