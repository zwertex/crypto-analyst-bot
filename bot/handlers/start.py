"""Start, help, and main-menu navigation handlers."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.menus import main_menu

router = Router(name="start")


WELCOME_TEXT = (
    "<b>👋 Привет!</b>\n\n"
    "Я анализирую крипто-активы по нескольким таймфреймам и подсказываю "
    "<b>LONG / SHORT / NEUTRAL</b> с конкретным планом сделки.\n\n"
    "Что умею:\n"
    "• Технический анализ: RSI, MACD, EMA(20/50/200), Bollinger Bands, ATR, "
    "объёмы, поддержки и сопротивления\n"
    "• Мульти-таймфрейм: 1h + 4h + 1d с весами\n"
    "• План: вход / стоп / TP1 / TP2 / risk-reward\n"
    "• Избранное и быстрый ре-скан\n\n"
    "Жми <b>🔍 Сканировать монету</b> и введи тикер (например, <code>BTC</code> или "
    "<code>SOLUSDT</code>)."
)


HELP_TEXT = (
    "<b>Как читать результат</b>\n\n"
    "🟢 <b>LONG</b> — сигнал на покупку, 🔴 <b>SHORT</b> — на продажу, "
    "⚪ <b>NEUTRAL</b> — рынок не определился, лучше подождать.\n\n"
    "<b>Уверенность</b> — насколько индикаторы согласованы между собой и "
    "между таймфреймами (1h × 1, 4h × 2, 1d × 3).\n\n"
    "<b>План сделки</b>:\n"
    "• <b>Вход</b> — текущая цена;\n"
    "• <b>Стоп-лосс</b> — на расстоянии 1.5 × ATR(14, 4h) — это волатильность, "
    "не \"красивый круглый уровень\";\n"
    "• <b>TP1 / TP2</b> — 1.5R и 3R от стопа;\n"
    "• <b>R/R</b> — отношение профита (TP2) к риску (стопу).\n\n"
    "<b>Индикаторы</b>:\n"
    "• <b>RSI</b> &lt;30 — перепродан, &gt;70 — перекуплен\n"
    "• <b>EMA50/200</b> — направление тренда\n"
    "• <b>MACD</b> — импульс\n"
    "• <b>Bollinger Bands</b> — экстремумы волатильности\n"
    "• <b>Объём</b> — подтверждение движения\n\n"
    "⚠️ Это <i>не</i> финансовая рекомендация. Бот не знает твой риск-профиль."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=main_menu())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню", reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.callback_query(F.data == "action:home")
async def go_home(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if call.message:
        await call.message.answer("Главное меню", reply_markup=main_menu())
    await call.answer()


@router.callback_query(F.data == "action:help")
async def show_help(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(HELP_TEXT, reply_markup=main_menu())
    await call.answer()


@router.callback_query(F.data == "action:settings")
async def show_settings(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "<b>⚙️ Настройки</b>\n\n"
            "Сейчас доступны базовые параметры — таймфреймы и веса захардкожены "
            "под классическую стратегию свинг/интрадей. Если нужны кастомные "
            "пресеты — напиши автору.",
            reply_markup=main_menu(),
        )
    await call.answer()


@router.callback_query(F.data == "action:top")
async def show_top(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "<b>🔥 Популярные тикеры</b>\n\nВыбери монету или введи свою через "
            "🔍 Сканировать.",
            reply_markup=main_menu(),
        )
    await call.answer()
