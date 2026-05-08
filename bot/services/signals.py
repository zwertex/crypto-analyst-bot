"""Signal engine.

Combines multiple indicators across multiple timeframes into a single
LONG / SHORT / NEUTRAL recommendation with entry, stop-loss, take-profit
and a confidence score.

Design:
- Each indicator on each timeframe contributes a small bounded vote in [-1, 1].
- Timeframes are weighted (1h=1, 4h=2, 1d=3) to favor higher-timeframe trends.
- The aggregate score is normalised to [-1, 1] and turned into a signal.
- Risk parameters (SL/TP) are computed from ATR on the 4h timeframe.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from bot.services.binance import Candle
from bot.services.indicators import (
    atr,
    bollinger_bands,
    ema,
    macd,
    rsi,
    support_resistance,
)


class Signal(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


@dataclass
class TimeframeSnapshot:
    """Indicator values at the latest candle of a single timeframe."""

    timeframe: str
    last_close: float
    rsi: float
    ema20: float
    ema50: float
    ema200: float
    macd: float
    macd_signal: float
    macd_hist: float
    bb_upper: float
    bb_lower: float
    bb_middle: float
    atr: float
    support: float
    resistance: float
    volume: float
    avg_volume: float
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass
class TradePlan:
    signal: Signal
    confidence: float
    entry: float
    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None
    risk_reward: float | None


@dataclass
class AnalysisResult:
    symbol: str
    last_price: float
    price_change_pct_24h: float | None
    funding_rate: float | None
    snapshots: dict[str, TimeframeSnapshot]
    plan: TradePlan
    summary_reasons: list[str]


def _last(values: np.ndarray) -> float:
    """Return the last non-NaN value, or NaN if there is none."""
    if values.size == 0:
        return float("nan")
    arr = values[~np.isnan(values)]
    if arr.size == 0:
        return float("nan")
    return float(arr[-1])


def build_snapshot(timeframe: str, candles: list[Candle]) -> TimeframeSnapshot:
    """Compute all indicators for one timeframe."""
    if len(candles) < 50:
        raise ValueError(f"need at least 50 candles for {timeframe}, got {len(candles)}")
    closes = np.array([c.close for c in candles], dtype=np.float64)
    highs = np.array([c.high for c in candles], dtype=np.float64)
    lows = np.array([c.low for c in candles], dtype=np.float64)
    volumes = np.array([c.volume for c in candles], dtype=np.float64)

    rsi_arr = rsi(closes, 14)
    ema20_arr = ema(closes, 20)
    ema50_arr = ema(closes, 50)
    ema200_arr = ema(closes, 200) if len(closes) >= 200 else np.full(closes.shape, np.nan)
    macd_res = macd(closes)
    bb_res = bollinger_bands(closes, 20, 2.0)
    atr_arr = atr(highs, lows, closes, 14)
    support, resistance = support_resistance(highs, lows, lookback=50)
    avg_vol = float(volumes[-20:].mean())

    return TimeframeSnapshot(
        timeframe=timeframe,
        last_close=float(closes[-1]),
        rsi=_last(rsi_arr),
        ema20=_last(ema20_arr),
        ema50=_last(ema50_arr),
        ema200=_last(ema200_arr),
        macd=_last(macd_res.macd),
        macd_signal=_last(macd_res.signal),
        macd_hist=_last(macd_res.hist),
        bb_upper=_last(bb_res.upper),
        bb_lower=_last(bb_res.lower),
        bb_middle=_last(bb_res.middle),
        atr=_last(atr_arr),
        support=support,
        resistance=resistance,
        volume=float(volumes[-1]),
        avg_volume=avg_vol,
    )


# Per-snapshot scoring weights. Sum of absolute max ~ 2.0, but realistic
# "all-aligned" cases hit ~1.6, which we treat as the effective max in the
# normalisation step below.
SNAPSHOT_MAX_SCORE = 1.6
SIGNAL_THRESHOLD = 0.20


def _score_snapshot(s: TimeframeSnapshot) -> TimeframeSnapshot:
    """Populate `score` and `reasons` for a snapshot. Returns the same object."""
    score = 0.0
    reasons: list[str] = []

    # EMA trend stack — the dominant signal in trending markets.
    if not np.isnan(s.ema50):
        if not np.isnan(s.ema200):
            if s.ema50 > s.ema200 and s.last_close > s.ema50:
                score += 0.8
                reasons.append("Тренд бычий: цена > EMA50 > EMA200")
            elif s.ema50 < s.ema200 and s.last_close < s.ema50:
                score -= 0.8
                reasons.append("Тренд медвежий: цена < EMA50 < EMA200")
            elif s.ema50 > s.ema200:
                score += 0.3
                reasons.append("EMA50 > EMA200 (бычий long-term)")
            else:
                score -= 0.3
                reasons.append("EMA50 < EMA200 (медвежий long-term)")
        else:
            if s.last_close > s.ema50:
                score += 0.2
                reasons.append("Цена выше EMA50")
            else:
                score -= 0.2
                reasons.append("Цена ниже EMA50")

    # RSI: weighted very light so it cannot flip a confirmed trend on its own.
    # In strong trends RSI extremes are common and not reliable reversal signals.
    if not np.isnan(s.rsi):
        if s.rsi < 25:
            score += 0.2
            reasons.append(f"RSI {s.rsi:.1f} <25 (сильно перепродан)")
        elif s.rsi < 35:
            score += 0.1
            reasons.append(f"RSI {s.rsi:.1f} перепродан")
        elif s.rsi > 75:
            score -= 0.2
            reasons.append(f"RSI {s.rsi:.1f} >75 (сильно перекуплен)")
        elif s.rsi > 65:
            score -= 0.1
            reasons.append(f"RSI {s.rsi:.1f} перекуплен")

    # MACD
    if not np.isnan(s.macd) and not np.isnan(s.macd_signal):
        if s.macd > s.macd_signal and s.macd_hist > 0:
            score += 0.3
            reasons.append("MACD выше сигнальной (бычий)")
        elif s.macd < s.macd_signal and s.macd_hist < 0:
            score -= 0.3
            reasons.append("MACD ниже сигнальной (медвежий)")

    # Bollinger Bands extremes
    if not np.isnan(s.bb_lower) and not np.isnan(s.bb_upper):
        if s.last_close <= s.bb_lower:
            score += 0.2
            reasons.append("Цена у нижней BB (потенц. отскок)")
        elif s.last_close >= s.bb_upper:
            score -= 0.2
            reasons.append("Цена у верхней BB (потенц. откат)")

    # Volume confirmation: amplify the leaning side
    if s.avg_volume > 0:
        ratio = s.volume / s.avg_volume
        if ratio > 1.5:
            if score > 0:
                score += 0.2
                reasons.append(f"Объём x{ratio:.1f} подтверждает рост")
            elif score < 0:
                score -= 0.2
                reasons.append(f"Объём x{ratio:.1f} подтверждает падение")

    s.score = max(-SNAPSHOT_MAX_SCORE, min(SNAPSHOT_MAX_SCORE, score))
    s.reasons = reasons
    return s


TIMEFRAME_WEIGHTS: dict[str, float] = {
    "1h": 1.0,
    "4h": 2.0,
    "1d": 3.0,
}


def aggregate(snapshots: dict[str, TimeframeSnapshot]) -> tuple[float, list[str]]:
    """Return (normalised_score in [-1, 1], aggregated_reasons)."""
    weighted_sum = 0.0
    weight_total = 0.0
    reasons: list[str] = []
    for tf, snap in snapshots.items():
        _score_snapshot(snap)
        w = TIMEFRAME_WEIGHTS.get(tf, 1.0)
        weighted_sum += snap.score * w
        weight_total += w * SNAPSHOT_MAX_SCORE
        for r in snap.reasons:
            reasons.append(f"[{tf}] {r}")
    if weight_total == 0:
        return 0.0, reasons
    norm = weighted_sum / weight_total
    return max(-1.0, min(1.0, norm)), reasons


def build_trade_plan(
    norm_score: float,
    snapshots: dict[str, TimeframeSnapshot],
) -> TradePlan:
    """Convert a normalised score to a concrete trade plan.

    Uses the 4h snapshot for entry/SL/TP if available, falling back to whatever
    timeframe is provided. SL is placed 1.5 * ATR away; TP1 = 1.5R, TP2 = 3R.
    """
    ref = snapshots.get("4h") or next(iter(snapshots.values()))
    entry = ref.last_close

    if norm_score >= SIGNAL_THRESHOLD:
        signal = Signal.LONG
    elif norm_score <= -SIGNAL_THRESHOLD:
        signal = Signal.SHORT
    else:
        signal = Signal.NEUTRAL

    confidence = min(1.0, abs(norm_score) / 0.6)

    if signal == Signal.NEUTRAL or np.isnan(ref.atr) or ref.atr <= 0:
        return TradePlan(
            signal=signal,
            confidence=confidence,
            entry=entry,
            stop_loss=None,
            take_profit_1=None,
            take_profit_2=None,
            risk_reward=None,
        )

    risk = 1.5 * ref.atr
    if signal == Signal.LONG:
        sl = entry - risk
        tp1 = entry + 1.5 * risk
        tp2 = entry + 3.0 * risk
    else:
        sl = entry + risk
        tp1 = entry - 1.5 * risk
        tp2 = entry - 3.0 * risk

    rr = abs(tp2 - entry) / abs(entry - sl) if entry != sl else None

    return TradePlan(
        signal=signal,
        confidence=confidence,
        entry=entry,
        stop_loss=sl,
        take_profit_1=tp1,
        take_profit_2=tp2,
        risk_reward=rr,
    )


def analyze(
    symbol: str,
    candles_by_tf: dict[str, list[Candle]],
    last_price: float,
    price_change_pct_24h: float | None,
    funding_rate: float | None,
) -> AnalysisResult:
    """High-level: build snapshots, aggregate, build plan."""
    snapshots: dict[str, TimeframeSnapshot] = {}
    for tf, candles in candles_by_tf.items():
        snapshots[tf] = build_snapshot(tf, candles)
    norm_score, reasons = aggregate(snapshots)
    plan = build_trade_plan(norm_score, snapshots)
    return AnalysisResult(
        symbol=symbol,
        last_price=last_price,
        price_change_pct_24h=price_change_pct_24h,
        funding_rate=funding_rate,
        snapshots=snapshots,
        plan=plan,
        summary_reasons=reasons,
    )
