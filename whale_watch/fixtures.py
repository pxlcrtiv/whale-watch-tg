"""Bundled fixture transfers — the zero-key demo data.

Realistic but synthetic: tx hashes are obviously fake (0x0000…N pattern) while
the tagged exchange addresses come from the bundled known-address list, so the
demo exercises the exact same enrichment/summarization pipeline as live mode.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .enrich import classify_direction, load_known_addresses, tag_address
from .model import Transfer
from .summarizer import Summarizer

FIXTURES_PATH = Path(__file__).parent / "data" / "fixtures" / "transfers.json"


def load_fixture_transfers(path: str | Path | None = None) -> list[Transfer]:
    raw = json.loads((Path(path) if path else FIXTURES_PATH).read_text(encoding="utf-8"))
    out: list[Transfer] = []
    for item in raw["transfers"]:
        out.append(
            Transfer(
                tx_hash=item["tx_hash"],
                log_index=item["log_index"],
                block=int(item["block"]),
                timestamp=int(item.get("ts") or 0),
                token=item["token"],
                token_address=item["token_address"],
                from_addr=item["from"],
                to_addr=item["to"],
                amount=Decimal(item["amount"]),
                value_usd=Decimal(item["value_usd"]) if item.get("value_usd") else None,
            )
        )
    return out


def run_fixture_demo(
    transfers: list[Transfer] | None = None,
    summarizer: Summarizer | None = None,
    source: str = "fixture",
) -> list:
    """Full pipeline over the fixtures: enrich -> summarize -> render.

    Returns the Alert list. Pure (no DB, no network) so the demo is keyless and
    deterministic under test.
    """
    known = load_known_addresses()
    summarizer = summarizer or Summarizer()
    transfers = transfers if transfers is not None else load_fixture_transfers()
    alerts = []
    for t in transfers:
        from_tag = tag_address(t.from_addr, known)
        to_tag = tag_address(t.to_addr, known)
        direction = classify_direction(from_tag, to_tag)
        alerts.append(summarizer.build_alert(t, from_tag, to_tag, direction, source=source))
    return alerts


def demo_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")