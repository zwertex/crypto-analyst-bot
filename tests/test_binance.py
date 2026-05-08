"""Tests for Binance client (using respx to mock HTTP)."""
from __future__ import annotations

import httpx
import pytest
import respx

from bot.services.binance import (
    BinanceClient,
    BinanceError,
    SymbolNotFoundError,
)

EXCHANGE_INFO = {
    "symbols": [
        {"symbol": "BTCUSDT", "status": "TRADING"},
        {"symbol": "ETHUSDT", "status": "TRADING"},
        {"symbol": "ETHBTC", "status": "TRADING"},
        {"symbol": "DELISTED", "status": "BREAK"},
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_resolve_symbol_btc() -> None:
    respx.get("https://api.binance.com/api/v3/exchangeInfo").mock(
        return_value=httpx.Response(200, json=EXCHANGE_INFO)
    )
    async with BinanceClient() as bc:
        assert await bc.resolve_symbol("btc") == "BTCUSDT"
        assert await bc.resolve_symbol("BTCUSDT") == "BTCUSDT"
        assert await bc.resolve_symbol("eth/usdt") == "ETHUSDT"
        assert await bc.resolve_symbol("eth-btc") == "ETHBTC"


@pytest.mark.asyncio
@respx.mock
async def test_resolve_symbol_unknown_raises() -> None:
    respx.get("https://api.binance.com/api/v3/exchangeInfo").mock(
        return_value=httpx.Response(200, json=EXCHANGE_INFO)
    )
    async with BinanceClient() as bc:
        with pytest.raises(SymbolNotFoundError):
            await bc.resolve_symbol("notacoin")


@pytest.mark.asyncio
@respx.mock
async def test_resolve_symbol_excludes_delisted() -> None:
    respx.get("https://api.binance.com/api/v3/exchangeInfo").mock(
        return_value=httpx.Response(200, json=EXCHANGE_INFO)
    )
    async with BinanceClient() as bc:
        with pytest.raises(SymbolNotFoundError):
            await bc.resolve_symbol("DELISTED")


@pytest.mark.asyncio
@respx.mock
async def test_resolve_empty_input_raises() -> None:
    respx.get("https://api.binance.com/api/v3/exchangeInfo").mock(
        return_value=httpx.Response(200, json=EXCHANGE_INFO)
    )
    async with BinanceClient() as bc:
        with pytest.raises(SymbolNotFoundError):
            await bc.resolve_symbol("   ")


@pytest.mark.asyncio
@respx.mock
async def test_get_klines_parses_rows() -> None:
    raw = [
        [1, "100", "110", "90", "105", "1000", 9, "100000", 50, "0", "0", "0"]
        for _ in range(3)
    ]
    respx.get("https://api.binance.com/api/v3/klines").mock(
        return_value=httpx.Response(200, json=raw)
    )
    async with BinanceClient() as bc:
        candles = await bc.get_klines("BTCUSDT", "1h", limit=3)
        assert len(candles) == 3
        assert candles[0].close == 105.0


@pytest.mark.asyncio
@respx.mock
async def test_get_ticker_24h() -> None:
    respx.get("https://api.binance.com/api/v3/ticker/24hr").mock(
        return_value=httpx.Response(
            200,
            json={
                "symbol": "BTCUSDT",
                "priceChange": "100",
                "priceChangePercent": "1.5",
                "lastPrice": "60000",
                "highPrice": "61000",
                "lowPrice": "59000",
                "volume": "1000",
                "quoteVolume": "60000000",
            },
        )
    )
    async with BinanceClient() as bc:
        t = await bc.get_ticker_24h("BTCUSDT")
        assert t.last_price == 60000.0
        assert t.price_change_pct == 1.5


@pytest.mark.asyncio
@respx.mock
async def test_funding_rate_returns_none_on_error() -> None:
    respx.get("https://fapi.binance.com/fapi/v1/premiumIndex").mock(
        return_value=httpx.Response(400, json={"msg": "no perp"})
    )
    async with BinanceClient() as bc:
        rate = await bc.get_funding_rate("FOOBAR")
        assert rate is None


@pytest.mark.asyncio
@respx.mock
async def test_http_error_raises_binance_error() -> None:
    respx.get("https://api.binance.com/api/v3/ticker/24hr").mock(
        return_value=httpx.Response(500, text="boom")
    )
    async with BinanceClient() as bc:
        with pytest.raises(BinanceError):
            await bc.get_ticker_24h("BTCUSDT")
