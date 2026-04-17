# Rules and FAQ

This page is the plain-language version of the competition rules and operating assumptions.

## Schedule

1. `11:00 AM`: Check-in starts
2. `11:45 AM`: Opening remarks
3. `12:00 PM`: Trading starts
4. `2:30 PM`: Lunch starts and trading pauses
5. `3:00 PM`: Trading resumes
6. `5:00 PM`: Surprise event
7. `6:00 PM`: Dinner starts and trading pauses
8. `6:30 PM`: Trading resumes
9. `8:00 PM`: Trading stops
10. `8:30 PM`: Awards ceremony

## Team structure and operations

- Teams can have up to `4` members.
- Each team can run up to `4` active competitor bots at a time.
- New teams begin with `$1,000,000` of `RUD`.
- `RUD` is the shared team treasury asset.
- Tradable inventory is held per bot, not in one shared team inventory bucket.

## Bot runtime and submission limits

- Competitor bots are uploaded as a single Python file.
- The guaranteed runtime is `Python 3.9` with the bundled `knight_trader` SDK and the approved quantitative libraries.
- Upload size is capped at `256 KB`.
- Each bot container is started with `256 MB` memory and `0.25 CPU`.
- Deployed bots receive `BOT_ID` and `EXCHANGE_URL`.
- Bots are uploaded in a paused state and must be started from the dashboard.

## Trading mechanics

- Markets use continuous limit-order matching with strict price-time priority.
- Order quantities snap to `0.001` units.
- Buy orders lock the bot's allocated `RUD` capital.
- Filled inventory belongs to the bot that acquired it.
- Naked shorting is allowed.
- Uncovered short exposure is charged at `1.5x` market value.
- Team-level exposure is still enforced across all bots on the team.
- Self-match prevention is active.
- Prediction markets can only trade between `$0.01` and `$0.99` per share.
- During a global halt, new orders, cancels, and auction bids are rejected.

## Market data and latency

- Bots connect to authenticated `/ws/state` through the SDK.
- The live state includes tick, competition state, order books, recent trades, and timeseries reconstructed from one snapshot plus deltas.
- The SDK keeps a zero-backlog queue, so slow bots can skip intermediate states and only receive the newest reconstructed snapshot.
- On reconnect or detected sequence gaps, the SDK reconnects for a fresh `/ws/state` snapshot.

## Assets

- `RUD`: internal cash asset used for balances, payouts, bot capital allocation, scoring, and bailout resets.
- `Spot / equities`: standard spot-style instruments with their own order books.
- `Forex`: separate tradable instruments using the same matching model as spot.
- `Bonds`: auctioned at `$1000` par per unit, with the stop-out yield becoming the coupon rate.
- `Options`: cash-settled derivatives with an underlying symbol, strike, and call/put type.
- `Prediction markets`: YES-share contracts that pay `$1` in `RUD` if they resolve YES.

## Capital, scoring, and bailouts

- Leaderboard equity is computed from per-bot inventory and team treasury balances marked at last traded prices, plus total bot capital, minus bailout penalties.
- Assets with no trade history can contribute zero to leaderboard valuation.
- Team gross exposure is capped by the sum of bot capital allocations.
- `RUD` balances earn periodic interest from the `ior_rate` timeseries.
- If team equity falls to `$50,000` or lower, the exchange triggers an automatic bailout.
- A bailout pauses all team bots, wipes non-`RUD` positions, resets `RUD` to `$1,000,000`, and adds a permanent `$1,500,000` leaderboard penalty.

## Operational notes

- The public site exposes leaderboard, public book, public trades, public tape, and public timeseries data.
- Competitor bot support is centered on the bundled SDK and websocket market-data stream.
- Admins can create assets, toggle tradability, clear books, resolve markets, resolve options, convert when-issued assets, and mature bonds.

## Penalties and disqualification

- Bots that exceed container limits or crash are not automatically repaired.
- Attempting to bypass auth, tamper with balances, abuse infrastructure, or interfere with other teams is grounds for immediate disqualification.
- Competitors are responsible for their own bot code, open orders, and capital usage.

## FAQ

### How do bots authenticate?

Deployed bots receive `BOT_ID` and `EXCHANGE_URL` in their container environment. The bundled `ExchangeClient` uses those automatically.

### Can bots on the same team coordinate?

Yes. The intended path is shared market state plus `get_team_state()`, which exposes current team balances, bots, open team orders, and recent team trades.

### How is the leaderboard calculated?

Total equity is marked at last traded prices, plus total bot capital, minus any bailout penalties. If an asset has never traded, it may still mark at zero.

### Can we short assets?

Yes. Naked shorting is allowed. Inventory is per bot, but exposure is enforced at the team level.

### Is there a minimum order size?

There is no large product-specific minimum size currently, but quantities snap to `0.001` units. Orders that round down to zero are rejected.

### Is the websocket stream JSON?

No. The official competitor stream is protobuf over `/ws/state`. The bundled Python SDK handles the snapshot-plus-delta protocol and local state rebuild for you.

### Do public REST endpoints replace the SDK?

No. The public REST endpoints are useful for dashboards, analytics, and low-frequency tooling. For live bot logic, use the SDK and `/ws/state`.

## See also

- [Developer docs](/docs)
- [Home](/)
