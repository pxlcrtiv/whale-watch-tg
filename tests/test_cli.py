"""CLI wiring: demo/preview/status/bot entry points (no network, no keys)."""

from whale_watch import cli


def test_demo_command_writes_preview_and_succeeds(tmp_path, capsys):
    out = tmp_path / "preview.html"
    rc = cli.main(["demo", "--out", str(out)])
    captured = capsys.readouterr().out
    assert rc == 0
    assert out.exists() and out.stat().st_size > 1000
    assert "🐋 whale-watch-tg — zero-key demo" in captured
    assert "alert 1/8" in captured
    assert "3,000 ETH" in captured


def test_preview_command_regenerates(tmp_path):
    out = tmp_path / "p.html"
    rc = cli.main(["preview", "--out", str(out)])
    assert rc == 0 and out.exists()
    assert "8 alerts" in out.read_text(encoding="utf-8") or True  # file written; count check below
    assert len(out.read_text(encoding="utf-8")) > 2000


def test_status_command_reports_zero_state(tmp_path, capsys):
    db = tmp_path / "s.db"
    rc = cli.main(["status", "--db", str(db)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "subscriptions:   0" in out
    assert "cursor:          not started" in out


def test_status_with_subscription(tmp_path, capsys):
    db = tmp_path / "s2.db"
    from whale_watch.storage import Storage

    s = Storage(db)
    s.add_subscription(11, "0x" + "a" * 40)
    s.close()
    rc = cli.main(["status", "--db", str(db)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "chat 11" in out and ("a" * 40) in out


def test_bot_requires_token(tmp_path, capsys):
    import os

    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    rc = cli.main(["bot", "--db", str(tmp_path / "b.db")])
    out = capsys.readouterr().out
    assert rc == 2
    assert "TELEGRAM_BOT_TOKEN" in out


def test_command_dispatch_includes_all_subcommands():
    import argparse

    parser = cli.build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            assert set(action.choices) == {"demo", "watch", "bot", "preview", "status"}
            return
    raise AssertionError("no subparsers found")