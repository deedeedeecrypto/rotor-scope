"""rotor-scope CLI: sync, report, demo."""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from .client import SeraReadClient, normalise_fill
from .config import Config
from .demo import demo_orders, generate
from .pnl import fill_rate, spread_capture
from .report import render
from .store import Store


def _write(html: str, out: str) -> str:
    Path(out).write_text(html, encoding="utf-8")
    return out


def cmd_demo(args) -> int:
    fills, mids = generate(n=args.fills)
    per_market = spread_capture(fills, mids)
    fr = fill_rate(demo_orders(fills))
    path = _write(render(per_market, fills, fr, stamp="demo data"), args.out)
    print(f"{len(fills)} synthetic fills across {len(per_market)} markets -> {path}")
    for m in sorted(per_market.values(), key=lambda x: x.market):
        cap = m.avg_capture_bps
        ccy = m.market.split("/")[-1]
        cap_txt = f"{cap:>7.1f} bps" if cap is not None else "      -"
        print(f"  {m.market:<12} realised {m.realised_quote:>12.4f} {ccy:<5} capture {cap_txt}"
              f"  fills {m.fills:>3}  inventory {m.open_base:>9.2f}")
    return 0


def cmd_sync(args) -> int:
    cfg = Config.from_env()
    if not cfg.can_read_private:
        print("Need SERA_API_KEY and SERA_OWNER_ADDRESS. Try: rotor-scope demo", file=sys.stderr)
        return 2
    with SeraReadClient(cfg) as c:
        tokens = c.tokens()
        raw = c.fills(limit=args.limit)
        fills = [normalise_fill(r, tokens) for r in raw]
    store = Store(cfg.db_path)
    added = store.upsert_fills(fills)
    print(f"fetched {len(fills)}, {added} new, {store.count()} stored in {cfg.db_path}")
    store.close()
    return 0


def cmd_report(args) -> int:
    cfg = Config.from_env()
    store = Store(cfg.db_path)
    fills = store.all_fills()
    store.close()
    if not fills:
        print("No fills stored. Run 'rotor-scope sync' first, or 'rotor-scope demo'.", file=sys.stderr)
        return 2
    mids: dict[str, Decimal] = {}
    if cfg.api_key or True:
        try:
            with SeraReadClient(cfg) as c:
                for market in {f.market for f in fills}:
                    b, q = market.split("/")
                    r = c.fx_rate(b, q)
                    if r:
                        mids[market] = r
        except Exception as e:  # reference price is a nice-to-have, not required
            print(f"reference mid unavailable ({e}); capture column will be blank", file=sys.stderr)
    per_market = spread_capture(fills, mids)
    fr = fill_rate([])
    path = _write(render(per_market, fills, fr), args.out)
    print(f"{len(fills)} fills -> {path}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="rotor-scope",
                                description="Read-only P&L and spread-capture monitoring for Sera market makers.")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="run on synthetic fills, no credentials needed")
    d.add_argument("--fills", type=int, default=240)
    d.add_argument("--out", default="rotor-scope.html")
    d.set_defaults(func=cmd_demo)

    s = sub.add_parser("sync", help="fetch fills from Sera into the local store")
    s.add_argument("--limit", type=int, default=500)
    s.set_defaults(func=cmd_sync)

    r = sub.add_parser("report", help="build the HTML report from stored fills")
    r.add_argument("--out", default="rotor-scope.html")
    r.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
