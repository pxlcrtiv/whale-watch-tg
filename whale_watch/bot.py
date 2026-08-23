"""Telegram bot skeleton — python-telegram-bot 20.x+ Application.

Commands:
  /start                  welcome + quickstart
  /subscribe <address>    watch a wallet (optionally: <address> <TOKEN>)
  /unsubscribe <address>  stop watching
  /list                   your subscriptions
  /status                 watcher health (cursor, event counts)
  /help                   usage

The bot is the *delivery* half: it serves subscription CRUD here and has a
send_alert() helper so the watcher loop (`whale-watch watch --send-telegram`)
can push alerts to every chat subscribed to an address. Spam control lives in
Storage (hourly cap + min gap) plus a per-user command cooldown below.

Requires TELEGRAM_BOT_TOKEN — run `whale-watch bot` (see README). No token is
ever required for the demo path.
"""

from __future__ import annotations

import logging
import os
import re
import time

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .storage import Storage

log = logging.getLogger("whale_watch.bot")

ADDRESS_RE = re.compile(r"^0[xX][a-fA-F0-9]{40}$")
TOKEN_RE = re.compile(r"^[A-Z0-9*]{2,12}$")

WELCOME = (
    "🐋 *whale-watch-tg*\n\n"
    "I watch Ethereum wallets for you and summarize every big move — "
    "`\"3,000 ETH to Binance — likely sell pressure\"`.\n\n"
    "*Try:*\n"
    "`/subscribe 0x28c6c06298d514db089934071355e5743bf21d60`  — watch Binance's hot wallet\n"
    "`/list` · `/unsubscribe <address>` · `/status`\n\n"
    "Demo (no keys needed): run `whale-watch demo` in the repo. "
    "*Informational only — not trading advice.*"
)

HELP = (
    "*Usage*\n"
    "`/subscribe <address> [TOKEN]` — start watching an address (TOKEN optional: USDT, ETH, WBTC, … or `*`)\n"
    "`/unsubscribe <address>` — stop watching\n"
    "`/list` — your subscriptions\n"
    "`/status` — watcher health\n"
    "`/help` — this message"
)

# Per-user command cooldown (anti-spam on the command side). State lives in
# app.bot_data["cmd_cooldowns"] so it is per-application, not process-global.
USER_COOLDOWN_SECONDS = 2.0


def _cooldown_ok(user_id: int, bot_data: dict) -> bool:
    cooldowns = bot_data.setdefault("cmd_cooldowns", {})
    now = time.monotonic()
    if now - cooldowns.get(user_id, 0.0) < USER_COOLDOWN_SECONDS:
        return False
    cooldowns[user_id] = now
    return True


def _storage_from_context(context: ContextTypes.DEFAULT_TYPE) -> Storage:
    return context.bot_data["storage"]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP, parse_mode="Markdown")


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _cooldown_ok(update.effective_user.id, context.bot_data):
        await update.message.reply_text("⏳ Slow down — one command every couple of seconds.")
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: `/subscribe 0x… <TOKEN>`", parse_mode="Markdown")
        return
    address = args[0].lower()
    if not ADDRESS_RE.match(address):
        await update.message.reply_text("❌ That doesn't look like a 40-char hex address (`0x…`).")
        return
    token = args[1].upper() if len(args) > 1 else "*"
    if not TOKEN_RE.match(token):
        await update.message.reply_text("❌ Token symbol must be `USDT`-style (or `*`).")
        return
    storage = _storage_from_context(context)
    new = storage.add_subscription(update.effective_chat.id, address, token)
    if new:
        await update.message.reply_text(f"✅ Watching `{address}` for `{token}` moves.", parse_mode="Markdown")
    else:
        await update.message.reply_text("👀 Already watching that address (updated token filter).")


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _cooldown_ok(update.effective_user.id, context.bot_data):
        await update.message.reply_text("⏳ Slow down — one command every couple of seconds.")
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: `/unsubscribe <address>`", parse_mode="Markdown")
        return
    storage = _storage_from_context(context)
    removed = storage.remove_subscription(update.effective_chat.id, args[0].lower())
    await update.message.reply_text("🗑 Stopped watching." if removed else "Wasn't watching that address.")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage = _storage_from_context(context)
    subs = storage.list_subscriptions(update.effective_chat.id)
    if not subs:
        await update.message.reply_text("No subscriptions yet. `/subscribe 0x…` to start.", parse_mode="Markdown")
        return
    lines = ["*Watching:*"]
    for s in subs:
        lines.append(f"`{s['address']}` — {s['token']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage = _storage_from_context(context)
    counts = storage.counts()
    cursor = counts["cursors"].get("ethereum")
    text = (
        "*Watcher status*\n"
        f"subscriptions: {counts['subscriptions']}\n"
        f"events seen: {counts['events']}\n"
        f"alerts sent: {counts['alerts']}\n"
        f"scan cursor (ethereum): {cursor if cursor is not None else 'not started'}"
    )
    await update.message.reply_text(text)


def build_application(token: str, db_path: str | os.PathLike, *, storage: Storage | None = None) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["storage"] = storage or Storage(db_path)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("status", cmd_status))
    return app


def send_alert(app: Application, chat_id: int, text: str) -> None:
    """Fire-and-forget alert delivery (used by the watcher loop)."""
    try:
        app.bot.send_message(chat_id=chat_id, text=text)
    except Exception as exc:  # Telegram API errors must not kill the scan loop
        log.warning("delivery to chat %s failed: %s", chat_id, exc)


def run_bot(token: str, db_path: str | os.PathLike) -> None:
    """Long-running polling bot. Ctrl-C to stop."""
    app = build_application(token, db_path)
    log.info("starting polling bot…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


def token_from_env() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN") or None