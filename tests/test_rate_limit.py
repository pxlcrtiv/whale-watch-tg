"""Anti-spam gates: hourly cap + minimum gap between alerts per chat."""

from decimal import Decimal

from whale_watch.model import Transfer


def _t(block: int) -> Transfer:
    return Transfer(
        tx_hash=f"0x{block:064x}", log_index=0, block=block, timestamp=block,
        token="USDT", token_address="0x" + "1" * 40,
        from_addr="0x" + "2" * 40, to_addr="0x" + "3" * 40, amount=Decimal(1),
    )


def test_hourly_cap_enforced(storage):
    t0 = 1_000_000
    for i in range(10):  # fill the hourly budget (max 10/h)
        assert storage.alert_allowed(1, now=t0 + i * 10)[0] is True
        storage.record_alert(1, _t(i), now=t0 + i * 10)
    ok, reason = storage.alert_allowed(1, now=t0 + 100)
    assert ok is False
    assert "hourly limit" in reason


def test_min_gap_enforced(storage):
    assert storage.alert_allowed(1, now=5_000)[0] is True
    storage.record_alert(1, _t(1), now=5_000)
    ok, reason = storage.alert_allowed(1, now=5_002)  # 2s < 5s gap
    assert ok is False
    assert "rate-limited" in reason
    # after the gap elapses, allowed again
    assert storage.alert_allowed(1, now=5_006)[0] is True


def test_window_rolls_over(storage):
    now = 1_000_000
    for i in range(10):
        storage.record_alert(1, _t(i), now=now - 3700 + i)  # 1h+ ago
    assert storage.alert_allowed(1, now=now)[0] is True  # old alerts don't count


def test_limits_are_per_chat(storage):
    for i in range(10):
        storage.record_alert(1, _t(i), now=5_000 + i)
    assert storage.alert_allowed(2, now=5_100)[0] is True  # other chat unaffected