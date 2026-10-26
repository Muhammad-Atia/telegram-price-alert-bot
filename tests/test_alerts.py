from decimal import Decimal

import pytest

from bot.alerts import Alert, ParseError, fmt, list_text, parse_add, triggered_text
from bot.store import Store


@pytest.mark.parametrize("text, expected", [
    ("BTCUSDT > 70000", ("BTCUSDT", ">", Decimal("70000"))),
    ("btcusdt>70000", ("BTCUSDT", ">", Decimal("70000"))),
    ("ETHUSDT < 2,500.5", ("ETHUSDT", "<", Decimal("2500.5"))),
    ("PEPEUSDT >= 0.00001234", ("PEPEUSDT", ">", Decimal("0.00001234"))),
    ("SOLUSDT <= 150", ("SOLUSDT", "<", Decimal("150"))),
])
def test_parse_ok(text, expected):
    assert parse_add(text) == expected


@pytest.mark.parametrize("text", ["", "BTCUSDT", "BTCUSDT = 70000", "BTCUSDT > abc", "BTCUSDT > 0", "> 70000"])
def test_parse_bad(text):
    with pytest.raises(ParseError):
        parse_add(text)


def test_hit_inclusive():
    up = Alert(1, 1, "BTCUSDT", ">", Decimal("70000"))
    down = Alert(2, 1, "BTCUSDT", "<", Decimal("60000"))
    assert up.hit(Decimal("70000")) and up.hit(Decimal("70000.01")) and not up.hit(Decimal("69999.99"))
    assert down.hit(Decimal("60000")) and down.hit(Decimal("59999")) and not down.hit(Decimal("60000.01"))


def test_fmt():
    assert fmt(Decimal("70000")) == "70,000"
    assert fmt(Decimal("70000.50")) == "70,000.5"
    assert fmt(Decimal("0.00001234")) == "0.00001234"


def test_store_roundtrip_and_ownership():
    s = Store(":memory:")
    a = s.add(10, "BTCUSDT", ">", Decimal("70000"))
    s.add(20, "ETHUSDT", "<", Decimal("2500"))
    assert [x.describe() for x in s.for_chat(10)] == ["BTCUSDT > 70,000"]
    assert not s.remove(20, a.id)          # another chat cannot delete it
    assert s.remove(10, a.id) and s.count(10) == 0
    assert len(s.all()) == 1


def test_messages():
    a = Alert(7, 1, "BTCUSDT", ">", Decimal("70000"))
    assert "BTCUSDT" in triggered_text(a, Decimal("70012.3")) and "70,012.3" in triggered_text(a, Decimal("70012.3"))
    assert list_text([]).startswith("No active alerts")
    assert "#7  BTCUSDT > 70,000" in list_text([a])
