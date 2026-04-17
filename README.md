# Knight Trader SDK Reference

This folder is published for transparency only.

It shows the Python client surface that competitor bots interact with during the event, but this repo copy is not the distribution path that submitted bots run from.

## What competitors actually use

Submitted bots run inside the competition environment with:

- the platform-provided SDK files
- `BOT_ID`
- `EXCHANGE_URL`

In practice, competitors write bot code against `ExchangeClient` and the bundled runtime handles the rest.

## SDK surface

The main client methods exposed in `knight_trader.py` / `knight_trader_share.py` are:

- `ExchangeClient()`
- `client.stream_state()`
- `client.get_assets()`
- `client.get_book(symbol=None)`
- `client.get_team_state()`
- `client.get_best_bid(symbol)`
- `client.get_best_ask(symbol)`
- `client.get_price(symbol)`
- `client.buy(symbol, price, quantity)`
- `client.sell(symbol, price, quantity)`
- `client.cancel(order_id)`
- `client.cancel_all()`
- `client.list_timeseries()`
- `client.get_timeseries(name, limit=100)`
- `client.place_auction_bid(symbol, yield_rate, quantity)`
- `client.close()`

## Environment model

The client expects the competition runtime to provide:

- `BOT_ID`
- `EXCHANGE_URL`

`BOT_ID` is the bot credential used by the SDK for trading and authenticated websocket access.

## Notes

- `stream_state()` consumes the authenticated `/ws/state` feed and yields the newest locally rebuilt state.
- `get_team_state()` is the intended low-frequency coordination path for bots on the same team.
- There is no separate bot-to-bot messaging API in the supported surface.
- This public repo copy is a readable reference. Competitors should not assume every internal helper file is meant to be copied manually into a submission.
