from datetime import datetime, timedelta, timezone
from decimal import Decimal

from rotor_scope.models import Fill
from rotor_scope.pnl import realised_pnl, spread_capture

T0 = datetime(2026, 8, 20, tzinfo=timezone.utc)


def mk(i, side, qty, price, market="XSGD/USDC"):
    q = Decimal(str(qty)); p = Decimal(str(price))
    return Fill(f"f{i}", f"o{i}", market, side, "XSGD", "USDC", q, q * p,
                Decimal("1.00"), T0 + timedelta(minutes=i))


def test_round_trip_books_profit():
    fills = [mk(0, "buy", 1000, "0.780"), mk(1, "sell", 1000, "0.790")]
    m = realised_pnl(fills)["XSGD/USDC"]
    assert m.realised_quote == Decimal("10.000")   # 1000 * 0.01
    assert m.matched_base == Decimal(1000)
    assert m.open_base == Decimal(0)


def test_unmatched_inventory_is_not_profit():
    fills = [mk(0, "buy", 1000, "0.780")]
    m = realised_pnl(fills)["XSGD/USDC"]
    assert m.realised_quote == Decimal(0)
    assert m.open_base == Decimal(1000)
    assert m.avg_open_price == Decimal("0.780")


def test_fifo_partial_match():
    fills = [mk(0, "buy", 1000, "0.780"), mk(1, "buy", 1000, "0.800"),
             mk(2, "sell", 1500, "0.810")]
    m = realised_pnl(fills)["XSGD/USDC"]
    # 1000 @ .78 -> .81 = 30 ; 500 @ .80 -> .81 = 5
    assert m.realised_quote == Decimal("35.000")
    assert m.open_base == Decimal(500)


def test_capture_sign_is_direction_aware():
    # sell above mid and buy below mid are both positive capture
    fills = [mk(0, "sell", 100, "0.7839"), mk(1, "buy", 100, "0.7761")]
    out = spread_capture(fills, {"XSGD/USDC": Decimal("0.78")})
    caps = out["XSGD/USDC"].capture_bps
    assert all(c > 0 for c in caps), caps
    assert abs(caps[0] - Decimal(50)) < Decimal("0.5")


def test_being_picked_off_shows_negative():
    fills = [mk(0, "sell", 100, "0.7761")]   # sold BELOW mid
    out = spread_capture(fills, {"XSGD/USDC": Decimal("0.78")})
    assert out["XSGD/USDC"].avg_capture_bps < 0
