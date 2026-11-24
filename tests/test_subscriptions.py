"""WatchPlan: one subscription-matching policy for scanning and delivery."""

from decimal import Decimal

from tests.conftest import BINANCE, USDT, WHALE
from whale_watch.model import Transfer
from whale_watch.subscriptions import Subscription, WatchPlan


def _transfer(token: str = "USDT", token_address: str = USDT) -> Transfer:
    return Transfer(
        tx_hash="0xabc",
        log_index=0,
        block=1,
        timestamp=None,
        token=token,
        token_address=token_address,
        from_addr=WHALE,
        to_addr=BINANCE,
        amount=Decimal(1000),
    )


def test_subscription_normalizes_address_and_token():
    rule = Subscription(1, WHALE.upper(), " usdt ")
    assert rule.address == WHALE
    assert rule.token == "USDT"
    assert Subscription(2, BINANCE).token == "*"


def test_wildcard_matches_sender_and_receiver():
    plan = WatchPlan((Subscription(1, WHALE), Subscription(2, BINANCE)))
    assert plan.matches(_transfer())
    assert plan.chats_for(_transfer()) == frozenset({1, 2})


def test_token_filters_route_chats_independently():
    plan = WatchPlan(
        (
            Subscription(1, WHALE, "USDT"),
            Subscription(2, BINANCE),
            Subscription(3, WHALE, "USDC"),
        )
    )
    assert plan.chats_for(_transfer()) == frozenset({1, 2})
    assert plan.chats_for(_transfer("USDC", "0x" + "2" * 40)) == frozenset({2, 3})


def test_token_contract_filter_matches_case_insensitively():
    contract = "0X" + USDT[2:].upper()
    plan = WatchPlan((Subscription(1, WHALE, contract),))
    assert plan.matches(_transfer("different symbol", USDT))
    assert not plan.matches(_transfer("USDC", "0x" + "2" * 40))


def test_unwatched_address_never_matches():
    plan = WatchPlan((Subscription(1, "0x" + "9" * 40),))
    assert not plan.matches(_transfer())
    assert plan.chats_for(_transfer()) == frozenset()


def test_empty_plan_has_no_matches_or_recipients():
    plan = WatchPlan(())
    assert not plan
    assert not plan.matches(_transfer())
    assert plan.chats_for(_transfer()) == frozenset()
