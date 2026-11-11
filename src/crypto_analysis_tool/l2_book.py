import asyncio
import json
import time
import logging
from collections import deque
import websockets
from websockets.exceptions import ConnectionClosed

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[
                        logging.FileHandler("quant_pipeline.log"),  
                        logging.StreamHandler()                    
                    ]
                )
logger = logging.getLogger(__name__)

class KrakenL2Buffer:
    def __init__(self):
        self.history = deque(maxlen=120) # ensure we don't exceed 60 seconds of data at ~2 ticks/sec
        self.bids = {}
        self.asks = {}

    def update_book(self, side_dict, updates):
        for update in updates:
            price = float(update[0])
            volume = float(update[1])

            if volume == 0.0:
                side_dict.pop(price, None) # order was canceled or fully filled, remove it
            else:
                side_dict[price] = volume

    def calculate_metrics(self):
        if not self.bids or not self.asks:
            return None

        # want the highest bid and the lowest ask
        sorted_bids = sorted(self.bids.keys(), reverse=True)
        sorted_asks = sorted(self.asks.keys())

        best_bid = sorted_bids[0]
        best_ask = sorted_asks[0]
        if best_bid >= best_ask:
            return None

        spread_bps = ((best_ask - best_bid) / best_bid) * 10000

        mid_price = (best_bid + best_ask) / 2
        bid_threshold = mid_price * 0.999 # 10 bps down
        ask_threshold = mid_price * 1.001 # 10 bps up

        bid_depth = sum(vol for price, vol in self.bids.items() if price >= bid_threshold)
        ask_depth = sum(vol for price, vol in self.asks.items() if price <= ask_threshold)

        return {
            "timestamp_ms": int(time.time() * 1000),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread_bps": round(spread_bps, 2),
            "bid_depth_10bps": round(bid_depth, 4),
            "ask_depth_10bps": round(ask_depth, 4)
        }

    async def connect_and_listen(self, shared_buffer):
        uri = "wss://ws.kraken.com/"
        subscribe_msg = {
            "event": "subscribe",
            "pair": ["XBT/USD"],
            "subscription": {"name": "book", "depth": 25} # want the top 25 levels
        }

        while True:
            try:
                async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info("Connected to Kraken L2 WebSocket and subscribed")

                    async for message in ws:
                        data = json.loads(message)

                        if isinstance(data, dict):
                            continue

                        payload = data[1]

                        # Initial Snapshot
                        if "as" in payload and "bs" in payload:
                            self.bids.clear()
                            self.asks.clear()
                            self.update_book(self.asks, payload["as"])
                            self.update_book(self.bids, payload["bs"])
                            logger.info("Initial L2 Snapshot Loaded")
                        else:
                            if "a" in payload:
                                self.update_book(self.asks, payload["a"])
                            if "b" in payload:
                                self.update_book(self.bids, payload["b"])
        
                            metrics = self.calculate_metrics()
                            if metrics:
                                self.history.append(metrics)
                                shared_buffer.put_nowait(metrics)
            except (ConnectionClosed, Exception) as e:
                logger.error(f"WebSocket connection dropped: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

                

async def keyboard_trigger(buffer_instance):
    """Simulating a news event trigger."""
    loop = asyncio.get_running_loop()
    await asyncio.sleep(3)

    while True:
        user_input = await loop.run_in_executor(None, input, "Press [ENTER] to simulate a news event and dump buffer...")
        
        if user_input.strip().lower() == "q":
            logger.info("Shutting Down...")
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            break

        snapshot = list(buffer_instance.history)
        if len(snapshot) == 0:
            logger.info("Buffer is still empty. Waiting for market data...")
            continue

        filename = f"l2_snapshot_{int(time.time())}.json"
        with open(filename, "w") as f:
            json.dump(snapshot, f, indent=4)

        logger.info(f"EVENT TRIGGERED! Dumped last 60 seconds of L2 data ({len(snapshot)} rows) to {filename}")


async def main():
    kraken_buffer = KrakenL2Buffer()

    asyncio.create_task(kraken_buffer.connect_and_listen())
    asyncio.create_task(keyboard_trigger(kraken_buffer))

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    asyncio.run(main())