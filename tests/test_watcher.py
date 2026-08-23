"""The scanner: cursor safety, idempotence, early filtering, decoding."""

from decimal import Decimal

import pytest

from tests.conftest import BINANCE, TRANSFER_TOPIC, USDT, WHALE, FakeProvider, raw_log, topic_addr
from whale_watch.watcher import EventScanner, ScanError, Web3Provider


def _tokens() -> dict:
    return {USDT: {"symbol": "USDT", "decimals": 6}}


def _usdt_logs(block: int, amount_raw: int, sender: str = WHALE, to: str = BINANCE, tx: str | None = None) -> list[dict]:
    return [
        raw_log(
            tx or f"0x{block:064x}", 0, block, USDT,
            [TRANSFER_TOPIC, topic_addr(sender), topic_addr(to)],
            hex(amount_raw),
        )
    ]


def test_decode_applies_decimals(storage):
    scanner = EventScanner(storage, FakeProvider([], 1), _tokens(), start_block=0)
    logs = _usdt_logs(100, 45_200_000 * 10**6)  # 45.2M USDT raw
    t = scanner._decode(logs[0], "USDT", 6, USDT)
    assert t.amount == Decimal(45200000)
    assert t.from_addr == WHALE
    assert t.to_addr == BINANCE
    assert t.token == "USDT"


def test_scan_filters_to_watched_addresses(storage):
    storage.add_subscription(1, WHALE)  # watch the sender
    provider = FakeProvider(_usdt_logs(20, 10**6), latest=25)
    scanner = EventScanner(storage, provider, _tokens(), start_block=10, batch_size=5)
    result = scanner.scan_once()
    assert result.new_events == 1
    assert [t.from_addr for t in result.alerts] == [WHALE]
    assert result.cursor == 25


def test_unwatched_transfers_produce_no_events(storage):
    # Nobody watches WHALE's address — the log must be dropped before decode cost.
    provider = FakeProvider(_usdt_logs(20, 10**6), latest=25)
    scanner = EventScanner(storage, provider, _tokens(), start_block=10)
    result = scanner.scan_once()
    assert result.new_events == 0
    assert result.alerts == []
    assert storage.counts()["events"] == 0


def test_cursor_resume_is_contiguous_and_idempotent(storage):
    storage.add_subscription(1, WHALE)
    rows = _usdt_logs(11, 10**6, tx="0x1") + _usdt_logs(12, 10**6, tx="0x2") + _usdt_logs(13, 10**6, tx="0x3")
    provider = FakeProvider(rows, latest=13)
    scanner = EventScanner(storage, provider, _tokens(), start_block=10, batch_size=1)

    first = scanner.scan_once()
    assert first.new_events == 3
    assert provider.requests == [(11, 11, USDT), (12, 12, USDT), (13, 13, USDT)]

    second = scanner.scan_once()  # same range again — no dupes, no work
    assert second.new_events == 0
    assert second.scanned_blocks == 0
    assert storage.counts()["events"] == 3


def test_scan_crash_never_skips_blocks(storage):
    storage.add_subscription(1, WHALE)
    rows = _usdt_logs(11, 10**6, tx="0x1") + _usdt_logs(12, 10**6, tx="0x2") + _usdt_logs(13, 10**6, tx="0x3")

    class FlakyProvider(FakeProvider):
        def __init__(self, rows, latest):
            super().__init__(rows, latest)
            self.calls = 0

        def get_logs(self, from_block, to_block, address, topics):
            self.calls += 1
            if self.calls == 3:  # "crash" on the third batch
                raise ScanError("RPC exploded")
            return super().get_logs(from_block, to_block, address, topics)

    provider = FlakyProvider(rows, latest=13)
    scanner = EventScanner(storage, provider, _tokens(), start_block=10, batch_size=1)
    with pytest.raises(ScanError):
        scanner.scan_once()
    # The two completed batches are persisted; the crash did not lose the cursor.
    assert storage.get_cursor("ethereum") == 12
    assert storage.counts()["events"] == 2

    recovered = EventScanner(storage, provider, _tokens(), start_block=10, batch_size=1)
    result = recovered.scan_once()
    assert result.new_events == 1  # only block 13 — no re-alerts of 11-12
    assert result.cursor == 13
    assert storage.counts()["events"] == 3


def test_no_watched_addresses_short_circuits(storage):
    provider = FakeProvider(_usdt_logs(20, 10**6), latest=25)
    scanner = EventScanner(storage, provider, _tokens(), start_block=10)
    result = scanner.scan_once()
    assert result.scanned_blocks == 0
    assert provider.requests == []  # no RPC calls at all


def test_zero_address_sender_is_skipped(storage):
    storage.add_subscription(1, "0x" + "0" * 40)  # nobody can be the zero address
    logs = _usdt_logs(20, 10**6, sender="0x" + "0" * 40)
    provider = FakeProvider(logs, latest=25)
    scanner = EventScanner(storage, provider, _tokens(), start_block=10)
    result = scanner.scan_once()
    assert result.new_events == 0


def test_web3_provider_against_public_rpc():
    """Offline by default. Set WHALE_WATCH_LIVE=1 to smoke-test the public RPC."""
    import os

    if not os.environ.get("WHALE_WATCH_LIVE"):
        pytest.skip("offline by default — export WHALE_WATCH_LIVE=1 for the live RPC smoke test")
    provider = Web3Provider("https://ethereum-rpc.publicnode.com")
    assert provider.get_block_number() > 18_000_000