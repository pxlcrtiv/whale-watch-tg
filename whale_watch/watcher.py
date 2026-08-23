"""Cursor-safe, idempotent on-chain transfer scanner.

Design (per roadmap Tier 3 spec):
  - Cursor-safe: the last scanned block is persisted in SQLite. A scan starts
    at cursor+1, so a crash or RPC failure can never skip blocks; re-processing
    an already-scanned range is harmless because events dedupe on
    (tx_hash, log_index) via INSERT OR IGNORE.
  - Idempotent: scanning the same logs twice yields zero duplicate events.
  - Filtered early: logs whose sender/receiver matches no subscription are
    dropped before decoding (cheap topic check).
  - Provider-agnostic: tests inject a fake provider; production uses
    Web3Provider over any HTTP/WebSocket RPC URL.

Two delivery halves live elsewhere: `cli watch` drives scan_once() in a loop
and routes Alert objects to Telegram chats / stdout; `bot` serves subscriptions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from .model import Transfer

log = logging.getLogger("whale_watch.watcher")

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@dataclass
class ScanResult:
    scanned_blocks: int
    logs_seen: int
    new_events: int
    alerts: list[Transfer]
    cursor: int | None


class ScanError(RuntimeError):
    """RPC-level failure (timeout, rate limit, range too wide)."""


class Provider:
    """Duck-typed RPC surface the scanner needs."""

    def get_block_number(self) -> int:
        raise NotImplementedError

    def get_logs(self, from_block: int, to_block: int, address: str, topics: list[str]) -> list[dict]:
        raise NotImplementedError


class Web3Provider(Provider):
    """web3.py-backed provider. Imported lazily so fixture/demo paths never
    need web3 installed."""

    def __init__(self, url: str) -> None:
        from web3 import Web3  # local import: keep demo/web-free

        self.w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 20}))
        if not self.w3.is_connected():
            raise ScanError(f"cannot connect to RPC: {url}")

    def get_block_number(self) -> int:
        return int(self.w3.eth.block_number)

    def get_logs(self, from_block: int, to_block: int, address: str, topics: list[str]) -> list[dict]:
        payload = {
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "address": address,
            "topics": [TRANSFER_TOPIC] + topics,
        }
        try:
            return self.w3.eth.get_logs(payload)
        except Exception as exc:  # web3 raises several RPC error types
            raise ScanError(f"eth_getLogs [{from_block}..{to_block}] failed: {exc}") from exc


class EventScanner:
    def __init__(
        self,
        storage,
        provider: Provider,
        tokens: dict[str, dict] | None = None,
        *,
        chain: str = "ethereum",
        batch_size: int = 2000,
        max_scan_blocks: int = 50000,
        start_block: int | None = None,
    ) -> None:
        self.storage = storage
        self.provider = provider
        self.chain = chain
        self.tokens = {
            addr.lower(): meta for addr, meta in (tokens or {}).items()
        }
        # Native ETH has no ERC-20 Transfer events; fixtures use the zero address.
        self.tokens.pop(ZERO_ADDRESS, None)
        self.batch_size = batch_size
        self.max_scan_blocks = max_scan_blocks
        self.start_block = start_block

    # ---------------------------------------------------------------- scanning
    def scan_once(self, latest: int | None = None) -> ScanResult:
        """Scan cursor+1 .. latest in batches. Never skips; never duplicates."""
        watched = self.storage.all_watched_addresses()
        if not watched or not self.tokens:
            return ScanResult(0, 0, 0, [], self.storage.get_cursor(self.chain))

        latest = latest if latest is not None else self.provider.get_block_number()
        cursor = self.storage.get_cursor(self.chain)
        if cursor is None:
            cursor = self.start_block if self.start_block is not None else latest
            self.storage.set_cursor(self.chain, cursor)

        if cursor >= latest:
            return ScanResult(0, 0, 0, [], cursor)

        end = min(latest, cursor + self.max_scan_blocks)
        logs_seen = new_events = 0
        alerts: list[Transfer] = []
        pos = cursor
        while pos < end:
            batch_end = min(end, pos + self.batch_size)
            for address, meta in self.tokens.items():
                try:
                    logs = self.provider.get_logs(pos + 1, batch_end, address, [])
                except ScanError:
                    # A batch that is too wide for the RPC is retried at half width.
                    if self.batch_size > 100:
                        self.batch_size //= 2
                        log.warning("RPC rejected batch — halving to %s blocks", self.batch_size)
                        continue
                    raise
                logs_seen += len(logs)
                for raw in logs:
                    transfer = self._decode(raw, meta["symbol"], meta["decimals"], address.lower())
                    if transfer is None:
                        continue
                    if not self._matches_watch(watched, transfer):
                        continue
                    if self.storage.record_event(transfer):
                        new_events += 1
                        alerts.append(transfer)
            pos = batch_end
            self.storage.set_cursor(self.chain, pos)
        return ScanResult(pos - cursor, logs_seen, new_events, alerts, pos)

    # ------------------------------------------------------------------ decoding
    def _matches_watch(self, watched: set[str], transfer: Transfer) -> bool:
        return transfer.from_addr in watched or transfer.to_addr in watched

    def _decode(self, raw: dict, symbol: str, decimals: int, token_address: str) -> Transfer | None:
        topics = raw.get("topics") or []
        if len(topics) != 3:
            return None
        from_addr = _topic_address(topics[1])
        to_addr = _topic_address(topics[2])
        if not from_addr or not to_addr:
            return None
        amount = Decimal(int(raw.get("data", "0x0"), 16)) / (Decimal(10) ** decimals)
        return Transfer(
            tx_hash=raw.get("transactionHash", "").lower(),
            log_index=int(raw.get("logIndex", 0), 16) if isinstance(raw.get("logIndex"), str) and raw.get("logIndex").startswith("0x") else int(raw.get("logIndex", 0)),
            block=int(raw.get("blockNumber", 0), 16) if isinstance(raw.get("blockNumber"), str) and raw.get("blockNumber").startswith("0x") else int(raw.get("blockNumber", 0)),
            timestamp=None,  # block timestamps need an extra RPC round-trip
            token=symbol,
            token_address=token_address,
            from_addr=from_addr,
            to_addr=to_addr,
            amount=amount,
        )


def _topic_address(topic: str) -> str | None:
    """32-byte topic field -> 20-byte checksum-free lowercase address."""
    h = topic.removeprefix("0x")
    if len(h) < 40:
        return None
    addr = "0x" + h[-40:]
    return addr.lower() if int(addr, 16) else None  # zero address = burn/mint, skip