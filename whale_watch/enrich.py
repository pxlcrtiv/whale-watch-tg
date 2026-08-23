"""Address enrichment — tag the sender/receiver of a transfer.

Bundled known-address list (exchange hot/cold wallets, DEX routers, treasuries)
is community-maintained, best-effort public data. It powers the core heuristic
"inflow to exchange = likely sell pressure" and the demo.

Warning: exchange wallets change over time; treat tags as hints, not facts.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
KNOWN_ADDRESSES_PATH = DATA_DIR / "known_addresses.json"
TOKENS_PATH = DATA_DIR / "tokens.json"

# Direction vocabulary used across the renderer + summarizer.
DIR_TO_EXCHANGE = "to_exchange"
DIR_FROM_EXCHANGE = "from_exchange"
DIR_P2P = "p2p"
DIR_INTERNAL = "internal"

_cached_known: dict[str, dict] | None = None


def load_known_addresses() -> dict[str, dict]:
    """Lowercased address -> {"name": ..., "kind": ...}."""
    global _cached_known
    if _cached_known is None:
        raw = json.loads(KNOWN_ADDRESSES_PATH.read_text(encoding="utf-8"))
        _cached_known = {
            entry["address"].lower(): {"name": entry["name"], "kind": entry["kind"]}
            for entry in raw["addresses"]
        }
    return _cached_known


def reload_known_addresses() -> None:
    global _cached_known
    _cached_known = None


def tag_address(address: str, known: dict[str, dict] | None = None) -> tuple[str, str] | None:
    """Return (name, kind) if the address is in the known list, else None."""
    known = known if known is not None else load_known_addresses()
    entry = known.get(address.lower())
    return (entry["name"], entry["kind"]) if entry else None


def classify_direction(from_tag: tuple[str, str] | None, to_tag: tuple[str, str] | None) -> str:
    """Exchange-in/exchange-out heuristic behind the sell-pressure narrative.

    Rule order matters: an exchange on the receiving side wins (inflow = sell
    pressure) unless BOTH sides are exchanges (institutional rebalancing).
    """
    from_ex = from_tag is not None and from_tag[1] == "exchange"
    to_ex = to_tag is not None and to_tag[1] == "exchange"
    if from_ex and to_ex:
        # Same entity hot->cold / cold->hot is internal noise; cross-exchange
        # moves are institutional settlement, not retail sell pressure.
        return DIR_INTERNAL if from_tag[0] == to_tag[0] else DIR_P2P
    if to_ex:
        return DIR_TO_EXCHANGE
    if from_ex:
        return DIR_FROM_EXCHANGE
    return DIR_P2P


def load_tokens() -> dict[str, dict]:
    """chain -> token_address -> {"symbol": ..., "decimals": ...}."""
    return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))


def token_symbols(chain: str = "ethereum") -> dict[str, str]:
    """Address -> token symbol for the given chain (lowercased keys)."""
    return {
        addr.lower(): meta["symbol"]
        for addr, meta in load_tokens().get(chain, {}).items()
    }