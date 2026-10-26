"""The price-check job with fakes: no Telegram, no network."""
import asyncio
from decimal import Decimal
from types import SimpleNamespace

import httpx

from bot.main import check
from bot.store import Store


class FakeBinance:
    def __init__(self, prices=None, fail=False):
        self._prices, self.fail, self.calls = prices or {}, fail, 0

    async def prices(self, symbols):
        self.calls += 1
        if self.fail:
            raise httpx.ConnectError("offline")
        return {s: self._prices[s] for s in symbols if s in self._prices}


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


def ctx(store, bn):
    return SimpleNamespace(bot_data={"store": store, "binance": bn}, bot=FakeBot())


def test_fires_once_and_removes():
    s = Store(":memory:")
    s.add(1, "BTCUSDT", ">", Decimal("70000"))
    s.add(1, "ETHUSDT", "<", Decimal("2500"))
    c = ctx(s, FakeBinance({"BTCUSDT": Decimal("70012.5"), "ETHUSDT": Decimal("2600")}))
    asyncio.run(check(c))
    assert [t for _, t in c.bot.sent][0].startswith("📈 <b>BTCUSDT</b> is above 70,000")
    assert [a.symbol for a in s.all()] == ["ETHUSDT"]       # fired alert removed, the other kept
    asyncio.run(check(c))
    assert len(c.bot.sent) == 1                              # no repeat
    assert c.bot_data["binance"].calls == 2                 # one request per tick for all symbols


def test_network_error_keeps_alerts():
    s = Store(":memory:")
    s.add(1, "BTCUSDT", ">", Decimal("1"))
    c = ctx(s, FakeBinance(fail=True))
    asyncio.run(check(c))
    assert not c.bot.sent and len(s.all()) == 1


def test_no_alerts_no_request():
    bn = FakeBinance()
    asyncio.run(check(ctx(Store(":memory:"), bn)))
    assert bn.calls == 0
