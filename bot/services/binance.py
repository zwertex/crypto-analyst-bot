"""Binance public REST client.

Uses only public endpoints (no API key required). Provides:
- exchange info / symbol validation
- klines (candles) for multiple timeframes
- 24h ticker statistics
- futures funding rate (best-effort)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SPOT_BASE_URL = "https://api.binance.com"
FAPI_BASE_URL = "https://fapi.binance.com"

DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


@dataclass(frozen=True)
class Candle:
    """A single OHLCV candle."""

    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float
    trades: int

    @classmethod
    def from_array(cls, raw: list[Any]) -> Candle:
        return cls(
            open_time=int(raw[0]),
            open=float(raw[1]),
            high=float(raw[2]),
            low=float(raw[3]),
            close=float(raw[4]),
            volume=float(raw[5]),
            close_time=int(raw[6]),
            quote_volume=float(raw[7]),
            trades=int(raw[8]),
        )


@dataclass(frozen=True)
class Ticker24h:
    """24-hour rolling window statistics."""

    symbol: str
    price_change: float
    price_change_pct: float
    last_price: float
    high: float
    low: float
    volume: float
    quote_volume: float


class BinanceError(Exception):
    """Binance API error wrapper."""


class SymbolNotFoundError(BinanceError):
    """Raised when a symbol does not exist on the exchange."""


class BinanceClient:
    """Thin async client over Binance public REST API."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        self._owns_client = client is None
        self._symbols_cache: set[str] | None = None
        self._symbols_lock = asyncio.Lock()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> BinanceClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def _get(self, base: str, path: str, **params: Any) -> Any:
        url = f"{base}{path}"
        try:
            r = await self._client.get(url, params={k: v for k, v in params.items() if v is not None})
        except httpx.HTTPError as e:
            raise BinanceError(f"network error: {e}") from e
        if r.status_code != 200:
            raise BinanceError(f"http {r.status_code}: {r.text[:200]}")
        return r.json()

    async def get_exchange_symbols(self) -> set[str]:
        """Return cached set of TRADING spot symbols (e.g. {'BTCUSDT', 'ETHUSDT', ...})."""
        if self._symbols_cache is not None:
            return self._symbols_cache
        async with self._symbols_lock:
            if self._symbols_cache is not None:
                return self._symbols_cache
            data = await self._get(SPOT_BASE_URL, "/api/v3/exchangeInfo")
            symbols = {
                s["symbol"]
                for s in data.get("symbols", [])
                if s.get("status") == "TRADING"
            }
            self._symbols_cache = symbols
            logger.info("loaded %d trading symbols from Binance", len(symbols))
            return symbols

    async def resolve_symbol(self, raw_input: str) -> str:
        """Normalise user input to a real Binance symbol.

        Examples:
            'btc' -> 'BTCUSDT'
            'BTC/USDT' -> 'BTCUSDT'
            'eth-usdt' -> 'ETHUSDT'
            'BTCUSDT' -> 'BTCUSDT'
            'sol' -> 'SOLUSDT'
        Raises SymbolNotFoundError if no match.
        """
        cleaned = "".join(ch for ch in raw_input.upper() if ch.isalnum())
        if not cleaned:
            raise SymbolNotFoundError("empty symbol")
        if len(cleaned) > 20:
            raise SymbolNotFoundError("symbol too long")

        symbols = await self.get_exchange_symbols()

        if cleaned in symbols:
            return cleaned

        for quote in ("USDT", "USDC", "BUSD", "BTC", "ETH"):
            candidate = f"{cleaned}{quote}"
            if candidate in symbols:
                return candidate

        for quote in ("USDT", "USDC", "BUSD"):
            if cleaned.endswith(quote):
                base = cleaned[: -len(quote)]
                candidate = f"{base}{quote}"
                if candidate in symbols:
                    return candidate

        raise SymbolNotFoundError(f"symbol {raw_input!r} not found on Binance")

    async def get_klines(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be in [1, 1000]")
        data = await self._get(
            SPOT_BASE_URL,
            "/api/v3/klines",
            symbol=symbol,
            interval=interval,
            limit=limit,
        )
        return [Candle.from_array(row) for row in data]

    async def get_ticker_24h(self, symbol: str) -> Ticker24h:
        data = await self._get(SPOT_BASE_URL, "/api/v3/ticker/24hr", symbol=symbol)
        return Ticker24h(
            symbol=data["symbol"],
            price_change=float(data["priceChange"]),
            price_change_pct=float(data["priceChangePercent"]),
            last_price=float(data["lastPrice"]),
            high=float(data["highPrice"]),
            low=float(data["lowPrice"]),
            volume=float(data["volume"]),
            quote_volume=float(data["quoteVolume"]),
        )

    async def get_funding_rate(self, symbol: str) -> float | None:
        """Return the latest funding rate for a USDT-margined perpetual, if available."""
        try:
            data = await self._get(
                FAPI_BASE_URL,
                "/fapi/v1/premiumIndex",
                symbol=symbol,
            )
        except BinanceError:
            return None
        rate = data.get("lastFundingRate")
        if rate is None:
            return None
        try:
            return float(rate)
        except (TypeError, ValueError):
            return None
