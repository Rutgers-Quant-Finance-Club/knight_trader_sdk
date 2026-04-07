import os
import time
import uuid
import threading
import queue
from urllib.parse import urlparse, urlunparse
from typing import Optional, Dict, List, Any

import requests
import websocket

try:
    from exchange_wire import decode_state_message
except ImportError:
    try:
        from .exchange_wire import decode_state_message
    except ImportError:
        def decode_state_message(message: Any) -> Dict[str, Any]:
            raise ImportError(
                "exchange_wire.py is not included in this public transparency copy."
            )

# --- Custom Exceptions for Graceful Handling ---
class ExchangeException(Exception):
    """Base class for exchange errors."""
    pass

class AuthenticationError(ExchangeException):
    """Raised when BOT_ID is missing."""
    pass

class OrderError(ExchangeException):
    """Raised when an order is rejected."""
    pass


# --- The Client ---
class ExchangeClient:
    def __init__(
        self,
        api_url: Optional[str] = None,
        bot_id: Optional[str] = None,
        agent_url: Optional[str] = None,
    ):
        # 1. Environment Check with Overrides
        self.api_url = api_url or os.environ.get("EXCHANGE_URL", "http://127.0.0.1:3000")
        self.bot_id = bot_id or os.environ.get("BOT_ID")
        self.agent_url = agent_url or os.environ.get("AGENT_URL")

        # NO FALLBACKS for live trading. 
        if not self.bot_id:
            print(" Warning: BOT_ID not found in environment variables or constructor.")
            print(" Off-platform scripts (like this SDK) require a valid BOT_ID even for public data.")
            print(" You MUST provide a bot_id to pull data or place orders.\n")
        else:
            print(f"Connected to Exchange at {self.api_url}.")

        # --- Background WebSocket Stream ---
        ws_url = self.api_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_url}/ws/state"

        # Unified State Cache
        self._latest_state = {"tick": 0, "book": {}, "timeseries": {}}
        self._state_lock = threading.Lock()
        self._active_orders = set() # Track for cancel_all
        self._tick_queue = queue.Queue(maxsize=1) # Zero backlog queue buffer
        self._stop_stream = False
        self._ws_app = None
        
        self._stream_thread = threading.Thread(target=self._websocket_stream, daemon=True)
        self._stream_thread.start()

    def _websocket_stream(self):
        """Background WebSocket loop maintaining zero-latency continuous state delivery."""
        def on_message(ws, message):
            if not message: return
            try:
                data = decode_state_message(message)
                # 1. Update fallback cache for standard endpoints
                with self._state_lock:
                    self._latest_state = data
                
                # 2. Feed the Stream Generator Queue (Force clear for Backpressure)
                if self._tick_queue.full():
                    try: self._tick_queue.get_nowait()
                    except: pass
                self._tick_queue.put_nowait(data)
                
            except Exception:
                pass

        def on_error(ws, error):
            print(f"WebSocket SDK Error: {error}")

        def on_close(ws, close_status_code, close_msg):
            print(f"WebSocket Closed: {close_status_code} - {close_msg}")

        def on_open(ws):
            print(f"WebSocket Stream Connected to {self.ws_url}")

        while not self._stop_stream:
            try:
                # 1. Add the API Key to the WebSocket Handshake
                headers = [f"X-API-Key: {self.bot_id}"] if self.bot_id else []
                
                self._ws_app = websocket.WebSocketApp(
                    self.ws_url,
                    header=headers,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close,
                    on_open=on_open
                )
                self._ws_app.run_forever(ping_interval=10, ping_timeout=5)
            except Exception as e:
                # 2. Stop hiding the errors!
                print(f"Critical WS Crash: {e}") 
            
            if not self._stop_stream:
                time.sleep(0.5) # Reconnect backoff

    def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper for POST requests with error handling."""
        if not self.bot_id:
            raise AuthenticationError("CRITICAL: Cannot place orders or cancel without a BOT_ID.")
            
        headers = {"X-API-Key": self.bot_id}

        try:
            resp = requests.post(f"{self.api_url}{endpoint}", json=data, headers=headers, timeout=0.5)
            
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

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Internal helper for GET requests with error handling."""
        headers = {"X-API-Key": self.bot_id} if self.bot_id else {}
        try:
            resp = requests.get(f"{self.api_url}{endpoint}", params=params, headers=headers, timeout=1.0)
            if resp.status_code == 200:
                return resp.json()
            else:
                return {}
        except Exception:
            return {}

    # --- State & Data Methods ---

    def stream_state(self):
        """
        Blocks and Yields the newest unified Market State (Tick, Book, and Timeseries).
        Uses backpressure clearing to ensure students never process slow, outdated ticks.
        """
        while not self._stop_stream:
            try:
                # Timeout allows us to check self._stop_stream flag periodically
                item = self._tick_queue.get(timeout=1.0)
                yield item
            except queue.Empty:
                continue

    def get_book(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns the latest cached Order Book instantly (zero-latency).
        Extracts the 'book' portion from the unified state.
        If symbol is provided, returns only that symbol's book (flat format).
        """
        with self._state_lock:
            full_book = self._latest_state.get("book", {})
            
            if symbol:
                return full_book.get(symbol.upper(), {"bids": {}, "asks": {}})
            
            # Auto-flattening for single-instrument ecosystems
            if "bids" not in full_book and len(full_book) == 1:
                return list(full_book.values())[0]

            # Return a shallow copy to prevent external mutation of background buffer
            return full_book.copy()

    def get_dashboard(self) -> Dict[str, Any]:
        """Returns team state visible to the current bot (bots, positions, orders, trades)."""
        return self._get("/api/exchange/team/state")

    def get_team_info(self) -> Dict[str, Any]:
        """Alias for get_dashboard() to support legacy bots."""
        return self.get_dashboard()

    def get_team_state(self) -> Dict[str, Any]:
        """Returns shared team state for bot coordination."""
        return self.get_dashboard()

    def get_price(self, symbol: str) -> float:
        """Helper to get current mid-price for a symbol."""
        book = self.get_book(symbol)
        bids = [float(p) for p in book.get('bids', {}).keys()]
        asks = [float(p) for p in book.get('asks', {}).keys()]
        if not bids or not asks: return 0.0
        return (max(bids) + min(asks)) / 2

    def cancel_all(self, symbol: Optional[str] = None) -> bool:
        """Cancels all active orders tracked by this client instance."""
        # Note: In a production system, this would call a bulk cancel endpoint.
        # Here we iterate over known active orders.
        to_cancel = list(self._active_orders)
        for oid in to_cancel:
             self.cancel(oid)
        return True

    # --- Trading Methods ---

    def place_order(self, side: str, price: float, quantity: float, symbol: str) -> Optional[str]:
        """
        Places a Limit Order.
        Returns an order UUID string if accepted, or None if rejected.
        """
        if quantity <= 0 or price <= 0:
            print(f"Warning: Invalid order parameters (Price: {price}, Qty: {quantity})")
            return None

        order_id = str(uuid.uuid4()) # Capture the ID
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
            self._post("/api/exchange/order", order)
            self._active_orders.add(order_id)
            return order_id # RETURN THE ID INSTEAD OF TRUE
        except OrderError as e:
            print(f"Order Rejected: {e}")
            return None
        except ExchangeException as e:
            print(f"Exchange Error: {e}")
            return None

    def cancel(self, order_id: str) -> bool:
        """
        Cancels an active Order by ID.
        Returns True if accepted, False otherwise.
        """
        try:
            self._post("/api/exchange/order/cancel", {"order_id": order_id, "bot_id": self.bot_id})
            if order_id in self._active_orders:
                self._active_orders.remove(order_id)
            return True
        except OrderError as e:
            print(f"Cancel Rejected: {e}")
            return False
        except ExchangeException as e:
            print(f"Exchange Error: {e}")
            return False

    # --- Convenience Wrappers ---
    
    def buy(self, symbol: str, price: float, quantity: float) -> Optional[str]:
        return self.place_order("Bid", price, quantity, symbol)

    def sell(self, symbol: str, price: float, quantity: float) -> Optional[str]:
        return self.place_order("Ask", price, quantity, symbol)

    # --- Timeseries Data ---

    def _agent_url(self) -> str:
        """
        Resolve the agent server URL.
        Priority:
        1. Explicit constructor argument
        2. AGENT_URL environment variable
        3. Exchange host with port swapped from 3000 -> 8000
        """
        if self.agent_url:
            return self.agent_url.rstrip("/")

        parsed = urlparse(self.api_url)
        if parsed.port == 3000:
            netloc = parsed.hostname or ""
            if parsed.username:
                netloc = parsed.username + ("@" + netloc if netloc else "")
            if parsed.password:
                netloc = parsed.username + ":" + parsed.password + "@" + (parsed.hostname or "")
            if parsed.hostname:
                host = parsed.hostname
                if ":" in host and not host.startswith("["):
                    host = f"[{host}]"
                netloc = f"{host}:8000"
                if parsed.username:
                    auth = parsed.username
                    if parsed.password:
                        auth += f":{parsed.password}"
                    netloc = f"{auth}@{netloc}"
            return urlunparse(parsed._replace(netloc=netloc, path="", params="", query="", fragment="")).rstrip("/")

        raise ExchangeException(
            "Agent URL is not configured. Pass agent_url=... or set AGENT_URL for timeseries access."
        )

    def list_timeseries(self) -> List[Dict[str, Any]]:
        """Returns a list of all public timeseries with metadata."""
        headers = {"X-API-Key": self.bot_id} if self.bot_id else {}
        try:
            resp = requests.get(f"{self._agent_url()}/timeseries", headers=headers, timeout=1.0)
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
        headers = {"X-API-Key": self.bot_id} if self.bot_id else {}
        try:
            resp = requests.get(f"{self._agent_url()}/timeseries/{name}/data", params={"limit": limit}, headers=headers, timeout=1.0)
            if resp.status_code == 200:
                return resp.json().get("data", [])
            return []
        except Exception:
            return []

    # --- Treasury Auctions ---
    
    def place_auction_bid(self, symbol: str, yield_rate: float, quantity: float) -> bool:
        """
        Submits a secret bid for a Treasury Bond Dutch Auction.
        
        Args:
            symbol: The bond ticker (e.g. "BOND_WI").
            yield_rate: Your desired yield as a decimal (e.g. 0.05 for 5%).
                        Lower yields win first. The highest winning yield becomes
                        the bond's coupon rate (stop-out yield).
            quantity: Number of face-value units to bid for.
        
        Capital locked: $1000.00 * quantity (bonds are issued at Par).
        If you win: You receive bonds that pay the stop-out coupon rate.
        If you lose: Your locked capital is returned.
        
        Returns True if accepted.
        """
        if quantity <= 0 or yield_rate <= 0:
            print(f"Warning: Invalid bid parameters (Yield: {yield_rate}, Qty: {quantity})")
            return False

        payload = {
            "symbol": symbol.upper(),
            "yield_rate": yield_rate,
            "quantity": quantity,
            "bot_id": self.bot_id
        }
        try:
            self._post("/api/exchange/auction/bid", payload)
            return True
        except ExchangeException as e:
            print(f"Auction Bid Failed: {e}")
            return False
