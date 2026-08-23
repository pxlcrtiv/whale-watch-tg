# Contributing to whale-watch-tg

Thanks for helping! This is a solo-but-open project: issues, PRs, and honest
caveats are all welcome.

## Ground rules

- **No keys in code, ever.** Telegram tokens, LLM keys, RPC keys go through
  env vars only. Tests are offline by design — keep them that way.
- **Demo stays zero-key.** If a feature needs a key to be *demonstrated*, it
  needs a fixture or a deterministic fallback too.
- **Don't break the idempotence contract.** Events dedupe on
  `(tx_hash, log_index)`; the cursor advances after each persisted batch.
  Anything that can skip or duplicate blocks on crash-retry is a bug.
- Tests before claims: every numeric claim in the README is reproduced by a
  command in this repo (`python -m pytest tests/ -q`, `whale-watch demo`).

## Getting started

```bash
git clone git@github.com:pxlcrtiv/whale-watch-tg.git
cd whale-watch-tg
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -q
ruff check whale_watch tests scripts
```

## What needs help

- More exchange addresses for `whale_watch/data/known_addresses.json` (with a
  source link in the PR description — labels must be verifiable).
- More fixture scenarios (exchange-internal hot→cold, treasury mints, wash
  patterns) in `whale_watch/data/fixtures/transfers.json`.
- Better template narratives / rate-class thresholds (backtested, with data).
- Tips for `scripts/tips_pool.json` (on-chain literacy, whale behavior,
  tooling — factual, helpful, no price predictions).

## Pull request checklist

- [ ] `python -m pytest tests/ -q` — all green, no `network` marks
- [ ] `ruff check whale_watch tests scripts` — clean
- [ ] `whale-watch demo` still renders a sensible alert + preview page
- [ ] CHANGELOG.md entry under `[Unreleased]`
- [ ] No secrets, no real funds, no paid-API hard dependencies

Small, focused PRs land faster than large rewrites. Questions first? Open an
issue — that's what they're for.

## License

By contributing you agree your work is licensed under the [MIT License](LICENSE).