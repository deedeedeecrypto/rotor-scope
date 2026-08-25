"""Configuration. Read-only by construction.

rotor-scope NEVER holds a private key. It reads an API key/secret and an owner
address, nothing else. There is no code path in this package that signs a
payload, places an order, or moves funds. See tests/test_readonly.py, which
fails the build if that ever stops being true.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

TESTNET = "https://api.testnet.sera.cx/api/v1"
MAINNET = "https://api.sera.cx/api/v1"


@dataclass(frozen=True)
class Config:
    base_url: str = TESTNET
    api_key: str | None = None
    api_secret: str | None = None
    owner_address: str | None = None
    db_path: str = "rotor_scope.sqlite"
    demo: bool = False

    @classmethod
    def from_env(cls, demo: bool = False) -> "Config":
        owner = os.getenv("SERA_OWNER_ADDRESS")
        return cls(
            base_url=os.getenv("SERA_BASE_URL", TESTNET).rstrip("/"),
            api_key=os.getenv("SERA_API_KEY"),
            api_secret=os.getenv("SERA_API_SECRET"),
            # Sera's read endpoints treat owner_address as case-sensitive and
            # want the lowercase form.
            owner_address=owner.lower() if owner else None,
            db_path=os.getenv("ROTOR_SCOPE_DB", "rotor_scope.sqlite"),
            demo=demo,
        )

    @property
    def can_read_private(self) -> bool:
        """/fills, /orders and /balances need a key. Public data does not."""
        return bool(self.api_key and self.owner_address)
