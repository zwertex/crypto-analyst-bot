"""Tests for the signal engine."""
from __future__ import annotations

import numpy as np

from bot.services.binance import Candle
from bot.services.signals import (
    Signal,
    aggregate,
    analyze,
    build_snapshot,
    build_trade_plan,
)


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


def _trending_closes(seed: int, n: int, drift: float, vol: float = 0.01, start: float = 100.0) -> list[float]:
    """Generate realistic price series: random walk with drift.

    `drift` is the per-step expected return, `vol` the per-step std.
    Positive drift -> uptrend; negative -> downtrend.
    """
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    prices = start * np.cumprod(1.0 + rets)
    return prices.tolist()


def test_build_snapshot_uptrend() -> None:
    closes = _trending_closes(seed=7, n=250, drift=0.004)
    snap = build_snapshot("4h", _make_candles(closes))
    assert snap.last_close == closes[-1]
    assert snap.ema50 < snap.last_close  # price above EMA50 in uptrend
    assert snap.ema200 < snap.ema50  # 50 above 200 in uptrend


def test_build_snapshot_too_few_candles_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        build_snapshot("1h", _make_candles([1.0, 2.0, 3.0]))


def test_aggregate_long_in_uptrend() -> None:
    closes = _trending_closes(seed=7, n=250, drift=0.004)
    snaps = {tf: build_snapshot(tf, _make_candles(closes)) for tf in ("1h", "4h", "1d")}
    score, reasons = aggregate(snaps)
    assert score > 0.2
    assert reasons


def test_aggregate_short_in_downtrend() -> None:
    closes = _trending_closes(seed=11, n=250, drift=-0.004)
    snaps = {tf: build_snapshot(tf, _make_candles(closes)) for tf in ("1h", "4h", "1d")}
    score, _ = aggregate(snaps)
    assert score < -0.2


def test_build_trade_plan_long_has_sl_below_entry() -> None:
    closes = _trending_closes(seed=7, n=250, drift=0.004)
    snaps = {tf: build_snapshot(tf, _make_candles(closes)) for tf in ("1h", "4h", "1d")}
    score, _ = aggregate(snaps)
    plan = build_trade_plan(score, snaps)
    assert plan.signal == Signal.LONG
    assert plan.stop_loss is not None
    assert plan.take_profit_1 is not None
    assert plan.take_profit_2 is not None
    assert plan.stop_loss < plan.entry < plan.take_profit_1 < plan.take_profit_2
    assert plan.risk_reward is not None
    assert plan.risk_reward > 1.5


def test_build_trade_plan_short_has_sl_above_entry() -> None:
    closes = _trending_closes(seed=11, n=250, drift=-0.004)
    snaps = {tf: build_snapshot(tf, _make_candles(closes)) for tf in ("1h", "4h", "1d")}
    score, _ = aggregate(snaps)
    plan = build_trade_plan(score, snaps)
    assert plan.signal == Signal.SHORT
    assert plan.stop_loss is not None
    assert plan.take_profit_1 is not None
    assert plan.take_profit_2 is not None
    assert plan.take_profit_2 < plan.take_profit_1 < plan.entry < plan.stop_loss


def test_build_trade_plan_neutral_no_levels() -> None:
    closes = [100.0 + (i % 3 - 1) * 0.5 for i in range(250)]
    snaps = {tf: build_snapshot(tf, _make_candles(closes)) for tf in ("1h", "4h", "1d")}
    score, _ = aggregate(snaps)
    plan = build_trade_plan(score, snaps)
    if plan.signal == Signal.NEUTRAL:
        assert plan.stop_loss is None
        assert plan.take_profit_1 is None


def test_analyze_end_to_end_uptrend_returns_long() -> None:
    closes = _trending_closes(seed=7, n=250, drift=0.004)
    candles_by_tf = {tf: _make_candles(closes) for tf in ("1h", "4h", "1d")}
    res = analyze(
        symbol="TESTUSDT",
        candles_by_tf=candles_by_tf,
        last_price=closes[-1],
        price_change_pct_24h=5.0,
        funding_rate=0.0001,
    )
    assert res.symbol == "TESTUSDT"
    assert res.plan.signal == Signal.LONG
    assert res.summary_reasons
