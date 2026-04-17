# Developer Docs

These notes are for competitors writing bots with the bundled Python SDK.

## Runtime and authentication

- Bots run in the `trading_bot` image based on `python:3.9-slim`.
- Your upload is a single Python file mounted as `/app/user_bot.py`.
- The runtime injects:
  - `BOT_ID`
  - `EXCHANGE_URL`
- `ExchangeClient()` reads those automatically.
- The injected bot ID is the bot credential used for trading and authenticated websocket access.
- Supported libraries in the competition runtime are:
  - `numpy`
  - `pandas`
  - `scipy`
  - `scikit-learn`
  - `statsmodels`
  - `ta-lib`
  - the bundled `knight_trader` files
- Current limits are:
  - `256 KB` max upload size
  - `256 MB` memory
  - `0.25 CPU`
- Bots are uploaded paused and must be started from the dashboard.

```text
BOT_ID=<your bot id>
EXCHANGE_URL=http://127.0.0.1:3000
```

## SDK surface

The intended interface is the bundled Python client, not a custom low-level transport.

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

### Notes

- `client.stream_state()` yields only the newest locally rebuilt state. Slow bots can skip intermediate updates.
- The SDK connects to authenticated `/ws/state`, receives one protobuf snapshot on connect, and then applies protobuf deltas locally for books, timeseries, tape, competition state, and private order-status updates.
- `buy()` and `sell()` block briefly while the SDK waits for the private order-status update tied to the generated `client_order_id`.
- `get_team_state()` is the intended low-frequency coordination path for bots on the same team.
- There is no separate bot-to-bot messaging API.

## Capital, inventory, and shorting

- `RUD` is the shared team treasury asset.
- The dashboard allocates `RUD` from the team treasury into each bot's capital bucket.
- Buy orders consume and lock only that bot's allocated capital.
- Tradable inventory is held per bot, not in one shared team inventory bucket.
- One bot cannot directly sell another bot's inventory.
- Naked shorting is allowed.
- Uncovered short exposure is charged at `1.5x` market value in the team-level exposure model.
- Gross exposure is enforced at the team level using last traded prices.
- Leaderboard equity is marked at last traded prices, plus total bot capital, minus bailout penalties.
- Assets with no recorded trade can still mark at zero.

## Asset behavior

- `RUD`: internal cash only, not a tradable market.
- `Spot / equities`: ordinary continuous order books.
- `Forex`: same matching model as spot, but not a full currency-conversion engine.
- `Prediction markets`: YES-share contracts bounded to `$0.01` through `$0.99`.
- `Options`: standalone contracts with an underlying, strike, and call/put type. They cash-settle to intrinsic value on expiry or admin resolution.
- `Bonds`: issued through a uniform-price auction by yield at `$1000` par per unit. The stop-out yield becomes the coupon rate. Coupon payments credit in `RUD`.

## Competition state

- The exchange can be in:
  - `pre_open`
  - `live`
  - `paused`
  - `post_close`
- During `paused`, new orders, cancels, and auction bids are rejected.
- During `post_close`, trading stops but admin settlement and resolution actions can still happen.
- `competition_state` is included in the authenticated `/ws/state` stream so bots can behave deterministically.

## Public snapshot endpoints

These exist for the website and low-frequency tooling. They are not the primary interface for live trading bots.

- `GET /api/exchange/public/book`
- `GET /api/exchange/public/leaderboard`
- `GET /api/exchange/public/trades`
- `GET /api/exchange/public/tape`

Usage notes:

- On the official website, those paths are served from the site origin.
- External callers should use the site host, for example `https://tradetheknight.com/...`.
- External REST callers should include the team API key in `X-API-Key`.
- For live bot logic, use `ExchangeClient()` and `stream_state()` instead of polling these endpoints.

## Timeseries feeds

- Public timeseries live on the agent runner, not inside the exchange process.
- The latest timeseries values are included in `stream_state()`.
- Historical timeseries access is available through:
  - `client.list_timeseries()`
  - `client.get_timeseries(name, limit=100)`
- Agent runner endpoints:
  - `GET /api/agent/timeseries`
  - `GET /api/agent/timeseries/:name/data?limit=...`
- The built-in system series is `ior_rate`.
- `RUD` reserve interest is based on `ior_rate`.

## Starter bot

```python
import time
from knight_trader import ExchangeClient

SYMBOL = "SPOTDEMO"  # Replace with a real tradable symbol on competition day.


def run():
    client = ExchangeClient()
    resting_bid = None
    resting_ask = None
    next_refresh = 0.0

    for state in client.stream_state():
        try:
            if state.get("competition_state") != "live":
                continue
            if time.monotonic() < next_refresh:
                continue

            book = state.get("book", {}).get(SYMBOL, {})
            bids = sorted((float(p) for p in book.get("bids", {}).keys()), reverse=True)
            asks = sorted(float(p) for p in book.get("asks", {}).keys())

            if not bids or not asks:
                continue

            best_bid = bids[0]
            best_ask = asks[0]
            spread = best_ask - best_bid

            if spread < 0.05:
                continue

            if resting_bid:
                client.cancel(resting_bid)
            if resting_ask:
                client.cancel(resting_ask)

            bid_px = round(best_bid + 0.01, 4)
            ask_px = round(best_ask - 0.01, 4)

            resting_bid = client.buy(SYMBOL, bid_px, 1.0)
            resting_ask = client.sell(SYMBOL, ask_px, 1.0)
            next_refresh = time.monotonic() + 0.5
        except Exception as exc:
            print(f"bot error: {exc}")
            time.sleep(1.0)


if __name__ == "__main__":
    run()
```

## See also

- [Rules and FAQ](/rules)
- [Home](/)
