"""Technical analysis indicators implemented on top of numpy.

Implementation notes:
- All functions accept arrays and return arrays of the same length, with leading
  NaNs where the indicator is not yet defined. This makes them composable and
  matches the convention in TA-Lib / pandas-ta.
- Functions are pure and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def _to_array(values: list[float] | FloatArray) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("expected a 1-D array of values")
    return arr


def sma(values: list[float] | FloatArray, period: int) -> FloatArray:
    """Simple moving average."""
    if period < 1:
        raise ValueError("period must be >= 1")
    arr = _to_array(values)
    out = np.full(arr.shape, np.nan)
    if arr.size < period:
        return out
    csum = np.cumsum(arr)
    out[period - 1] = csum[period - 1] / period
    out[period:] = (csum[period:] - csum[:-period]) / period
    return out


def ema(values: list[float] | FloatArray, period: int) -> FloatArray:
    """Exponential moving average. Seeded with SMA of the first `period` values."""
    if period < 1:
        raise ValueError("period must be >= 1")
    arr = _to_array(values)
    out = np.full(arr.shape, np.nan)
    if arr.size < period:
        return out
    alpha = 2.0 / (period + 1.0)
    out[period - 1] = arr[:period].mean()
    for i in range(period, arr.size):
        out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]
    return out


def rsi(values: list[float] | FloatArray, period: int = 14) -> FloatArray:
    """Wilder's RSI."""
    if period < 1:
        raise ValueError("period must be >= 1")
    arr = _to_array(values)
    out = np.full(arr.shape, np.nan)
    if arr.size <= period:
        return out
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()
    if avg_loss == 0:
        out[period] = 100.0
    elif avg_gain == 0:
        out[period] = 0.0
    else:
        rs = avg_gain / avg_loss
        out[period] = 100.0 - (100.0 / (1.0 + rs))
    for i in range(period + 1, arr.size):
        gain = gains[i - 1]
        loss = losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            out[i] = 100.0
        elif avg_gain == 0:
            out[i] = 0.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


@dataclass(frozen=True)
class MacdResult:
    macd: FloatArray
    signal: FloatArray
    hist: FloatArray


def macd(
    values: list[float] | FloatArray,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> MacdResult:
    if fast >= slow:
        raise ValueError("fast must be < slow")
    arr = _to_array(values)
    ema_fast = ema(arr, fast)
    ema_slow = ema(arr, slow)
    macd_line = ema_fast - ema_slow
    macd_clean = np.where(np.isnan(macd_line), 0.0, macd_line)
    signal_full = ema(macd_clean, signal)
    not_ready = np.isnan(macd_line)
    signal_line = np.where(not_ready, np.nan, signal_full)
    first_valid = int(np.argmax(~not_ready)) if (~not_ready).any() else arr.size
    invalid_signal = np.arange(arr.size) < first_valid + signal - 1
    signal_line = np.where(invalid_signal, np.nan, signal_line)
    hist = macd_line - signal_line
    return MacdResult(macd=macd_line, signal=signal_line, hist=hist)


@dataclass(frozen=True)
class BollingerResult:
    middle: FloatArray
    upper: FloatArray
    lower: FloatArray


def bollinger_bands(
    values: list[float] | FloatArray,
    period: int = 20,
    num_std: float = 2.0,
) -> BollingerResult:
    arr = _to_array(values)
    middle = sma(arr, period)
    out_std = np.full(arr.shape, np.nan)
    if arr.size >= period:
        for i in range(period - 1, arr.size):
            window = arr[i - period + 1 : i + 1]
            out_std[i] = window.std(ddof=0)
    upper = middle + num_std * out_std
    lower = middle - num_std * out_std
    return BollingerResult(middle=middle, upper=upper, lower=lower)


def true_range(high: FloatArray, low: FloatArray, close: FloatArray) -> FloatArray:
    if not (high.size == low.size == close.size):
        raise ValueError("h/l/c arrays must have equal length")
    tr = np.full(high.shape, np.nan)
    tr[0] = high[0] - low[0]
    for i in range(1, high.size):
        a = high[i] - low[i]
        b = abs(high[i] - close[i - 1])
        c = abs(low[i] - close[i - 1])
        tr[i] = max(a, b, c)
    return tr


def atr(
    high: list[float] | FloatArray,
    low: list[float] | FloatArray,
    close: list[float] | FloatArray,
    period: int = 14,
) -> FloatArray:
    """Wilder's ATR."""
    h = _to_array(high)
    l_ = _to_array(low)
    c = _to_array(close)
    tr = true_range(h, l_, c)
    out = np.full(h.shape, np.nan)
    if h.size <= period:
        return out
    out[period] = tr[1 : period + 1].mean()
    for i in range(period + 1, h.size):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def support_resistance(
    high: FloatArray, low: FloatArray, lookback: int = 50
) -> tuple[float, float]:
    """Return (support, resistance) as the min low and max high over the lookback window."""
    if high.size == 0 or low.size == 0:
        raise ValueError("empty arrays")
    n = min(lookback, high.size)
    return float(low[-n:].min()), float(high[-n:].max())
