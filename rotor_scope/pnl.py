"""The part that matters: realised P&L, spread capture and fill rate.

rotor does not keep any of this. Its own state store says so in the source:
"Tiny unresolved-state store; this is not a trade-history database." It holds
currently-open orders and replaces them every tick, so a maker running it can
see what is live but never what it earned. This module reconstructs that from
Sera's /fills.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from decimal import Decimal

from .models import Fill

BPS = Decimal(10_000)


@dataclass
class MarketPnL:
    market: str
    realised_quote: Decimal = Decimal(0)   # profit in the quote currency
    fees_usd: Decimal = Decimal(0)
    matched_base: Decimal = Decimal(0)     # base volume that round-tripped
    open_base: Decimal = Decimal(0)        # inventory still held (+long/-short)
    open_cost_quote: Decimal = Decimal(0)  # cost basis of that inventory
    buys: int = 0
    sells: int = 0
    capture_bps: list[Decimal] = field(default_factory=list)

    @property
    def fills(self) -> int:
        return self.buys + self.sells

    @property
    def avg_capture_bps(self) -> Decimal | None:
        if not self.capture_bps:
            return None
        return sum(self.capture_bps) / Decimal(len(self.capture_bps))

    @property
    def avg_open_price(self) -> Decimal | None:
        if self.open_base == 0:
            return None
        return self.open_cost_quote / self.open_base


def realised_pnl(fills: list[Fill]) -> dict[str, MarketPnL]:
    """FIFO-match buys against sells per market.

    Realised profit is only booked when a position round-trips. Inventory left
    over is reported separately as open_base with its cost basis, never marked
    to market here - an unrealised number that moves with the reference price
    does not belong in the same column as money actually earned.
    """
    out: dict[str, MarketPnL] = {}
    # FIFO lots per market, per direction
    longs: dict[str, deque] = defaultdict(deque)   # (qty, price) bought
    shorts: dict[str, deque] = defaultdict(deque)  # (qty, price) sold short

    for f in sorted(fills, key=lambda x: x.ts):
        m = out.setdefault(f.market, MarketPnL(market=f.market))
        m.fees_usd += f.fee_usd
        qty, px = f.base_amount, f.price
        if qty <= 0:
            continue

        if f.side == "buy":
            m.buys += 1
            book = shorts[f.market]
            while qty > 0 and book:
                s_qty, s_px = book[0]
                take = min(qty, s_qty)
                m.realised_quote += (s_px - px) * take   # sold high, bought back
                m.matched_base += take
                qty -= take
                if take == s_qty:
                    book.popleft()
                else:
                    book[0] = (s_qty - take, s_px)
            if qty > 0:
                longs[f.market].append((qty, px))
        else:
            m.sells += 1
            book = longs[f.market]
            while qty > 0 and book:
                l_qty, l_px = book[0]
                take = min(qty, l_qty)
                m.realised_quote += (px - l_px) * take   # bought low, sold high
                m.matched_base += take
                qty -= take
                if take == l_qty:
                    book.popleft()
                else:
                    book[0] = (l_qty - take, l_px)
            if qty > 0:
                shorts[f.market].append((qty, px))

    for market, m in out.items():
        long_qty = sum(q for q, _ in longs[market])
        long_cost = sum(q * p for q, p in longs[market])
        short_qty = sum(q for q, _ in shorts[market])
        short_cost = sum(q * p for q, p in shorts[market])
        m.open_base = long_qty - short_qty
        m.open_cost_quote = long_cost - short_cost
    return out


def spread_capture(fills: list[Fill], mids: dict[str, Decimal]) -> dict[str, MarketPnL]:
    """How far from the reference mid each fill actually executed, in bps.

    This is the number that says whether the strategy is working. A maker
    configures fixed_bps and assumes it earns roughly that; capture measures
    what it earned instead. Consistently below the configured spread means the
    quotes are being picked off, which no other tool in this stack reports.
    """
    out = realised_pnl(fills)
    for f in fills:
        mid = mids.get(f.market)
        if not mid or mid <= 0:
            continue
        edge = (f.price - mid) / mid * BPS
        # A sell above mid and a buy below mid are both positive capture.
        out[f.market].capture_bps.append(edge if f.side == "sell" else -edge)
    return out


def fill_rate(orders: list[dict]) -> tuple[int, int, float | None]:
    """(filled, placed, rate). Quotes that never get hit are the other half of
    the story: perfect capture on two fills a day is not a working strategy."""
    placed = len(orders)
    if placed == 0:
        return 0, 0, None
    filled = sum(
        1 for o in orders
        if str(o.get("status", "")).lower() in {"matched", "settled", "filled", "partially_filled"}
    )
    return filled, placed, filled / placed


def summarise(per_market: dict[str, MarketPnL]) -> dict:
    return {
        "markets": len(per_market),
        "fills": sum(m.fills for m in per_market.values()),
        "matched_base": sum(m.matched_base for m in per_market.values()),
        "fees_usd": sum(m.fees_usd for m in per_market.values()),
        "realised_by_quote": {
            m.market.split("/")[-1]: sum(
                x.realised_quote for x in per_market.values()
                if x.market.split("/")[-1] == m.market.split("/")[-1]
            )
            for m in per_market.values()
        },
    }
