"""Summarizer: LLM with deterministic template fallback + exact alert text."""

from decimal import Decimal

from tests.conftest import BINANCE, WHALE
from whale_watch.enrich import DIR_TO_EXCHANGE, classify_direction, tag_address
from whale_watch.model import Transfer
from whale_watch.summarizer import NARRATIVES, Summarizer, fmt_usd, rate_class_for


def _transfer(amount: str = "3000", usd: str = "7200000", token: str = "ETH", to: str = BINANCE) -> Transfer:
    return Transfer(
        tx_hash="0x" + "a" * 64, log_index=3, block=19_999_991,
        timestamp=1_755_000_000, token=token,
        token_address="0x" + "1" * 40,
        from_addr=WHALE, to_addr=to, amount=Decimal(amount),
        value_usd=Decimal(usd) if usd else None,
    )


def test_template_narratives_cover_all_directions():
    s = Summarizer()
    assert "sell pressure" in s._template_narrative(DIR_TO_EXCHANGE)
    assert "accumulation" in s._template_narrative("from_exchange")
    assert "Wallet-to-wallet" in s._template_narrative("p2p")
    assert "rebalancing" in s._template_narrative("internal")
    assert NARRATIVES[DIR_TO_EXCHANGE] == "Likely sell pressure: large inflow to a centralized exchange."


def test_unconfigured_llm_falls_back_to_template():
    s = Summarizer(llm_url="", llm_key="")  # not configured
    t = _transfer()
    from_tag = tag_address(t.from_addr)
    to_tag = tag_address(t.to_addr)
    text = s.narrative(t, from_tag, to_tag, classify_direction(from_tag, to_tag))
    assert "sell pressure" in text  # deterministic, no keys


def test_build_alert_produces_full_subscriber_text():
    s = Summarizer()
    t = _transfer()
    from_tag = tag_address(t.from_addr)
    to_tag = tag_address(t.to_addr)
    alert = s.build_alert(t, from_tag, to_tag, classify_direction(from_tag, to_tag), source="fixture")
    assert "3,000 ETH" in alert.summary
    assert "→ Binance" in alert.summary
    assert "Likely sell pressure" in alert.summary
    assert "19,999,991" in alert.summary
    assert "Demo fixture" in alert.summary
    assert "LARGE" in alert.summary and "$7.20M" in alert.summary
    assert alert.rate_class == "LARGE"
    assert alert.from_tag == "Binance" or alert.to_tag == "Binance"
    assert alert.source == "fixture"


def test_mega_and_watch_rate_classes():
    assert rate_class_for(Decimal(45200000)) == "MEGA MOVE"
    assert rate_class_for(Decimal(7200000)) == "LARGE"
    assert rate_class_for(Decimal(65000)) == "WATCH"
    assert rate_class_for(None) == "WATCH"


def test_usd_formatting():
    assert fmt_usd(Decimal(45200000)) == "$45.20M"
    assert fmt_usd(Decimal(7200000)) == "$7.20M"
    assert fmt_usd(Decimal(65000)) == "$65.0K"
    assert fmt_usd(Decimal("123.45")) == "$123.45"
    assert fmt_usd(Decimal(1_200_000_000)) == "$1.20B"
    assert fmt_usd(None) == "USD estimate unavailable"


def test_llm_configured_but_offline_degrades_to_template():
    s = Summarizer(llm_url="http://127.0.0.1:9/v1", llm_key="test", llm_model="m")  # nothing listens
    t = _transfer()
    text = s.narrative(t, None, ("Binance", "exchange"), DIR_TO_EXCHANGE)
    assert "sell pressure" in text  # call failed -> template, no crash