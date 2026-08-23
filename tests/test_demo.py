"""The zero-key demo: fixture transfers -> enriched, summarized alerts."""

from whale_watch.enrich import DIR_TO_EXCHANGE
from whale_watch.fixtures import run_fixture_demo


def test_demo_produces_all_alerts(fixtures):
    alerts = run_fixture_demo(fixtures)
    assert len(alerts) == len(fixtures)
    assert all(a.source == "fixture" for a in alerts)
    assert all(a.summary for a in alerts)


def test_demo_headline_alert_is_sell_pressure(fixtures):
    alerts = run_fixture_demo(fixtures)
    first = alerts[0]
    assert first.direction == DIR_TO_EXCHANGE
    assert first.to_tag == "Binance"
    assert "3,000 ETH" in first.summary
    assert "Binance" in first.summary
    assert "sell pressure" in first.summary


def test_demo_mixes_direction_classes(fixtures):
    alerts = run_fixture_demo(fixtures)
    directions = {a.direction for a in alerts}
    assert DIR_TO_EXCHANGE in directions
    assert "from_exchange" in directions  # e.g. WBTC out of Coinbase
    assert "p2p" in directions            # e.g. the SHIB transfer


def test_demo_is_deterministic(fixtures):
    a1 = run_fixture_demo(fixtures)
    a2 = run_fixture_demo(fixtures)
    assert [a.summary for a in a1] == [a.summary for a in a2]