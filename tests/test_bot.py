"""Bot handlers: subscription CRUD through mocked telegram update/context."""

import asyncio

from tests.conftest import BINANCE
from whale_watch.bot import (
    ADDRESS_RE,
    HELP,
    WELCOME,
    build_application,
    cmd_list,
    cmd_status,
    cmd_subscribe,
    cmd_unsubscribe,
)


class FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, parse_mode=None):
        self.replies.append(text)
        return True


class FakeUpdate:
    def __init__(self, message=None, chat_id=42, user_id=7):
        self.message = message or FakeMessage()
        self.effective_chat = type("C", (), {"id": chat_id})()
        self.effective_user = type("U", (), {"id": user_id})()


class FakeContext:
    def __init__(self, storage, args=None):
        self.args = args or []
        self.bot_data = {"storage": storage}


def _run(coro):
    return asyncio.run(coro)


def test_address_regex_validates():
    assert ADDRESS_RE.match(BINANCE)
    assert ADDRESS_RE.match(BINANCE.upper())
    assert not ADDRESS_RE.match("0x123")
    assert not ADDRESS_RE.match(BINANCE + "ff")
    assert not ADDRESS_RE.match("nope")


def test_subscribe_adds_row(storage):
    msg = FakeMessage()
    _run(cmd_subscribe(FakeUpdate(msg), FakeContext(storage, args=[BINANCE, "USDT"])))
    assert storage.list_subscriptions(42)[0]["address"] == BINANCE
    assert msg.replies[0].startswith("✅")


def test_subscribe_rejects_bad_address(storage):
    msg = FakeMessage()
    _run(cmd_subscribe(FakeUpdate(msg), FakeContext(storage, args=["0xshort"])))
    assert storage.list_subscriptions(42) == []
    assert msg.replies[0].startswith("❌")


def test_unsubscribe_removes_row(storage):
    storage.add_subscription(42, BINANCE)
    msg = FakeMessage()
    _run(cmd_unsubscribe(FakeUpdate(msg), FakeContext(storage, args=[BINANCE])))
    assert storage.list_subscriptions(42) == []
    assert msg.replies[0] == "🗑 Stopped watching."


def test_list_shows_subscriptions(storage):
    storage.add_subscription(42, BINANCE)
    msg = FakeMessage()
    _run(cmd_list(FakeUpdate(msg), FakeContext(storage)))
    assert "Watching" in msg.replies[0] and BINANCE in msg.replies[0]


def test_status_reports_counts(storage):
    storage.add_subscription(42, BINANCE)
    msg = FakeMessage()
    _run(cmd_status(FakeUpdate(msg), FakeContext(storage)))
    assert "subscriptions: 1" in msg.replies[0]


def test_application_registers_six_handlers():
    app = build_application("123:TEST", ":memory:", storage=__import__("whale_watch.storage", fromlist=["Storage"]).Storage(":memory:"))
    handlers = app.handlers[0]
    from telegram.ext import CommandHandler

    assert len(handlers) == 6
    assert all(isinstance(h, CommandHandler) for h in handlers)
    commands = []
    for h in handlers:
        commands.extend(h.commands)
    assert commands == ["start", "help", "subscribe", "unsubscribe", "list", "status"]


def test_welcome_and_help_are_informative():
    assert "subscribe" in WELCOME.lower() and "not trading advice" in WELCOME
    assert "/subscribe" in HELP and "/list" in HELP