"""Render an AnalysisResult into a Telegram-friendly HTML message."""
from __future__ import annotations

import html
import math

from bot.services.signals import AnalysisResult, Signal, TimeframeSnapshot


def _esc(s: str) -> str:
    """HTML-escape dynamic text so '<', '>', '&' do not break Telegram parser."""
    return html.escape(s, quote=False)


def _fmt_price(value: float | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if value == 0:
        return "0"
    abs_v = abs(value)
    if abs_v >= 1000:
        return f"{value:,.2f}".replace(",", " ")
    if abs_v >= 1:
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _fmt_pct(value: float | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value:+.2f}%"


def _signal_emoji(s: Signal) -> str:
    return {Signal.LONG: "🟢", Signal.SHORT: "🔴", Signal.NEUTRAL: "⚪"}[s]


def _confidence_bar(c: float) -> str:
    filled = max(0, min(10, round(c * 10)))
    return "▓" * filled + "░" * (10 - filled)


def _snapshot_block(snap: TimeframeSnapshot) -> str:
    return (
        f"<b>{_esc(snap.timeframe.upper())}</b>  RSI {snap.rsi:.1f}  "
        f"MACD {snap.macd:.4f}/{snap.macd_signal:.4f}\n"
        f"  EMA20 {_fmt_price(snap.ema20)}  EMA50 {_fmt_price(snap.ema50)}  "
        f"EMA200 {_fmt_price(snap.ema200)}\n"
        f"  BB: [{_fmt_price(snap.bb_lower)} … {_fmt_price(snap.bb_upper)}]  "
        f"ATR {_fmt_price(snap.atr)}\n"
        f"  S/R: {_fmt_price(snap.support)} / {_fmt_price(snap.resistance)}  "
        f"Vol x{(snap.volume / snap.avg_volume if snap.avg_volume else 0):.2f}"
    )


def render_analysis(result: AnalysisResult) -> str:
    plan = result.plan
    lines: list[str] = []
    lines.append(
        f"<b>{_esc(result.symbol)}</b>  {_fmt_price(result.last_price)}  "
        f"({_fmt_pct(result.price_change_pct_24h)} 24ч)"
    )
    if result.funding_rate is not None:
        lines.append(f"<i>Funding: {result.funding_rate * 100:+.4f}%</i>")
    lines.append("")
    lines.append(
        f"{_signal_emoji(plan.signal)} <b>Сигнал: {_esc(plan.signal.value)}</b>  "
        f"уверенность {plan.confidence * 100:.0f}%  {_confidence_bar(plan.confidence)}"
    )

    if plan.signal != Signal.NEUTRAL:
        lines.append("")
        lines.append("<b>План сделки</b>")
        lines.append(f"• Вход: <code>{_fmt_price(plan.entry)}</code>")
        lines.append(f"• Стоп-лосс: <code>{_fmt_price(plan.stop_loss)}</code>")
        lines.append(f"• TP1: <code>{_fmt_price(plan.take_profit_1)}</code>")
        lines.append(f"• TP2: <code>{_fmt_price(plan.take_profit_2)}</code>")
        if plan.risk_reward is not None:
            lines.append(f"• Risk/Reward: <b>{plan.risk_reward:.2f}</b>")

    lines.append("")
    lines.append("<b>Индикаторы по таймфреймам</b>")
    for tf in ("1h", "4h", "1d"):
        if tf in result.snapshots:
            lines.append(_snapshot_block(result.snapshots[tf]))

    if result.summary_reasons:
        lines.append("")
        lines.append("<b>Обоснование</b>")
        for r in result.summary_reasons[:14]:
            lines.append(f"• {_esc(r)}")

    lines.append("")
    lines.append(
        "<i>⚠️ Не финансовая рекомендация. Технический анализ — лишь оценка вероятностей. "
        "Управляйте риском, не рискуйте больше 1–2% депозита на сделку.</i>"
    )
    return "\n".join(lines)
