# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Bot `--send-telegram` integration tests with a live bot token once one is
  provided (keyless mocks cover the handlers today).

## [0.1.0] — 2026-08-23

Initial public release.

### Added

- Cursor-safe ERC-20 transfer scanner (`whale_watch/watcher.py`): batched
  `eth_getLogs` over public RPC, persisted block cursor, idempotent event
  dedupe on `(tx_hash, log_index)`, crash-safe resume (batch-halving on RPC
  range rejection), optional provider swap for Alchemy/Infura RPCs.
- Address enrichment (`whale_watch/enrich.py`) with a bundled known-address
  list (21 entries: exchange hot/cold wallets, DEX routers, Tether treasury,
  ETH2 deposit contract) and exchange in/out/internal direction classification.
- Alert summarizer (`whale_watch/summarizer.py`): OpenAI-compatible LLM
  backend (env-configured) with a deterministic template fallback — no key,
  no network, no crash ever loses an alert; exact-subscriber-text renderer.
- SQLite store (`whale_watch/storage.py`): subscriptions, event ledger, scan
  cursor, delivered-alert ledger, per-chat spam gates (10 alerts/hour, 5 s
  minimum gap).
- Telegram bot skeleton (`whale_watch/bot.py`): `/start`, `/help`,
  `/subscribe`, `/unsubscribe`, `/list`, `/status`; per-user command cooldown;
  delivery helper for the watcher loop.
- Zero-key demo (`whale-watch demo`): 8 bundled fixture transfers run through
  the real pipeline into terminal alerts plus a self-contained HTML preview
  page (`examples/whale-alert-preview.html`).
- CLI (`whale-watch`): `demo`, `watch` (live loop, console or Telegram
  delivery), `bot`, `preview`, `status`.
- Daily Green automation: `scripts/daily_update.py` (deterministic daily tip
  rotation, idempotent, backfills missed days) + 24 curated on-chain/whale
  tips in `scripts/tips_pool.json`; `.github/workflows/daily.yml` fallback.
- CI: `.github/workflows/ci.yml` (pytest on 3.11/3.12, ruff, demo smoke test).
- 63 offline tests (fake RPC provider, mocked Telegram context, fixtures).
- README with real demo transcript, tech stack, honest caveats; MIT LICENSE;
  CONTRIBUTING.md.