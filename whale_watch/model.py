"""Core data models: Transfer (a decoded on-chain token movement) and Alert
(the enriched, user-facing version of a transfer)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Rate classes by USD size (inclusive lower bounds).
RATE_MEGA = "MEGA MOVE"
RATE_LARGE = "LARGE"
RATE_WATCH = "WATCH"
RATE_CLASSES = ((Decimal(10_000_000), RATE_MEGA), (Decimal(1_000_000), RATE_LARGE), (Decimal(100_000), RATE_WATCH))


@dataclass(frozen=True)
class Transfer:
    """A decoded ERC-20 (or fixture) transfer between two addresses."""

    tx_hash: str
    log_index: int
    block: int
    timestamp: int | None  # unix seconds; None when unknown (live scanning without ts)
    token: str            # symbol, e.g. "USDT", "ETH"
    token_address: str    # token contract (zero address for native ETH fixtures)
    from_addr: str        # normalized lowercase
    to_addr: str          # normalized lowercase
    amount: Decimal       # human units (decimals applied)
    value_usd: Decimal | None = None

    def amount_fmt(self) -> str:
        """3,000 / 45,200,000 — comma-grouped integer part (fraction kept ≤2)."""
        q = self.amount.quantize(Decimal("0.01"))
        return f"{q:,.2f}".rstrip("0").rstrip(".")

    def __post_init__(self) -> None:
        # Lowercase only identifiers (addresses/hashes); token symbols keep case.
        for field in ("tx_hash", "token_address", "from_addr", "to_addr"):
            object.__setattr__(self, field, str(getattr(self, field)).lower())


@dataclass(frozen=True)
class Alert:
    """A transfer ready to be delivered: enriched, summarized, rendered."""

    transfer: Transfer
    from_tag: str | None      # exchange/entity name of the sender
    to_tag: str | None        # exchange/entity name of the receiver
    direction: str            # to_exchange | from_exchange | p2p | internal
    narrative: str            # one-two sentence LLM-style summary (template fallback)
    summary: str              # full rendered alert text (exactly what a subscriber sees)
    rate_class: str
    source: str               # "live" | "fixture"


def rate_class_for(value_usd: Decimal | None) -> str:
    if not value_usd:
        return RATE_WATCH
    for floor, label in RATE_CLASSES:
        if value_usd >= floor:
            return label
    return RATE_WATCH


def fmt_usd(value: Decimal | None) -> str:
    """$7.20M · $123.4K · $123.45 — compact USD formatting."""
    if value is None:
        return "USD estimate unavailable"
    x = float(value)
    if x >= 1e9:
        return f"${x / 1e9:.2f}B"
    if x >= 1e6:
        return f"${x / 1e6:.2f}M"
    if x >= 1e3:
        return f"${x / 1e3:.1f}K"
    return f"${x:,.2f}"


def short_addr(address: str) -> str:
    """0x28c6c062…bf21d60 — readable truncation of a hex address."""
    return f"{address[:10]}…{address[-8:]}"


def _norm16(hex_address: str) -> str:
    """Padding-only fix: strip leading zeros from a 32-byte topic field."""
    h = hex_address.removeprefix("0x")
    return "0x" + h[-40:].lower()