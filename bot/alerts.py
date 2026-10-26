"""Pure logic: parsing commands, deciding when an alert fires, formatting messages. No I/O, easy to test."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

OPS = {">": "above", "<": "below"}
_ADD = re.compile(r"^\s*([A-Za-z0-9]{2,20})\s*(>=|<=|>|<)\s*([0-9][0-9_,]*\.?[0-9]*)\s*$")


@dataclass(frozen=True)
class Alert:
    id: int
    chat_id: int
    symbol: str
    op: str          # ">" or "<"
    price: Decimal

    def hit(self, last: Decimal) -> bool:
        """'>' fires at or above the level, '<' at or below it."""
        return last >= self.price if self.op == ">" else last <= self.price

    def describe(self) -> str:
        return f"{self.symbol} {self.op} {fmt(self.price)}"


class ParseError(ValueError):
    pass


def parse_add(text: str) -> tuple[str, str, Decimal]:
    """'BTCUSDT > 70000' -> ('BTCUSDT', '>', Decimal('70000')). '>=' / '<=' are accepted as '>' / '<'."""
    m = _ADD.match(text or "")
    if not m:
        raise ParseError("Usage: /add SYMBOL > PRICE   e.g. /add BTCUSDT > 70000")
    symbol, op, raw = m.group(1).upper(), m.group(2)[0], m.group(3).replace(",", "").replace("_", "")
    try:
        price = Decimal(raw)
    except InvalidOperation:
        raise ParseError(f"'{m.group(3)}' is not a price") from None
    if price <= 0:
        raise ParseError("The price must be above zero")
    return symbol, op, price


def fmt(x: Decimal) -> str:
    """70000 -> '70,000', 0.00001234 -> '0.00001234': thousands separators, no trailing zeros."""
    q = x.normalize()
    whole, _, frac = f"{q:f}".partition(".")
    return f"{int(whole):,}" + (f".{frac}" if frac else "")


def triggered_text(a: Alert, last: Decimal) -> str:
    arrow = "📈" if a.op == ">" else "📉"
    return f"{arrow} <b>{a.symbol}</b> is {OPS[a.op]} {fmt(a.price)}\nLast price: <b>{fmt(last)}</b>\n<i>Alert #{a.id} removed.</i>"


def list_text(alerts: list[Alert]) -> str:
    if not alerts:
        return "No active alerts. Add one with /add BTCUSDT > 70000"
    return "Your alerts:\n" + "\n".join(f"#{a.id}  {a.describe()}" for a in alerts)
