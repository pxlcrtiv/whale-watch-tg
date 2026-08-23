"""Alert summarization — the "AI" part of whale-watch-tg.

Two backends, one output shape:
  1. LLM backend (optional): any OpenAI-compatible /chat/completions endpoint
     (OpenAI, OpenRouter, Ollama, LocalAI, ...) configured via env vars:
       WHALE_WATCH_LLM_URL     e.g. https://api.openai.com/v1
       WHALE_WATCH_LLM_API_KEY
       WHALE_WATCH_LLM_MODEL    default gpt-4o-mini
  2. Deterministic template fallback (default, zero keys): rule-based
     narratives — inbound exchange flow -> "likely sell pressure",
     outbound -> "likely accumulation", untagged -> wallet-to-wallet.

The template fallback is always used unless an LLM is configured AND the call
succeeds; any network/model error degrades gracefully to the template so an
alert is never lost because a model was unavailable.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal

from .enrich import DIR_FROM_EXCHANGE, DIR_INTERNAL, DIR_P2P, DIR_TO_EXCHANGE
from .model import Alert, Transfer, fmt_usd, rate_class_for, short_addr

NARRATIVES = {
    DIR_TO_EXCHANGE: "Likely sell pressure: large inflow to a centralized exchange.",
    DIR_FROM_EXCHANGE: "Likely accumulation: large outflow from a centralized exchange.",
    DIR_P2P: "Wallet-to-wallet transfer (neither address is a tagged exchange).",
    DIR_INTERNAL: "Move between the same entity's own wallets — often hot-to-cold rebalancing noise.",
}

_SYSTEM_PROMPT = (
    "You are a concise on-chain whale-alert analyst. Given a crypto transfer, write "
    "ONE sentence (max 24 words) explaining what it likely means: is it sell pressure, "
    "accumulation, an exchange rebalancing, or a plain transfer? Mention direction and "
    "the exchange only if tagged. No hedging filler, no markdown, no emoji."
)


class Summarizer:
    def __init__(self, llm_url: str | None = None, llm_key: str | None = None, llm_model: str | None = None) -> None:
        self.llm_url = (llm_url or os.environ.get("WHALE_WATCH_LLM_URL", "")).rstrip("/")
        self.llm_key = llm_key or os.environ.get("WHALE_WATCH_LLM_API_KEY", "")
        self.llm_model = llm_model or os.environ.get("WHALE_WATCH_LLM_MODEL", "gpt-4o-mini")

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_url and self.llm_key)

    # ------------------------------------------------------------------ public
    def narrative(self, transfer: Transfer, from_tag: tuple | None, to_tag: tuple | None, direction: str) -> str:
        """LLM summary if configured, deterministic template otherwise."""
        if self.llm_configured:
            try:
                return self._llm_narrative(transfer, from_tag, to_tag, direction)
            except Exception:
                pass  # graceful degradation — template fallback below
        return self._template_narrative(direction)

    def build_alert(
        self,
        transfer: Transfer,
        from_tag: tuple[str, str] | None,
        to_tag: tuple[str, str] | None,
        direction: str,
        *,
        source: str = "live",
    ) -> Alert:
        narrative = self.narrative(transfer, from_tag, to_tag, direction)
        summary = render_alert(
            transfer,
            from_tag=from_tag,
            to_tag=to_tag,
            direction=direction,
            narrative=narrative,
            source=source,
        )
        return Alert(
            transfer=transfer,
            from_tag=from_tag[0] if from_tag else None,
            to_tag=to_tag[0] if to_tag else None,
            direction=direction,
            narrative=narrative,
            summary=summary,
            rate_class=rate_class_for(transfer.value_usd),
            source=source,
        )

    # ------------------------------------------------------------------- backends
    @staticmethod
    def _template_narrative(direction: str) -> str:
        return NARRATIVES.get(direction, NARRATIVES[DIR_P2P])

    def _llm_narrative(self, transfer: Transfer, from_tag: tuple | None, to_tag: tuple | None, direction: str) -> str:
        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Transfer: {transfer.amount_fmt()} {transfer.token}"
                        f" ({fmt_usd(transfer.value_usd)}) from {transfer.from_addr}"
                        f" tagged={from_tag} to {transfer.to_addr} tagged={to_tag};"
                        f" direction={direction}. One sentence."
                    ),
                },
            ],
            "temperature": 0.3,
            "max_tokens": 60,
        }
        req = urllib.request.Request(
            f"{self.llm_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.llm_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
        text = body["choices"][0]["message"]["content"].strip()
        return text if text else self._template_narrative(direction)


def render_alert(
    transfer: Transfer,
    *,
    from_tag: tuple[str, str] | None,
    to_tag: tuple[str, str] | None,
    direction: str,
    narrative: str,
    source: str,
    at: datetime | None = None,
) -> str:
    """The exact message a subscriber receives (Telegram-flavored plain text).

    Example:
      🐋 Whale alert · ETH · LARGE ($7.20M)

      3,000 ETH (≈ $7.20M) → Binance
      Likely sell pressure: large inflow to a centralized exchange.

      From 0x8a355f52…1b4f2e (untagged)
      To   0x28c6c062…bf21d60 (Binance · exchange)
      Tx   0x00000000…000001 · block 19,999,991 · ethereum
      2026-08-23 12:00:00 UTC

      Demo fixture — informational only, not trading advice.
    """
    at = at or (datetime.fromtimestamp(transfer.timestamp, tz=timezone.utc) if transfer.timestamp else datetime.now(timezone.utc))
    target = to_tag[0] if to_tag else "an unknown address"
    lines = [
        f"🐋 Whale alert · {transfer.token} · {rate_class_for(transfer.value_usd)} ({fmt_usd(transfer.value_usd)})",
        "",
        f"{transfer.amount_fmt()} {transfer.token} (≈ {fmt_usd(transfer.value_usd)}) → {target}",
        narrative,
        "",
        f"From {short_addr(transfer.from_addr)} ({from_tag[0] + ' · ' + from_tag[1] if from_tag else 'untagged'})",
        f"To   {short_addr(transfer.to_addr)} ({to_tag[0] + ' · ' + to_tag[1] if to_tag else 'untagged'})",
        f"Tx   {short_addr(transfer.tx_hash)} · block {transfer.block:,} · {transfer.token_address[:10]}…",
        at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "",
    ]
    if source == "fixture":
        lines.append("Demo fixture — informational only, not trading advice.")
    return "\n".join(lines).strip()


def fmt_amount_units(amount: Decimal, token: str) -> str:
    q = amount.quantize(Decimal("0.01"))
    return f"{q:,.2f}".rstrip("0").rstrip(".") + f" {token}"