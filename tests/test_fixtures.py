"""Bundled fixture data sanity: the demo corpus must be self-consistent."""

import json
from decimal import Decimal
from pathlib import Path

from whale_watch.enrich import load_known_addresses

FIXTURES = Path(__file__).resolve().parent.parent / "whale_watch" / "data" / "fixtures" / "transfers.json"
TOKENS = Path(__file__).resolve().parent.parent / "whale_watch" / "data" / "tokens.json"


def test_eight_fixture_transfers_load(fixtures):
    assert len(fixtures) == 8
    assert len({t.tx_hash for t in fixtures}) == 8  # unique hashes
    for t in fixtures:
        assert t.amount > Decimal(0)
        assert t.tx_hash.startswith("0x") and len(t.tx_hash) == 66
        assert t.from_addr.startswith("0x") and t.to_addr.startswith("0x")


def test_fixture_exchange_addresses_are_tagged(fixtures):
    known = load_known_addresses()
    tagged = [t for t in fixtures if t.to_addr in known or t.from_addr in known]
    assert len(tagged) >= 6  # the demo headline requires exchange tagging
    # The headline demo transfer: 3,000 ETH -> Binance
    eth_to_binance = [t for t in fixtures if t.token == "ETH" and t.to_addr in known and known[t.to_addr]["name"] == "Binance"]
    assert eth_to_binance, "demo needs an ETH->Binance fixture"
    assert eth_to_binance[0].amount == Decimal(3000)


def test_fixture_token_addresses_exist_in_token_map(fixtures):
    tokens = json.loads(TOKENS.read_text(encoding="utf-8"))["ethereum"]
    for t in fixtures:
        if t.token != "ETH":  # native ETH is the zero address, not an ERC-20 map entry
            assert t.token_address.lower() in {k.lower() for k in tokens}, f"unknown token address for {t.token}"


def test_fixture_usd_values_are_plausible(fixtures):
    for t in fixtures:
        assert t.value_usd is not None and t.value_usd > 0
        # sanity: USD not off by orders of magnitude from the token's market range
        assert Decimal(0) < t.value_usd < Decimal(1_000_000_000)