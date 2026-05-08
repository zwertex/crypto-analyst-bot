"""Lightweight in-memory user storage (watchlists). Per-process only."""
from __future__ import annotations

from collections import defaultdict


class WatchlistStorage:
    """Per-user set of symbols. Bounded to keep memory predictable."""

    MAX_PER_USER = 25

    def __init__(self) -> None:
        self._data: dict[int, list[str]] = defaultdict(list)

    def get(self, user_id: int) -> list[str]:
        return list(self._data[user_id])

    def add(self, user_id: int, symbol: str) -> bool:
        items = self._data[user_id]
        if symbol in items:
            return False
        if len(items) >= self.MAX_PER_USER:
            raise ValueError(f"watchlist limit ({self.MAX_PER_USER}) reached")
        items.append(symbol)
        return True

    def remove(self, user_id: int, symbol: str) -> bool:
        items = self._data[user_id]
        if symbol not in items:
            return False
        items.remove(symbol)
        return True

    def clear(self, user_id: int) -> None:
        self._data[user_id].clear()
