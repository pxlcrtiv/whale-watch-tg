"""The standalone alert preview page."""

from whale_watch.fixtures import run_fixture_demo
from whale_watch.preview import render_preview


def test_preview_page_renders_all_alerts(tmp_path, fixtures):
    alerts = run_fixture_demo(fixtures)
    out = render_preview(alerts, tmp_path / "preview.html")
    assert out.exists() and out.stat().st_size > 2000
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "whale-watch-tg — alert preview" in html
    assert "Binance" in html
    assert "demo fixture" in html
    for a in alerts:
        assert a.transfer.token in html


def test_preview_contains_no_unrendered_placeholders(tmp_path, fixtures):
    alerts = run_fixture_demo(fixtures)
    out = render_preview(alerts, tmp_path / "preview.html")
    html = out.read_text(encoding="utf-8")
    assert "None" not in html
    assert "{alert" not in html


def test_preview_escapes_user_data(tmp_path, fixtures):
    from decimal import Decimal

    from whale_watch.model import Transfer

    evil = Transfer(
        tx_hash="0x" + "e" * 64, log_index=0, block=1, timestamp=None,
        token='<script>alert(1)</script>', token_address="0x" + "1" * 40,
        from_addr="0x" + "2" * 40, to_addr="0x" + "3" * 40, amount=Decimal(1),
    )
    from whale_watch.summarizer import Summarizer

    alerts = [Summarizer().build_alert(evil, None, ("<b>X</b>", "exchange"), "to_exchange", source="fixture")]
    out = render_preview(alerts, tmp_path / "preview.html")
    html = out.read_text(encoding="utf-8")
    assert "<script>" not in html
    assert "&lt;b&gt;" in html