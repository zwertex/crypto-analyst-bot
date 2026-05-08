"""Tests for the in-memory watchlist."""
from __future__ import annotations

import pytest

from bot.storage import WatchlistStorage


def test_add_and_get() -> None:
    s = WatchlistStorage()
    assert s.add(1, "BTCUSDT") is True
    assert s.add(1, "ETHUSDT") is True
    assert s.get(1) == ["BTCUSDT", "ETHUSDT"]


def test_add_duplicate_is_noop() -> None:
    s = WatchlistStorage()
    s.add(1, "BTCUSDT")
    assert s.add(1, "BTCUSDT") is False


def test_remove() -> None:
    s = WatchlistStorage()
    s.add(1, "BTCUSDT")
    assert s.remove(1, "BTCUSDT") is True
    assert s.remove(1, "BTCUSDT") is False
    assert s.get(1) == []


def test_separation_per_user() -> None:
    s = WatchlistStorage()
    s.add(1, "BTCUSDT")
    s.add(2, "ETHUSDT")
    assert s.get(1) == ["BTCUSDT"]
    assert s.get(2) == ["ETHUSDT"]


def test_max_per_user() -> None:
    s = WatchlistStorage()
    for i in range(WatchlistStorage.MAX_PER_USER):
        s.add(1, f"COIN{i}USDT")
    with pytest.raises(ValueError):
        s.add(1, "ONEMOREUSDT")
