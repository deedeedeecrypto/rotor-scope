"""Domain types.

Amounts arrive from Sera as raw integer strings in token base units. They are
converted to Decimal exactly once, here, using the decimals from /tokens. Money
is never a float anywhere in this package.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


def to_decimal(raw: str | int, decimals: int) -> Decimal:
    return Decimal(str(raw)) / (Decimal(10) ** decimals)


def parse_ts(value) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        v = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
    return datetime.now(tz=timezone.utc)


@dataclass(frozen=True)
class Token:
    symbol: str
    address: str
    decimals: int
    currency: str


@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    market: str
    side: str            # "buy" or "sell", from the base token's point of view
    base_symbol: str
    quote_symbol: str
    base_amount: Decimal
    quote_amount: Decimal
    fee_usd: Decimal
    ts: datetime

    @property
    def price(self) -> Decimal:
        """Quote per unit of base. The executed price of this fill."""
        if self.base_amount == 0:
            return Decimal(0)
        return self.quote_amount / self.base_amount


@dataclass(frozen=True)
class Balance:
    symbol: str
    decimals: int
    wallet: Decimal
    vault_available: Decimal
    vault_frozen: Decimal

    @property
    def total(self) -> Decimal:
        return self.wallet + self.vault_available + self.vault_frozen
