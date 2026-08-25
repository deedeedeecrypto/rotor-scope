"""SQLite persistence. rotor throws fill history away; this keeps it."""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

from .models import Fill, parse_ts

SCHEMA = """
CREATE TABLE IF NOT EXISTS fills (
  fill_id TEXT PRIMARY KEY,
  order_id TEXT, market TEXT, side TEXT,
  base_symbol TEXT, quote_symbol TEXT,
  base_amount TEXT, quote_amount TEXT, fee_usd TEXT,
  ts TEXT
);
CREATE INDEX IF NOT EXISTS fills_market_ts ON fills(market, ts);
CREATE TABLE IF NOT EXISTS snapshots (
  taken_at TEXT, symbol TEXT, wallet TEXT, vault_available TEXT, vault_frozen TEXT
);
"""


class Store:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        self.db.commit()

    def upsert_fills(self, fills: list[Fill]) -> int:
        rows = [(f.fill_id, f.order_id, f.market, f.side, f.base_symbol, f.quote_symbol,
                 str(f.base_amount), str(f.quote_amount), str(f.fee_usd), f.ts.isoformat())
                for f in fills]
        before = self.count()
        self.db.executemany(
            "INSERT OR IGNORE INTO fills VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
        self.db.commit()
        return self.count() - before

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM fills").fetchone()[0]

    def all_fills(self) -> list[Fill]:
        out = []
        for r in self.db.execute("SELECT * FROM fills ORDER BY ts"):
            out.append(Fill(r[0], r[1], r[2], r[3], r[4], r[5],
                            Decimal(r[6]), Decimal(r[7]), Decimal(r[8]), parse_ts(r[9])))
        return out

    def close(self):
        self.db.close()
