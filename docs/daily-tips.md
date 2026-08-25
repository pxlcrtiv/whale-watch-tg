# Whale-watching tips of the day

> Maintained by `scripts/daily_update.py` (Daily Green automation) — one
> dated, non-empty on-chain/whale tip per day, rotated from the pool in
> `scripts/tips_pool.json`. Pause by creating a `.daily-pause` file in the
> repo root, or unload the scheduler job (see README, Daily Green).


## 2026-08-23 — Whale tip of the day: Stablecoin exchange flows lead BTC direction

A recurring empirical pattern: stablecoin inflows (USDT/USDC to exchanges) rise before BTC buying pressure; outflow spikes precede selling. The theory: stablecoins are the 'dry powder' that converts into BTC/ETH. Track exchange stablecoin balances as a leading indicator alongside whale moves.

> `whale-watch watch --subscribe 0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48`


## 2026-08-24 — Whale tip of the day: Follow the validator deposit address

0x00000000219ab540356cbb839cbe05303d7705fa is the ETH2 staking deposit contract. A 32-ETH round-trip is routine; a 100,000+ ETH deposit in one block is institutional conviction. Deposit spikes correlate with long-term supply lock-up — a slow-motion whale signal that never hits an exchange.

> `whale-watch watch --subscribe 0x00000000219ab540356cbb839cbe05303d7705fa`


## 2026-08-25 — Whale tip of the day: Don't chase every 8-figure transfer: alert fatigue is real

MEGA stablecoin moves (ten-figure USDT shuffles between exchanges) happen daily and move nothing. The edge is in *classified* signals — size × direction × tagged entities × context. An alerting system without entity tagging and rate-class filtering trains you to ignore every alert. Better five good alerts than fifty noisy ones.

> `whale-watch demo`

