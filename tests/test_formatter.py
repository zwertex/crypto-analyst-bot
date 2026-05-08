"""Tests for the message formatter."""
from __future__ import annotations

import numpy as np

from bot.services.binance import Candle
from bot.services.formatter import render_analysis
from bot.services.signals import Signal, analyze


def _make_candles(closes: list[float]) -> list[Candle]:
    out: list[Candle] = []
    for i, c in enumerate(closes):
        out.append(
            Candle(
                open_time=i * 1000,
                open=c,
                high=c * 1.01,
                low=c * 0.99,
                close=c,
                volume=1000.0,
                close_time=i * 1000 + 999,
                quote_volume=c * 1000,
                trades=10,
            )
        )
    return out


def test_render_long_includes_plan_lines() -> None:
    closes = list(np.linspace(100, 200, 250))
    candles_by_tf = {tf: _make_candles(closes) for tf in ("1h", "4h", "1d")}
    res = analyze(
        symbol="BTCUSDT",
        candles_by_tf=candles_by_tf,
        last_price=closes[-1],
        price_change_pct_24h=5.0,
        funding_rate=None,
    )
    assert res.plan.signal == Signal.LONG
    text = render_analysis(res)
    assert "BTCUSDT" in text
    assert "LONG" in text
    assert "Стоп-лосс" in text
    assert "TP1" in text
    assert "Risk/Reward" in text


def test_render_neutral_skips_plan() -> None:
    closes = [100.0 + (i % 3 - 1) * 0.5 for i in range(250)]
    candles_by_tf = {tf: _make_candles(closes) for tf in ("1h", "4h", "1d")}
    res = analyze(
        symbol="STABLE",
        candles_by_tf=candles_by_tf,
        last_price=100.0,
        price_change_pct_24h=0.1,
        funding_rate=None,
    )
    text = render_analysis(res)
    assert "Сигнал" in text
    if res.plan.signal == Signal.NEUTRAL:
        assert "Стоп-лосс" not in text
