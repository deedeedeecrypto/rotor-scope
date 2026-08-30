# rotor-scope

Read-only P&L, fill and spread-capture monitoring for anyone running a market maker on
Sera — [`rotor`](https://github.com/sera-cx/rotor) or the earn.sera.cx agent.

Built on Sera. `built-on-sera`

## Why

rotor tells you what is quoted right now. It does not tell you whether you are making
money, because it does not keep the data. Its own state store says so in the source:

> Tiny unresolved-state store; this is not a trade-history database.

It holds currently-open orders and pending returns, and replaces them every tick.
Telegram gets a ping per quote and nothing aggregated. So a maker running rotor cannot
answer three basic questions:

1. **Am I actually making money?** Realised P&L per market, FIFO-matched.
2. **Am I capturing the spread I configured?** You set `fixed_bps = 50`. Are you
   earning 50, or are you being picked off?
3. **Are my quotes even getting hit?** Perfect capture on two fills a day is not a
   working strategy.

rotor-scope answers those from Sera's own `/fills`, `/orders` and `/balances`. It
requires no change to rotor and works for anyone already running it.

## Run it in one command, with no credentials

```bash
pip install -e .
rotor-scope demo
```

That generates 240 synthetic fills from a maker quoting ±50 bps that gets adversely
selected on a slice of them, runs the real P&L engine over it, and writes
`rotor-scope.html`. Nothing is mocked except the fills — the arithmetic is the same
code that runs on live data.

```
240 synthetic fills across 2 markets -> rotor-scope.html
  MYRT/USDC    realised     106.7594 USDC  capture    31.0 bps  fills 120  inventory   1941.00
  XSGD/USDC    realised     377.7172 USDC  capture    32.0 bps  fills 120  inventory   2605.00
```

Configured spread was 50 bps. Realised capture is 31. **That gap is the whole point of
the tool** — nothing else in this stack reports it.

## Run it on your own account

```bash
export SERA_BASE_URL="https://api.testnet.sera.cx/api/v1"
export SERA_API_KEY="..."
export SERA_API_SECRET="..."
export SERA_OWNER_ADDRESS="0x..."

rotor-scope sync      # pull fills into a local sqlite store
rotor-scope report    # build the HTML
```

Run `sync` on a cron. Sera paginates `/fills`; the store deduplicates on `fill_id`, so
re-syncing is safe and history accumulates locally even though Sera's own retention is
not something you control.

## It cannot touch your funds

**rotor-scope never holds a private key and never writes to Sera.** It reads an API key
and an owner address, nothing more. There is no signing code, no order placement, no
withdrawal path, and the HTTP client exposes `GET` only.

That is enforced, not promised: `tests/test_readonly.py` greps the whole package for
`.post(`, `.put(`, `.delete(`, `.patch(`, `private_key`, `eth_account` and the signing
helpers, and fails the build if any of them appear.

```bash
pytest
```

## What the numbers mean

**Realised** is booked only when a position round-trips, FIFO-matched per market.

**Inventory** is what is still held, shown with its cost basis and deliberately *not*
marked to market. An unrealised number that moves with the price does not belong in the
same column as money actually earned.

**Capture bps** measures each fill against the reference mid from `/fx/rate`. A sell
above mid and a buy below mid both count positive. Consistently below your configured
`fixed_bps` means your quotes are being picked off — the maker is buying the losing side
of an informed flow.

**Gas** is tracked separately per market. Sera charges a flat fee per swap regardless of
size, so on small clips it is the dominant cost and a strategy can show positive capture
while losing money net.

## Layout

```
rotor_scope/
  config.py   env config; no private key, ever
  client.py   read-only Sera REST client (GET only)
  models.py   Decimal-only money types; raw base units converted once
  pnl.py      FIFO realised P&L, spread capture, fill rate
  store.py    sqlite; the history rotor throws away
  demo.py     deterministic synthetic fills
  report.py   single-file HTML, no CDN, opens from disk
```

Money is `Decimal` everywhere. There is no `float` in any code path that touches an
amount.

## Licence

MIT.


## Trying it against a real account

rotor-scope only reads, so it needs an account with fills in it. If you do not have one:
https://g.sera.cx/2LvTnQG9gQ

That is my referral link, so signing up through it earns us both community points. If
you would rather not, sera.cx signs you up exactly the same way.
