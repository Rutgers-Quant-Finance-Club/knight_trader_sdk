# Knight Trader SDK Reference

This folder is published for transparency only.

It shows the Python client surface that competitor bots interact with during the event, but this public repo is not the supported distribution path for submitted bots.

## What Competitors Actually Use

Submitted bots run inside the competition environment with the platform-provided SDK files and environment variables already present.

In practice, competitors write bot code against `ExchangeClient` and the bundled runtime handles the rest.

## Why This Copy Is Incomplete

This public reference intentionally omits some internal support files.

In particular, `exchange_wire.py` is not included here. That file handles binary websocket decoding for the live state stream. The public `knight_trader_share.py` file remains useful as a readable reference for:

* authentication shape
* request methods and endpoint usage
* high-level SDK method names
* expected team-state access patterns

It is not intended to be copied from this repo into a submitted bot.

## Reference Surface

The main client methods exposed in `knight_trader_share.py` are:

* `ExchangeClient()`
* `client.stream_state()`
* `client.get_book(symbol=None)`
* `client.get_team_state()`
* `client.get_dashboard()`
* `client.get_team_info()`
* `client.buy(symbol, price, quantity)`
* `client.sell(symbol, price, quantity)`
* `client.cancel(order_id)`
* `client.cancel_all()`
* `client.list_timeseries()`
* `client.get_timeseries(name, limit=100)`
* `client.place_auction_bid(symbol, yield_rate, quantity)`

## Environment Model

The client expects the competition runtime to provide:

* `BOT_ID`
* `EXCHANGE_URL`

An optional `AGENT_URL` may also be used for timeseries requests in deployments where the agent service is not derived from the exchange host automatically.

## Notes

* `get_team_state()` is the intended low-frequency coordination path for bots on the same team.
* There is no separate bot-to-bot messaging API shown in this public reference.
* `get_dashboard()` and `get_team_info()` are legacy aliases for `get_team_state()`.
