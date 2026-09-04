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


## 2026-08-26 — Whale tip of the day: Your cursor is a database row, not a magic number

Cursor safety means: read last_block from storage, scan cursor+1..cursor+N, persist after each batch. If you crash mid-scan, the next run resumes exactly where you left off; reprocessing an old range is harmless because events dedupe on (tx_hash, log_index). Never derive the cursor from 'now' at startup — you'll skip blocks during downtime.

> `whale-watch status`


## 2026-08-27 — Whale tip of the day: Cold wallet outflows are accumulation — until they're not

Large OTC settlements are often settled from cold wallets to an under-the-radar address, then re-deposited to an exchange days later. The first leg reads as bullish accumulation; the second leg as sell pressure. Tag the OTC desk addresses in your known-address list to link the two legs — that's how the pros read tape.

> `whale-watch watch`


## 2026-08-28 — Whale tip of the day: Dust attacks and address contamination

Attackers airdrop tiny amounts (dust) to many wallets to cluster them (privacy deanonymization). If you subscribe to every address that 'sent you dust', you'll build a map of clusters — and scanners that alert on dust-level transfers teach you nothing. Filter by minimum USD value; whale-watch's WATCH class starts at $100K per transfer.

> `whale-watch demo`


## 2026-08-29 — Whale tip of the day: Exchange reserve data is a public good

Public proof-of-reserve trackers (alternative.me, CryptoQuant, Glassnode free tier) show aggregate CEX balances. Combined with your own whale alerts: falling exchange ETH reserves + repeated whale *outflows* = supply being locked away — historically a bullish structural shift. Reserves are lagging; your alerts are leading.

> `whale-watch status`


## 2026-08-30 — Whale tip of the day: Timestamp discipline: block time ≠ execution time

A transfer's block timestamp is when the block was minted, not when the tx was submitted. Whale scanners showing 'actionable NOW' are really showing 'actionable ~12s ago at best'. For speed, pair on-chain alerts with mempool sniffing; for truth, always cite block height, not clock time, in alert metadata.

> `whale-watch demo`


## 2026-08-31 — Whale tip of the day: Chain splits: what works on Ethereum generalizes

The Transfer-event scanner is chain-agnostic — same topic0 on polygon, arbitrum, base, optimism. What changes: token addresses, RPC endpoints, and the exchange wallet map. A multi-chain whale watcher is one tokens.json and one known_addresses.json away. Start single-chain, keep the data files the extension point.

> `whale-watch watch`


## 2026-09-01 — Whale tip of the day: Backtest your alert thresholds before you trust them

The honest way to tune a whale alert: replay historical Transfer logs through your exact pipeline (enrichment → filter → narrative) over 90 days, count alerts that preceded notable price moves vs noise. If your 'mega move' threshold fires 200 times a week, it's not a signal, it's a screensaver. whale-watch fixtures make this replay testable offline.

> `whale-watch demo`


## 2026-09-02 — Whale tip of the day: Privacy rails change the meaning of 'exchange'

Deposits via Tornado Cash, Railgun, or relayer contracts rarely hit the exchange hot wallet directly — they arrive from a pool or a private relayer address first. A scanner that tags only raw addresses will classify a big private deposit as 'wallet-to-wallet'. Keep a denylist/known-relayer list updated, or accept the blind spot consciously.

> `whale-watch watch`


## 2026-09-03 — Whale tip of the day: Ships weekly, not hourly: cadence beats noise

Day-trading whale alerts is a zero-sum race against MEV bots and OTC desks. The durable edge is *weekly synthesis*: net exchange flows per token, top-10 flows, accumulation clusters — delivered as a single readable digest. The alert is for awareness; the digest is for decision. Both, in that order.

> `whale-watch demo`


## 2026-09-04 — Whale tip of the day: Exchange inflow ≈ sell pressure — but it's a heuristic, not a fact

The core whale-watch signal: ERC-20 transfers INTO an exchange hot wallet usually precede sell orders, and outflows usually mean accumulation. It is a strong prior, not a guarantee — exchanges also rebalance internally (hot→cold), and OTC desks settle off-chain. Always read the size, the target (hot vs cold wallet), and the entity before acting.

> `whale-watch demo`


## 2026-09-05 — Whale tip of the day: The Transfer event is the whole game

Every ERC-20 movement emits `Transfer(from, to, value)` with topic0 = keccak256("Transfer(address,address,uint256)") = 0xddf252ad…b3ef. A whale scanner is mostly a filter over eth_getLogs for that signature — sender in topics[1], receiver in topics[2], amount in data. Know those three fields and you can track any token without indexing every block yourself.

> `curl -s -X POST https://ethereum-rpc.publicnode.com -H 'Content-Type: application/json' --data '{"jsonrpc":"2.0","id":1,"method":"eth_getLogs","params":[{"fromBlock":"0x1312d00","toBlock":"0x1312d00","address":"0xdac17f958d2ee523a2206206994597c13d831ec7","topics":["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"]}]}'`

