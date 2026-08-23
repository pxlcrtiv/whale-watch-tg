"""whale-watch — command-line entry point.

  whale-watch demo                  keyless demo: fixture transfers -> rendered
                                    alerts in the terminal + examples/preview.html
  whale-watch watch                 live cursor-safe scan loop (public RPC)
  whale-watch bot                   Telegram bot (TELEGRAM_BOT_TOKEN required)
  whale-watch preview               regenerate the preview page from fixtures
  whale-watch status                SQLite store summary

Demo path needs zero keys, zero network and (by design) never imports web3 or
python-telegram-bot — the "live" paths pull those in lazily.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import DEFAULT_RPC_URL, DEMO_CHAT_ID
from .enrich import load_known_addresses, load_tokens
from .fixtures import load_fixture_transfers, run_fixture_demo
from .preview import render_preview
from .storage import Storage

PREVIEW_DEFAULT = Path("examples/whale-alert-preview.html")
DB_DEFAULT = Path("whale-watch.sqlite3")

log = logging.getLogger("whale_watch.cli")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


# ----------------------------------------------------------------------- demo
def cmd_demo(args: argparse.Namespace) -> int:
    transfers = load_fixture_transfers(args.fixtures) if args.fixtures else load_fixture_transfers()
    alerts = run_fixture_demo(transfers)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    print("=" * 64)
    print("🐋 whale-watch-tg — zero-key demo")
    print(f"   {len(transfers)} bundled fixture transfers · {stamp}")
    print("   enrich → summarize → render · same pipeline as live mode")
    print("=" * 64)
    for i, alert in enumerate(alerts, 1):
        print()
        print(f"--- alert {i}/{len(alerts)} · {alert.rate_class} · demo chat #{DEMO_CHAT_ID} ---")
        print(alert.summary)
        print()

    print("-" * 64)
    print("Summary: exchange inflow heuristic active; LLM backend NOT configured")
    print("         (set WHALE_WATCH_LLM_URL/KEY for AI narratives — template used here).")

    out = render_preview(alerts, args.out)
    print(f"✅ Web preview written: {out}")
    print(f"   open it:   open {out}")
    print(f"   or serve:  python3 -m http.server 8000 --directory {out.parent}")
    print("   start live scan with: whale-watch watch  (public RPC, zero keys)")
    return 0


# ---------------------------------------------------------------------- watch
def cmd_watch(args: argparse.Namespace) -> int:
    from .enrich import classify_direction, tag_address
    from .summarizer import Summarizer
    from .watcher import EventScanner, ScanError, Web3Provider

    storage = Storage(args.db)
    known = load_known_addresses()
    tokens = load_tokens().get("ethereum", {})
    if args.console_subscribe:
        for addr in args.console_subscribe:
            storage.add_subscription(DEMO_CHAT_ID, addr)
    if not storage.all_watched_addresses():
        print("No subscriptions yet — watching Binance hot wallet by default.")
        print("Add more with `whale-watch watch --subscribe 0x…` or via the bot.")
        storage.add_subscription(DEMO_CHAT_ID, "0x28c6c06298d514db089934071355e5743bf21d60")

    app = None
    if args.send_telegram:
        from .bot import build_application, token_from_env

        token = token_from_env()
        if not token:
            print("ERROR: --send-telegram needs TELEGRAM_BOT_TOKEN (see README).")
            return 2
        app = build_application(token, storage.db_path)  # delivery-only, no polling

    provider = Web3Provider(args.rpc)
    summ = Summarizer()
    scanner = EventScanner(storage, provider, tokens, chain="ethereum", batch_size=args.batch)
    print(f"Scanning ethereum via {args.rpc} every {args.interval}s "
          f"(batch {args.batch} blocks) — Ctrl-C to stop.")
    while True:
        try:
            result = scanner.scan_once()
        except ScanError as exc:
            print(f"⚠ scan error (will retry in {args.interval}s): {exc}")
            time.sleep(args.interval)
            continue
        if result.scanned_blocks:
            print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] scanned "
                  f"{result.scanned_blocks} blocks · {result.logs_seen} logs · "
                  f"{result.new_events} new event(s) · cursor {result.cursor}")
        for transfer in result.alerts:
            from_tag = tag_address(transfer.from_addr, known)
            to_tag = tag_address(transfer.to_addr, known)
            alert = summ.build_alert(
                transfer, from_tag, to_tag, classify_direction(from_tag, to_tag)
            )
            _deliver(storage, app, transfer, alert.summary)
        time.sleep(args.interval)


def _deliver(storage: Storage, app, transfer, text: str) -> None:
    """Route an alert to every subscribed chat (or the console demo chat)."""
    chats = storage.chats_for_address(transfer.from_addr) + storage.chats_for_address(transfer.to_addr)
    chats = sorted(set(chats))
    for chat in chats:
        ok, reason = storage.alert_allowed(chat)
        if not ok:
            print(f"⏳ chat {chat}: skipped — {reason}")
            continue
        if app is not None:
            from .bot import send_alert

            send_alert(app, chat, text)
            storage.record_alert(chat, transfer)
        else:
            print(f"\n→ chat {chat}\n{text}\n")
            storage.record_alert(chat, transfer)


# ------------------------------------------------------------------------ bot
def cmd_bot(args: argparse.Namespace) -> int:
    from .bot import run_bot, token_from_env

    token = args.token or token_from_env()
    if not token:
        print("ERROR: no Telegram bot token.")
        print("  Create one with @BotFather, then export TELEGRAM_BOT_TOKEN=…")
        print("  (or pass --token). The demo does NOT need this.")
        return 2
    run_bot(token, args.db)
    return 0


# -------------------------------------------------------------------- preview
def cmd_preview(args: argparse.Namespace) -> int:
    alerts = run_fixture_demo(load_fixture_transfers(args.fixtures) if args.fixtures else load_fixture_transfers())
    out = render_preview(alerts, args.out)
    print(f"Preview page written: {out} ({len(alerts)} alerts)")
    return 0


# --------------------------------------------------------------------- status
def cmd_status(args: argparse.Namespace) -> int:
    storage = Storage(args.db)
    counts = storage.counts()
    print(f"db:              {args.db}")
    print(f"subscriptions:   {counts['subscriptions']}")
    print(f"events:          {counts['events']}")
    print(f"alerts:          {counts['alerts']}")
    for chain, block in counts["cursors"].items():
        print(f"cursor {chain}:   {block}")
    if not counts["cursors"]:
        print("cursor:          not started")
    subs = storage.list_subscriptions()
    if subs:
        print("\nsubscriptions:")
        for s in subs:
            print(f"  chat {s['chat_id']:<10} {s['address']}  {s['token']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="whale-watch",
        description="Telegram whale tracker with AI summaries — subscribe to any "
        "wallet, get alerts like '3,000 ETH to Binance — likely sell pressure'.",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")

    sub = p.add_subparsers(dest="command", required=True)

    def _db(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--db", default=str(DB_DEFAULT), help="SQLite store path")

    d = sub.add_parser("demo", help="zero-key demo from bundled fixture transfers")
    _db(d)
    d.add_argument("--out", default=str(PREVIEW_DEFAULT), help="preview page output path")
    d.add_argument("--fixtures", default=None, help="alternative fixtures JSON")
    d.set_defaults(func=cmd_demo)

    w = sub.add_parser("watch", help="live cursor-safe scan loop (public RPC, zero keys)")
    _db(w)
    w.add_argument("--rpc", default=DEFAULT_RPC_URL, help="Ethereum RPC URL")
    w.add_argument("--interval", type=float, default=12.0, help="poll interval seconds")
    w.add_argument("--batch", type=int, default=2000, help="blocks per eth_getLogs call")
    w.add_argument("--subscribe", action="append", dest="console_subscribe",
                   help="address to subscribe (console chat); repeatable")
    w.add_argument("--send-telegram", action="store_true",
                   help="deliver alerts via Telegram (needs TELEGRAM_BOT_TOKEN)")
    w.set_defaults(func=cmd_watch)

    b = sub.add_parser("bot", help="run the Telegram bot (TELEGRAM_BOT_TOKEN required)")
    _db(b)
    b.add_argument("--token", default=None, help="bot token (else TELEGRAM_BOT_TOKEN env)")
    b.set_defaults(func=cmd_bot)

    pr = sub.add_parser("preview", help="regenerate the alert preview page from fixtures")
    _db(pr)
    pr.add_argument("--out", default=str(PREVIEW_DEFAULT))
    pr.add_argument("--fixtures", default=None)
    pr.set_defaults(func=cmd_preview)

    s = sub.add_parser("status", help="show subscription/event/cursor counts")
    _db(s)
    s.set_defaults(func=cmd_status)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nbye 👋")
        return 0


if __name__ == "__main__":
    sys.exit(main())