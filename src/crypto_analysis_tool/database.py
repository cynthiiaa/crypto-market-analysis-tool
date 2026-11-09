import os
import logging
from dotenv import load_dotenv
from datetime import datetime
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[
                        logging.FileHandler("quant_pipeline.log"),  
                        logging.StreamHandler()                    
                    ]
                )
logger = logging.getLogger(__name__)

supabase = create_client(supabase_url=os.environ["SUPABASE_URL"], supabase_key=os.environ["SUPABASE_KEY"])

def flush_to_supabase(event_data, raw_headline, buffer_snapshot):
    logger.info(f"Saving Event and L2 Snapshot to Postgres...")

    event_res = supabase.table("market_events").insert({
        "asset": event_data.get("primary_asset_ticker", "UNKNOWN"),
        "event_category": event_data.get("core_event_category", "UNKNOWN"),
        "vllm_sentiment_score": event_data.get("sentiment", 0),
        "raw_text": raw_headline,
        "event_details": event_data.get("event_description", "")
    }).execute()

    event_id = event_res.data[0]["id"]

    snapshot_rows = [
        {
            "event_id": event_id,
            "timestamp": datetime.fromtimestamp(t[0] / 1000.0).isoformat(),
            "bid_price": t[1],
            "ask_price": t[2]
        }
        for t in buffer_snapshot
    ]

    if snapshot_rows:
        supabase.table("liquidity_snapshots").insert(snapshot_rows).execute()
        logger.info(f"Wrote {len(snapshot_rows)} L2 ticks to Supabase")