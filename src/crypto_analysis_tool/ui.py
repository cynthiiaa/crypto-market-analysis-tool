import os
import logging
from dotenv import load_dotenv
from nicegui import ui
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

def fetch_recent_events():
    """Fetch 10 most recent news events caught by the LLM"""
    response = supabase.table("market_events").select("*").order("created_at", desc=True).limit(10).execute()
    return response.data

def fetch_l2_snapshot(event_id):
    """Fetch the 60-second Kraken order book tick data for a specific event."""
    response = supabase.table("liquidity_snapshots").select("*").eq("event_id", event_id).order("timestamp").execute()
    return response.data


def render_chart(event_id):
    """Dynamically streams database snapshots directly into dual-axis EChart elements"""
    data = fetch_l2_snapshot(event_id)

    if not data:
        status_msg.set_text("Waiting for buffer flush... no L2 data found for this event.")
        status_msg.set_visibility(True)
        chart.set_visibility(False)
        metrics_bar.set_visibility(False)
        return

   # slice [11:19] to grab the HH:MM:SS from the ISO timestamp
    timestamps = [d["timestamp"][11:19] for d in data]
    bids = [float(d["bid_price"]) for d in data]
    asks = [float(d["ask_price"]) for d in data]
    spreads = [float(d.get("spread_bps", 0)) for d in data]
    
    latest_bid = bids[-1]
    latest_ask = asks[-1]
    latest_spread = spreads[-1]

    bid_metric.set_text(f"${latest_bid:,.2f}")
    ask_metric.set_text(f"${latest_ask:,.2f}")
    spread_metric.set_text(f"{latest_spread:.2f} bps")

    if latest_spread > 5.0:
        spread_metric.classes(replace="text-2xl font-black text-rose-600 animate-pulse")
    else:
        spread_metric.classes(replace="text-2xl font-bold text-emerald-600")

    status_msg.set_visibility(False)
    metrics_bar.set_visibility(True)
    chart.set_visibility(True)

    chart.options["xAxis"]["data"] = timestamps
    chart.options["series"][0]["data"] = asks    
    chart.options["series"][1]["data"] = bids     
    chart.options["series"][2]["data"] = spreads 

    chart.update()


#--------- UI Layout Configuration ---------#
ui.colors(primary="#1e292f", secondary="#2a3440", accent="#10b981")

with ui.header().classes("bg-primary text-white p-4 shadow-md"):
    ui.label("Bitcoin Liquidity Dashboard").classes("text-2xl font-bold tracking-wider")

with ui.row().classes("w-full p-4 gap-6 no-wrap"):
    # Left column is the news feeds
    with ui.column().classes("w-1/3 bg-gray-50 p-4 rounded shadow"):
        ui.label("Recent Market Triggers").classes("text-xl font-extrabold mb-4 text-gray-800")

        events = fetch_recent_events()
        for event in events:
            with ui.card().classes("w-full mb-3 border-l-4 border-emerald-500 hover:shadow-lg transition-shadow cursor-pointer") as card:
                ui.label(f"{event['asset']} - {event['event_category']}").classes("font-bold text-lg text-primary")
                ui.label(f"Sentiment: {event['vllm_sentiment_score']}").classes("text-sm text-gray-600")
                ui.label(event['raw_text']).classes("text-xs text-gray-500 italic mt-1 line-clamp-2")
                
                card.on("click", lambda e, eid=event["id"]: render_chart(eid))                  

    with ui.column().classes("w-3/5 p-4 bg-white rounded shadow"):
        # Right column is the L2 visualization
        ui.label("60-Second L2 Spread Anomaly").classes("text-xl font-bold mb-2 text-primary")
        status_msg = ui.label("Select a market trigger from the left to load L2 liquidity logs.").classes("text-gray-500 italic")

        with ui.row().classes("w-full justify-between gap-4 mb-4") as metrics_bar:
            with ui.card().classes("p-3 flex-1 text-center bg-gray-50 border border-gray-100"):
                ui.label("EVENT LATEST BID").classes("text-xs font-bold text-gray-400 tracking-wider")
                bid_metric = ui.label("-").classes("text-2xl font-bold text-gray-700")
            with ui.card().classes("p-3 flex-1 text-center bg-gray-50 border border-gray-100"):
                ui.label("EVENT LATEST ASK").classes("text-xs font-bold text-gray-400 tracking-wider")
                ask_metric = ui.label("-").classes("text-2xl font-bold text-gray-700")
            with ui.card().classes("p-3 flex-1 text-center bg-gray-50 border border-gray-100"):
                ui.label("LATEST SPREAD").classes("text-xs font-bold text-gray-400 tracking-wider")
                spread_metric = ui.label("-").classes("text-2xl font-bold text-emerald-600")
        
        metrics_bar.set_visibility(False)

        # pre-render an empty ECharts instance
        chart = ui.echart({
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "cross"}
            },
            "legend": {"data": ["Best Ask", "Best Bid", "Spread (bps)"], "top": "2%"},
            "grid": {"left": "5%", "right": "5%", "bottom": "15%", "containLabel": True},
            "xAxis": {
                "type": "category", 
                "data": [], 
                "boundaryGap": False,
                "axisLine": {"lineStyle": {"color": "#94a3b8"}}
            },
            "yAxis": [
                {
                    "type": "value",
                    "name": "Asset Price",
                    "scale": True, 
                    "splitLine": {"show": True, "lineStyle": {"type": "dashed", "color": "#f1f5f9"}},
                    "axisLabel": {"formatter": "${value}"}
                },
                {
                    "type": "value",
                    "name": "Spread (bps)",
                    "position": "right",
                    "splitLine": {"show": False} 
                }
            ],
            "series": [
                {
                    'name': 'Best Ask', 
                    'type': 'line', 
                    'yAxisIndex': 0, 
                    'data': [], 
                    'itemStyle': {'color': '#ef4444'}, 
                    'showSymbol': False, 
                    'lineStyle': {'width': 2},
                    'step': 'end' 
                },
                {
                    'name': 'Best Bid', 
                    'type': 'line', 
                    'yAxisIndex': 0,
                    'data': [], 
                    'itemStyle': {'color': '#10b981'}, 
                    'showSymbol': False, 
                    'lineStyle': {'width': 2},
                    'step': 'end'
                },
                {
                    'name': 'Spread (bps)', 
                    'type': 'bar', 
                    'yAxisIndex': 1, 
                    'data': [], 
                    'itemStyle': {'color': 'rgba(148, 163, 184, 0.15)'}, 
                    'barWidth': '70%'
                }
            ],
            "dataZoom": [{"type": "inside"}, {"type": "slider", "bottom": "2%"}],
        }).classes("w-full h-[450px]")

        chart.set_visibility(False)


ui.run(port=8088, title="L2 Dashboard", dark=False)
