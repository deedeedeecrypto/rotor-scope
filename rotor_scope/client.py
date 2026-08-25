"""Read-only Sera REST client.

Deliberately exposes GET only. There is no request() helper that takes a method,
no post(), and no signing code. Adding one would fail tests/test_readonly.py.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from .config import Config
from .models import Balance, Fill, Token, parse_ts, to_decimal


class SeraReadClient:
    def __init__(self, cfg: Config, timeout: float = 20.0):
        self.cfg = cfg
        self._http = httpx.Client(timeout=timeout, base_url=cfg.base_url)

    # -- internals -------------------------------------------------------
    def _get(self, path: str, *, auth: bool = False, **params) -> Any:
        headers = {}
        if auth:
            if not self.cfg.api_key:
                raise PermissionError(
                    f"{path} needs SERA_API_KEY. Run with --demo for a no-credential walkthrough."
                )
            headers["X-API-Key"] = self.cfg.api_key
            if self.cfg.api_secret:
                headers["X-API-Secret"] = self.cfg.api_secret
        clean = {k: v for k, v in params.items() if v is not None}
        r = self._http.get(path, params=clean, headers=headers)
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._http.close()

    def __enter__(self): return self
    def __exit__(self, *a): self.close()

    # -- public, no credentials needed -----------------------------------
    def tokens(self) -> dict[str, Token]:
        rows = self._get("/tokens").get("tokens", [])
        return {
            r["symbol"]: Token(r["symbol"], r["address"], int(r["decimals"]), r.get("currency", ""))
            for r in rows
        }

    def markets(self) -> list[dict]:
        return self._get("/markets").get("markets", [])

    def fx_rate(self, base: str, quote: str) -> Decimal | None:
        """Reference mid used as the benchmark for spread capture."""
        try:
            body = self._get("/fx/rate", base=base, quote=quote)
        except httpx.HTTPError:
            return None
        rate = body.get("rate")
        return Decimal(str(rate)) if rate is not None else None

    # -- private reads, API key only, never a private key -----------------
    def fills(self, *, limit: int = 500, offset: int = 0,
              settlement_status: str | None = None) -> list[dict]:
        body = self._get(
            "/fills", auth=True,
            owner_address=self.cfg.owner_address,
            limit=limit, offset=offset,
            settlement_status=settlement_status,
        )
        return body.get("fills", body) if isinstance(body, dict) else body

    def orders(self, *, limit: int = 500, offset: int = 0) -> list[dict]:
        body = self._get(
            "/orders", auth=True,
            owner_address=self.cfg.owner_address, limit=limit, offset=offset,
        )
        return body.get("orders", body) if isinstance(body, dict) else body

    def balances(self) -> list[Balance]:
        rows = self._get("/balances", auth=True,
                         owner_address=self.cfg.owner_address).get("balances", [])
        out = []
        for r in rows:
            d = int(r["decimals"])
            out.append(Balance(
                symbol=r["symbol"], decimals=d,
                wallet=to_decimal(r.get("wallet_balance", 0), d),
                vault_available=to_decimal(r.get("vault_available", 0), d),
                vault_frozen=to_decimal(r.get("vault_frozen", 0), d),
            ))
        return out


def normalise_fill(raw: dict, tokens: dict[str, Token]) -> Fill:
    """Map one /fills row onto a Fill.

    Sera returns raw base-unit integers, so decimals come from /tokens rather
    than being assumed. Field names are read defensively because the fills
    payload is the least documented part of the public API.
    """
    base_sym = raw.get("base_symbol") or raw.get("base") or ""
    quote_sym = raw.get("quote_symbol") or raw.get("quote") or ""
    bd = tokens[base_sym].decimals if base_sym in tokens else 18
    qd = tokens[quote_sym].decimals if quote_sym in tokens else 18
    return Fill(
        fill_id=str(raw.get("fill_id") or raw.get("id") or raw.get("uuid")),
        order_id=str(raw.get("order_id") or ""),
        market=raw.get("market") or f"{base_sym}/{quote_sym}",
        side=(raw.get("side") or "buy").lower(),
        base_symbol=base_sym,
        quote_symbol=quote_sym,
        base_amount=to_decimal(raw.get("base_amount") or raw.get("filled_base") or 0, bd),
        quote_amount=to_decimal(raw.get("quote_amount") or raw.get("filled_quote") or 0, qd),
        fee_usd=Decimal(str(raw.get("fee_usd") or raw.get("gas_cost_usd") or 0)),
        ts=parse_ts(raw.get("filled_at") or raw.get("created_at") or raw.get("timestamp")),
    )
