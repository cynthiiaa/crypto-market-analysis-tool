import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("1. Inserting mock vLLM event...\n")
event_data = {
    "asset": "BTC",
    "event_category": "EXCHANGE_LISTING",
    "vllm_sentiment_score": 8,
    "raw_text": "Coinbase to list massive BTC liquidity pool."
}

event_response = supabase.table("market_events").upsert(event_data).execute() # using upsert instead of insert to update current rows
event_id = event_response.data[0]["id"]
print(f"Event created with UUID: {event_id}\n")

print("2. Flushing simulated L2 buffer...")
snapshots = [
    {"event_id": event_id, "timestamp": "2024-11-01T12:00:00.100Z", "bid_price": 64000.50, "ask_price": 64001.00},
    {"event_id": event_id, "timestamp": "2024-11-01T12:00:00.200Z", "bid_price": 64000.00, "ask_price": 64001.50},
    {"event_id": event_id, "timestamp": "2024-11-01T12:00:00.300Z", "bid_price": 63999.50, "ask_price": 64002.00}
]

snap_response = supabase.table("liquidity_snapshots").upsert(snapshots).execute() # switch back to insert if you want
print(f"Successfully wrote {len(snap_response.data)} L2 snapshots to Supabase.")