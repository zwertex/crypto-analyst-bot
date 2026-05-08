"""Tests for technical indicators."""
from __future__ import annotations

import math

import numpy as np
import pytest

from bot.services.indicators import (
    atr,
    bollinger_bands,
    ema,
    macd,
    rsi,
    sma,
    support_resistance,
)


def test_sma_basic() -> None:
    out = sma([1, 2, 3, 4, 5], 3)
    assert math.isnan(out[0]) and math.isnan(out[1])
    assert out[2] == pytest.approx(2.0)
    assert out[3] == pytest.approx(3.0)
    assert out[4] == pytest.approx(4.0)


def test_sma_period_validation() -> None:
    with pytest.raises(ValueError):
        sma([1, 2, 3], 0)


def test_ema_seeded_with_sma() -> None:
    values = [1.0] * 30
    out = ema(values, 10)
    # EMA of constant series equals that constant after seeding
    for v in out[10:]:
        assert v == pytest.approx(1.0)


def test_ema_changes_with_new_value() -> None:
    values = [1.0] * 9 + [2.0] * 11
    out = ema(values, 5)
    assert out[-1] > 1.0
    assert out[-1] < 2.0


def test_rsi_range() -> None:
    rng = np.random.default_rng(42)
    closes = np.cumsum(rng.standard_normal(200)) + 100
    out = rsi(closes, 14)
    valid = out[~np.isnan(out)]
    assert valid.size > 100
    assert valid.min() >= 0
    assert valid.max() <= 100


def test_rsi_strong_uptrend_high() -> None:
    closes = np.linspace(100, 200, 50)
    out = rsi(closes, 14)
    assert out[-1] > 90


def test_rsi_strong_downtrend_low() -> None:
    closes = np.linspace(200, 100, 50)
    out = rsi(closes, 14)
    assert out[-1] < 10


def test_macd_crossover() -> None:
    closes = np.concatenate([np.linspace(100, 80, 30), np.linspace(80, 130, 30)])
    res = macd(closes)
    # at the end of a strong uptrend, macd should be > signal
    assert res.macd[-1] > res.signal[-1]


def test_bollinger_centred() -> None:
    closes = np.linspace(100, 110, 40)
    bb = bollinger_bands(closes, 20, 2.0)
    assert bb.upper[-1] > bb.middle[-1] > bb.lower[-1]


def test_atr_positive() -> None:
    rng = np.random.default_rng(0)
    closes = np.cumsum(rng.standard_normal(100)) + 100
    highs = closes + rng.uniform(0.1, 1.0, size=closes.shape)
    lows = closes - rng.uniform(0.1, 1.0, size=closes.shape)
    out = atr(highs, lows, closes, 14)
    valid = out[~np.isnan(out)]
    assert valid.size > 50
    assert (valid > 0).all()


def test_support_resistance() -> None:
    highs = np.array([1.0, 2.0, 3.0, 5.0, 4.0])
    lows = np.array([0.5, 1.0, 2.0, 4.0, 3.0])
    s, r = support_resistance(highs, lows, lookback=5)
    assert s == 0.5
    assert r == 5.0
