"""Deterministic synthetic fills so the tool runs with no credentials.

A reviewer can clone this repo and see a real report in one command. That
matters more than it sounds: the alternative is a README screenshot, and a
screenshot proves nothing about whether the P&L maths is right.

The generator models a maker that quotes +/- 50 bps around a drifting mid and
gets adversely selected on a slice of fills, so the spread-capture column shows
something worth reading rather than a flat 50.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .models import Fill

MARKETS = [("XSGD", "USDC", Decimal("0.78")), ("MYRT", "USDC", Decimal("0.2487"))]


def generate(n: int = 240, seed: int = 7) -> tuple[list[Fill], dict[str, Decimal]]:
    rng = random.Random(seed)
    start = datetime(2026, 8, 18, tzinfo=timezone.utc)
    fills: list[Fill] = []
    mids: dict[str, Decimal] = {}

    for base, quote, anchor in MARKETS:
        market = f"{base}/{quote}"
        mid = anchor
        mids[market] = anchor
        for i in range(n // len(MARKETS)):
            # mid drifts slowly
            mid += Decimal(rng.randint(-6, 6)) / Decimal(100_000)
            side = "buy" if i % 2 == 0 else "sell"
            edge = Decimal(50)
            # one fill in four is picked off: filled at a worse edge
            if rng.random() < 0.25:
                edge = Decimal(rng.randint(-30, 15))
            signed = edge if side == "sell" else -edge
            price = (mid * (Decimal(10_000) + signed) / Decimal(10_000)).quantize(Decimal("0.000001"))
            qty = Decimal(rng.randint(200, 2200))
            fills.append(Fill(
                fill_id=f"demo-{market}-{i}",
                order_id=f"ord-{market}-{i // 2}",
                market=market,
                side=side,
                base_symbol=base,
                quote_symbol=quote,
                base_amount=qty,
                quote_amount=(qty * price).quantize(Decimal("0.000001")),
                fee_usd=Decimal("1.00"),
                ts=start + timedelta(minutes=17 * i),
            ))
        mids[market] = mid
    return fills, mids


def demo_orders(fills: list[Fill]) -> list[dict]:
    """Placed-but-unfilled quotes, so fill rate is not trivially 100%."""
    orders = [{"order_id": f.order_id, "status": "settled"} for f in fills]
    orders += [{"order_id": f"unfilled-{i}", "status": "cancelled"} for i in range(len(fills) * 2)]
    return orders
