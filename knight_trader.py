import os
import requests
import time
import uuid
import sys
import threading
import json
import websocket
import queue
from typing import Optional, Dict, List, Any

# --- Custom Exceptions for Graceful Handling ---
class ExchangeException(Exception):
    """Base class for exchange errors."""
    pass

class AuthenticationError(ExchangeException):
    """Raised when BOT_ID is missing or invalid."""
    pass

class OrderError(ExchangeException):
    """Raised when an order is rejected by the matching engine."""
    pass

# --- The Client ---
class ExchangeClient:
    def __init__(self, api_url: Optional[str] = None, bot_id: Optional[str] = None):
        """
        Initializes the Exchange Client.
        
        :param api_url: Optional override of the Exchange server URL (defaults to env-var EXCHANGE_URL or http://127.0.0.1:3000)
        :param bot_id: Optional UUID string identifying your bot (defaults to env-var BOT_ID)
        """
        # 1. Configuration Lookup
        self.api_url = api_url or os.environ.get("EXCHANGE_URL", "http://127.0.0.1:3000")
        self.bot_id = bot_id or os.environ.get("BOT_ID")

        if not self.bot_id:
            print("   Warning: `bot_id` not found in constructor or environment variables.")
            print("   You MUST provide a valid bot_id to place or cancel orders.")
            print("   Example: client = ExchangeClient(bot_id='your-uuid-here')\n")
        else:
            print(f"   Connected to Exchange at {self.api_url} as Agent {self.bot_id[:8]}...")

        # --- Background WebSocket Stream ---
        ws_url = self.api_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_url}/ws/book"

        self._latest_book = {"bids": {}, "asks": {}}
        self._book_lock = threading.Lock()
        self._tick_queue = queue.Queue(maxsize=1) # Zero backlog queue buffer
        self._stop_stream = False
        self._ws_app = None
        
        self._stream_thread = threading.Thread(target=self._websocket_stream, daemon=True)
        self._stream_thread.start()

    def _websocket_stream(self):
        """Background WebSocket loop maintaining zero-latency continuous orderbook delivery."""
        def on_message(ws, message):
            if not message: return
            try:
                data = json.loads(message)
                # 1. Update fallback cache for standard endpoints
                with self._book_lock:
                    self._latest_book = data
                
                # 2. Feed the Stream Generator Queue (Force clear for Backpressure)
                if self._tick_queue.full():
                    try: self._tick_queue.get_nowait()
                    except: pass
                self._tick_queue.put_nowait(data)
                
            except Exception:
                pass

        def on_error(ws, error):
            pass

        def on_close(ws, close_status_code, close_msg):
            pass

        def on_open(ws):
            pass

        while not self._stop_stream:
            try:
                self._ws_app = websocket.WebSocketApp(
                    self.ws_url,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close,
                    on_open=on_open
                )
                self._ws_app.run_forever(ping_interval=10, ping_timeout=5)
            except Exception:
                pass
            
            if not self._stop_stream:
                time.sleep(0.5) # Reconnect backoff

    def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper for POST requests with error handling."""
        if not self.bot_id:
            raise AuthenticationError("Cannot place call; `bot_id` is missing.")
            
        try:
            resp = requests.post(f"{self.api_url}{endpoint}", json=data, timeout=0.5)
            
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 400:
                raise OrderError(f"Rejected: {resp.text}")
            elif resp.status_code == 403:
                raise AuthenticationError(f"Forbidden: {resp.text}")
            else:
                raise ExchangeException(f"Server Error {resp.status_code}: {resp.text}")
                
        except requests.exceptions.ConnectionError:
            raise ExchangeException("Could not connect to Exchange (Is it running?)")
        except requests.exceptions.Timeout:
            raise ExchangeException("Exchange timed out")

    def get_book(self) -> Dict[str, Any]:
        """
        Returns the latest cached Order Book instantly (zero-latency).
        Returns: {'bids': {'100.00': [...]}, 'asks': {'101.00': [...]}}
        """
        with self._book_lock:
            # Return a shallow copy to prevent external mutation of background buffer
            return self._latest_book.copy()

    def stream_book(self):
        """
        Blocks and Yields the newest Order Book dataframe iteratively.
        Uses backpressure clearing to ensure students never process slow, outdated ticks.
        """
        while not self._stop_stream:
            try:
                # Timeout allows us to check self._stop_stream flag periodically
                item = self._tick_queue.get(timeout=1.0)
                yield item
            except queue.Empty:
                continue

    def place_order(self, side: str, price: float, quantity: float, symbol: str) -> str:
        """
        Places a Limit Order.
        Returns the order_id (UUID string) if accepted, or None if rejected.
        """
        if quantity <= 0 or price <= 0:
            print(f"   Warning: Invalid order parameters (Price: {price}, Qty: {quantity})")
            return None

        order_id = str(uuid.uuid4())
        order = {
            "id": order_id, 
            "owner_id": self.bot_id,
            "symbol": symbol.upper(),
            "price": f"{price:.2f}",
            "quantity": f"{quantity:.2f}",
            "side": side.capitalize(),
            "order_type": "Limit",
            "timestamp": int(time.time() * 1000)
        }

        try:
            self._post("/order", order)
            return order_id
        except OrderError as e:
            print(f"   Order Rejected: {e}")
            return None
        except ExchangeException as e:
            print(f"   Exchange Error: {e}")
            return None

    def cancel(self, order_id: str) -> bool:
        """
        Cancels an active Order by ID.
        Returns True if accepted, False otherwise.
        """
        try:
            self._post("/order/cancel", {"order_id": order_id, "bot_id": self.bot_id})
            return True
        except OrderError as e:
            print(f"   Cancel Rejected: {e}")
            return False
        except ExchangeException as e:
            print(f"   Exchange Error: {e}")
            return False

    # --- Convenience Wrappers ---
    
    def buy(self, symbol: str, price: float, quantity: float) -> str:
        return self.place_order("Bid", price, quantity, symbol)

    def sell(self, symbol: str, price: float, quantity: float) -> str:
        return self.place_order("Ask", price, quantity, symbol)

    # --- Timeseries Data ---

    def _agent_url(self) -> str:
        """Derive the agent server URL from exchange URL."""
        # For local testing back-ends
        if ":3000" in self.api_url:
             return self.api_url.replace(":3000", ":8000")
        return self.api_url

    def list_timeseries(self) -> List[Dict[str, Any]]:
        """Returns a list of all public timeseries with metadata."""
        try:
            resp = requests.get(f"{self._agent_url()}/timeseries", timeout=1.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception:
            return []

    def get_timeseries(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Returns data points for a named timeseries.
        Each point: {'t': unix_timestamp, 'v': value}
        """
        try:
            resp = requests.get(f"{self._agent_url()}/timeseries/{name}/data", params={"limit": limit}, timeout=1.0)
            if resp.status_code == 200:
                return resp.json().get("data", [])
            return []
        except Exception:
            return []

    # --- Treasury Auctions ---
    
    def place_auction_bid(self, symbol: str, price: float, quantity: float) -> bool:
        """
        Submits a secret bid for a Treasury Bond Dutch Auction.
        Locks (price * quantity) USD from capital.
        """
        if quantity <= 0 or price <= 0:
            print(f"   Warning: Invalid bid parameters (Price: {price}, Qty: {quantity})")
            return False

        payload = {
            "symbol": symbol.upper(),
            "price": price,
            "quantity": quantity,
            "api_key": self.bot_id
        }
        try:
            self._post("/api/auction/bid", payload)
            return True
        except ExchangeException as e:
            print(f"   Auction Bid Failed: {e}")
            return False
