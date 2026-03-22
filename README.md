# Knight Trader SDK

The official Python client for the **Trade the Knight** algorithmic trading platform. 

This SDK provides a real-time, zero-latency streaming connection to the central matching engine, allowing developers to consume Order Book updates and execute trades asynchronously.

---

## Installation

To use this client, you need Python 3.9+ and two core dependencies:

```bash
pip install requests websocket-client
```

Simply drop `knight_trader_share.py` into your project directory (or rename it to `knight_trader.py`) to get started!

---

## Quick Start

To connect your algorithm to the exchange, instantiate the `ExchangeClient`. 

```python
from knight_trader import ExchangeClient

# 1. Initialize with your Bot ID
client = ExchangeClient(
    api_url="https://tradetheknight.com", 
    bot_id="your-uuid-here"
)

# 2. Continuous Event-Driven Loop
# This iterator blocks natively until the Exchange pushes a state update.
for book in client.stream_book():
    # Example: Look at Apple (AAPL)
    if "AAPL" not in book:
        continue
        
    aapl_book = book["AAPL"]
    best_bid = max([float(p) for p in aapl_book.get("bids", {}).keys()]) if aapl_book.get("bids") else None
    best_ask = min([float(p) for p in aapl_book.get("asks", {}).keys()]) if aapl_book.get("asks") else None
    
    # Place a buy order if spread exists
    if best_bid and best_ask:
        print(f"Spread: {best_ask - best_bid:.2f}")
        # client.buy("AAPL", price=best_bid + 0.01, quantity=10.0)
```

---

## API Reference

### 1. Market Data Streams

#### `client.stream_book() -> Generator[dict]`
A blocking generator that yields the newest Order Book dataframe the exact CPU cycle the exchange broadcasts it. **Highly recommended for live strategy execution.**

```python
for book in client.stream_book():
    print(book)
```

#### `client.get_book() -> dict`
Instantly returns a static snapshot of the latest order book cached in memory. Does not block.

---

### 2. Order Execution

#### `client.buy(symbol: str, price: float, quantity: float) -> str`
Places a Bid limit order. Returns an `order_id` (UUID string) if accepted, or `None` if rejected.

#### `client.sell(symbol: str, price: float, quantity: float) -> str`
Places an Ask limit order. Shorts require sufficient Gross Margin allocation.

#### `client.cancel(order_id: str) -> bool`
Cancels an active pending order on the board.

---

### 3. Alternative Instruments & Timeseries

#### `client.list_timeseries() -> list`
Returns a list of metadata for macro-economic blind prediction streams.

#### `client.get_timeseries(name: str, limit: int = 100) -> list`
Returns historical ticks for the specified indicator: `[{'t': timestamp, 'v': value}]`.

#### `client.place_auction_bid(symbol: str, price: float, quantity: float) -> bool`
Submits a secret Dutch Auction bid for Treasury (When-Issued) bonds.

---

## Environment Variables

When submitting your bot on the platform, all credentials (`BOT_ID` and `EXCHANGE_URL`) are **automatically injected into your container environment by the infrastructure**. You do not need to manage them.

For local deployment or debugging via Docker, you can pass these variables yourself:

*   `EXCHANGE_URL`: Defaults to `http://127.0.0.1:3000`
*   `BOT_ID`: Required for execution if not passed manually.
