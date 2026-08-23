"""Shared test fixtures: temp storage, fixture transfers, fake RPC provider."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whale_watch.fixtures import load_fixture_transfers
from whale_watch.storage import Storage


@pytest.fixture
def storage(tmp_path):
    s = Storage(tmp_path / "test.db", max_alerts_per_hour=10, min_alert_gap_seconds=5)
    yield s
    s.close()


@pytest.fixture
def fixtures():
    """The bundled demo transfers."""
    return load_fixture_transfers()


class FakeProvider:
    """Scripted RPC: returns the rows whose block falls in the requested range."""

    def __init__(self, rows, latest: int) -> None:
        self.rows = rows
        self.latest = latest
        self.requests: list[tuple[int, int, str]] = []

    def get_block_number(self) -> int:
        return self.latest

    def get_logs(self, from_block: int, to_block: int, address: str, topics: list[str]) -> list[dict]:
        self.requests.append((from_block, to_block, address))
        return [
            r for r in self.rows
            if r["address"].lower() == address.lower()
            and from_block <= int(r["blockNumber"], 16) <= to_block
        ]


def raw_log(tx_hash: str, log_index: int, block: int, address: str, topics: list[str], data: str) -> dict:
    return {
        "transactionHash": tx_hash,
        "logIndex": hex(log_index),
        "blockNumber": hex(block),
        "address": address,
        "topics": topics,
        "data": data,
    }


TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
BINANCE = "0x28c6c06298d514db089934071355e5743bf21d60"
COINBASE = "0x71660c4005ba85c37ccec55d0c4493e66fe775d3"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
WHALE = "0x8a355f524215e5fb13e5e35d1c5f63f2d0d1b4f2"


def topic_addr(addr: str) -> str:
    return "0x" + "0" * 24 + addr[2:].lower()