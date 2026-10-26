"""Binance public market data: no API key, no account. https://developers.binance.com/docs/binance-spot-api-docs/rest-api"""
from __future__ import annotations

import json
from decimal import Decimal

import httpx

BASE = "https://api.binance.com"


class Binance:
    def __init__(self, base: str = BASE, timeout: float = 10.0):
        self.http = httpx.AsyncClient(base_url=base, timeout=timeout)
        self._symbols: set[str] | None = None

    async def close(self) -> None:
        await self.http.aclose()

    async def symbols(self) -> set[str]:
        """Every tradable spot symbol, loaded once (used to validate /add)."""
        if self._symbols is None:
            r = await self.http.get("/api/v3/exchangeInfo", params={"permissions": "SPOT"})
            r.raise_for_status()
            self._symbols = {s["symbol"] for s in r.json()["symbols"] if s.get("status") == "TRADING"}
        return self._symbols

    async def prices(self, symbols: set[str]) -> dict[str, Decimal]:
        """Last price of several symbols in ONE request (request weight 4, whatever the number of symbols)."""
        if not symbols:
            return {}
        r = await self.http.get("/api/v3/ticker/price", params={"symbols": json.dumps(sorted(symbols), separators=(",", ":"))})
        r.raise_for_status()
        return {x["symbol"]: Decimal(x["price"]) for x in r.json()}

    async def price(self, symbol: str) -> Decimal:
        r = await self.http.get("/api/v3/ticker/price", params={"symbol": symbol})
        r.raise_for_status()
        return Decimal(r.json()["price"])
