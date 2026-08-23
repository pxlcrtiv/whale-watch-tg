"""Storage: subscriptions, event dedupe, cursor — the idempotence backbone."""

from tests.conftest import BINANCE, WHALE
from whale_watch.model import Transfer
from whale_watch.storage import utc_now

ADDR_A = "0x28c6c06298d514db089934071355e5743bf21d60"


def _t(block: int, tx: str = "0xaaaa", li: int = 0) -> Transfer:
    return Transfer(
        tx_hash=tx, log_index=li, block=block, timestamp=None,
        token="USDT", token_address="0x" + "1" * 40,
        from_addr=WHALE, to_addr=BINANCE, amount=__import__("decimal").Decimal("1000"),
    )


def test_subscribe_unsubscribe_roundtrip(storage):
    assert storage.add_subscription(1, ADDR_A) is True
    assert storage.add_subscription(1, ADDR_A) is False  # idempotent
    assert storage.add_subscription(1, "0x" + "2" * 40) is True
    subs = storage.list_subscriptions(1)
    assert len(subs) == 2
    assert subs[0]["address"] == ADDR_A  # ordered by created_at
    assert subs[0]["token"] == "*"

    assert storage.remove_subscription(1, ADDR_A) is True
    assert storage.remove_subscription(1, ADDR_A) is False
    assert len(storage.list_subscriptions(1)) == 1


def test_watched_addresses_and_chat_routing(storage):
    storage.add_subscription(7, ADDR_A)
    storage.add_subscription(9, ADDR_A)
    storage.add_subscription(7, "0x" + "3" * 40)
    assert storage.all_watched_addresses() == {ADDR_A, "0x" + "3" * 40}
    assert sorted(storage.chats_for_address(ADDR_A)) == [7, 9]


def test_event_dedupe_on_tx_log_pair(storage):
    t1 = _t(100)
    t2 = _t(101, tx="0xbbbb")
    assert storage.record_event(t1) is True
    assert storage.record_event(t1) is False          # same (tx, log_index) — dup
    assert storage.record_event(t2) is True
    assert storage.counts()["events"] == 2
    assert storage.has_event("0xaaaa", 0) is True
    assert storage.has_event("0xcc", 0) is False


def test_cursor_save_and_load(storage):
    assert storage.get_cursor("ethereum") is None
    storage.set_cursor("ethereum", 19_999_991)
    assert storage.get_cursor("ethereum") == 19_999_991
    storage.set_cursor("ethereum", 19_999_995)  # overwrite
    assert storage.get_cursor("ethereum") == 19_999_995
    assert storage.counts()["cursors"]["ethereum"] == 19_999_995


def test_alert_seen_tracking(storage):
    t = _t(100)
    storage.record_alert(1, t, now=utc_now())
    assert storage.alert_seen(1, t) is True
    assert storage.alert_seen(2, t) is False


def test_case_insensitive_addresses(storage):
    storage.add_subscription(1, ADDR_A.upper())
    assert storage.list_subscriptions(1)[0]["address"] == ADDR_A
    assert storage.all_watched_addresses() == {ADDR_A}