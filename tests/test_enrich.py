"""Address enrichment: known-address tagging and direction classification."""

from tests.conftest import BINANCE, WHALE
from whale_watch.enrich import (
    DIR_FROM_EXCHANGE,
    DIR_INTERNAL,
    DIR_P2P,
    DIR_TO_EXCHANGE,
    classify_direction,
    load_known_addresses,
    tag_address,
)


def test_known_exchange_is_tagged():
    tag = tag_address(BINANCE)
    assert tag == ("Binance", "exchange")


def test_unknown_address_is_none():
    assert tag_address(WHALE) is None
    assert tag_address("0x" + "9" * 40) is None


def test_tagging_is_case_insensitive():
    assert tag_address(BINANCE.upper()) == ("Binance", "exchange")


def test_direction_classification():
    exchange = ("Binance", "exchange")
    other_exchange = ("Coinbase", "exchange")
    assert classify_direction(None, exchange) == DIR_TO_EXCHANGE
    assert classify_direction(exchange, None) == DIR_FROM_EXCHANGE
    assert classify_direction(None, None) == DIR_P2P
    assert classify_direction(exchange, other_exchange) == DIR_P2P
    assert classify_direction(exchange, ("Binance", "exchange")) == DIR_INTERNAL  # hot->cold
    assert classify_direction(("Uniswap V2 Router", "dex"), exchange) == DIR_TO_EXCHANGE


def test_bundled_list_loads_with_all_required_fields():
    known = load_known_addresses()
    assert len(known) >= 15
    for addr, meta in known.items():
        assert addr.startswith("0x") and len(addr) == 42
        assert meta["name"] and meta["kind"] in ("exchange", "dex", "treasury", "staking", "burn")