"""FSM states for the bot."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ScanStates(StatesGroup):
    waiting_for_symbol = State()


class WatchlistStates(StatesGroup):
    waiting_for_symbol = State()
