"""Single-file HTML report. No CDN, no build step, opens from disk."""
from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone
from html import escape


def _fmt(v, places="0.01"):
    if v is None:
        return "&mdash;"
    return f"{Decimal(v).quantize(Decimal(places)):,}"


def render(per_market, fills, fr, stamp: str | None = None) -> str:
    filled, placed, rate = fr
    stamp = stamp or datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = []
    for m in sorted(per_market.values(), key=lambda x: x.market):
        cap = m.avg_capture_bps
        cap_cls = "good" if cap is not None and cap > 0 else "bad"
        pnl_cls = "good" if m.realised_quote > 0 else ("bad" if m.realised_quote < 0 else "")
        rows.append(f"""<tr>
<td class="m">{escape(m.market)}</td>
<td class="n {pnl_cls}">{_fmt(m.realised_quote, '0.0001')} {escape(m.market.split('/')[-1])}</td>
<td class="n {cap_cls}">{_fmt(cap) if cap is not None else '&mdash;'}</td>
<td class="n">{m.fills}</td>
<td class="n">{_fmt(m.matched_base, '0.01')}</td>
<td class="n">{_fmt(m.open_base, '0.01')}</td>
<td class="n">{_fmt(m.avg_open_price, '0.000001') if m.avg_open_price else '&mdash;'}</td>
<td class="n">{_fmt(m.fees_usd)}</td>
</tr>""")

    total_fees = sum(m.fees_usd for m in per_market.values())
    total_fills = sum(m.fills for m in per_market.values())
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>rotor-scope</title>
<style>
:root{{--bg:#fbfbfa;--fg:#1b1b19;--dim:#6b6b66;--line:#e5e4e0;--good:#0f7b52;--bad:#b4341f;--card:#fff}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0d0e10;--fg:#e9e9e6;--dim:#8b8b85;--line:#26272b;--good:#4ade80;--bad:#f87171;--card:#141518}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;padding:32px 20px}}
.wrap{{max-width:1000px;margin:0 auto}}
h1{{font-size:20px;margin:0 0 4px;letter-spacing:-.01em}}
.sub{{color:var(--dim);font-size:13px;margin-bottom:24px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:24px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.tile .k{{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.06em}}
.tile .v{{font-size:22px;font-variant-numeric:tabular-nums;margin-top:4px}}
.scroll{{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}}
table{{border-collapse:collapse;width:100%;min-width:760px}}
th,td{{padding:10px 14px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}}
th{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);font-weight:600}}
tr:last-child td{{border-bottom:none}}
td.n{{text-align:right;font-variant-numeric:tabular-nums}}
td.m{{font-weight:600}}
.good{{color:var(--good)}} .bad{{color:var(--bad)}}
.note{{color:var(--dim);font-size:12px;margin-top:18px;max-width:70ch}}
</style></head><body><div class="wrap">
<h1>rotor-scope</h1>
<div class="sub">Read-only. {stamp}</div>
<div class="tiles">
<div class="tile"><div class="k">Fills</div><div class="v">{total_fills}</div></div>
<div class="tile"><div class="k">Fill rate</div><div class="v">{'&mdash;' if rate is None else f'{rate*100:.1f}%'}</div></div>
<div class="tile"><div class="k">Quotes placed</div><div class="v">{placed}</div></div>
<div class="tile"><div class="k">Gas paid</div><div class="v">${_fmt(total_fees)}</div></div>
</div>
<div class="scroll"><table>
<thead><tr><th>Market</th><th style="text-align:right">Realised</th><th style="text-align:right">Capture bps</th>
<th style="text-align:right">Fills</th><th style="text-align:right">Round-tripped</th>
<th style="text-align:right">Inventory</th><th style="text-align:right">Cost basis</th><th style="text-align:right">Gas</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan="8" style="color:var(--dim)">No fills yet.</td></tr>'}</tbody>
</table></div>
<p class="note">Realised is booked only on round-trips. Inventory is what is still held and is
deliberately not marked to market, so an unrealised number that moves with price never sits in
the same column as money actually earned. Capture is measured against the reference mid: a sell
above mid and a buy below mid both count positive. Capture well under your configured
<code>fixed_bps</code> means the quotes are being picked off.</p>
</div></body></html>"""
