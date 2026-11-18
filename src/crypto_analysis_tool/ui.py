import os
import logging
from dotenv import load_dotenv
from nicegui import ui
from openai import AsyncOpenAI
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

llm_client = AsyncOpenAI(base_url=os.environ["MODAL_CHATBOT_URL"], api_key="dummy-key")

MODEL_NAME = "kaitchup/Olmo-3.1-32B-Instruct-awq-w4a16-asym"
MAX_L2_CONTEXT_ROWS = 20
MAX_CHAT_HISTORY_MESSAGES = 8
MAX_CHAT_HISTORY_CHARS = 6000

# global State for RAG 
active_context_state = {
    "event": None,
    "l2_data": []
}

def fetch_recent_events():
    """Fetch 10 most recent news events caught by the LLM"""
    response = supabase.table("market_events").select("*").order("created_at", desc=True).limit(10).execute()
    return response.data

def fetch_l2_snapshot(event_id):
    """Fetch the 60-second Kraken order book tick data for a specific event."""
    response = supabase.table("liquidity_snapshots").select("*").eq("event_id", event_id).order("timestamp").execute()
    return response.data

def render_chart(event_data):
    """Dynamically streams database snapshots directly into dual-axis EChart elements and updates AI context"""
    event_id = event_data["id"]
    data = fetch_l2_snapshot(event_id)

    active_context_state["event"] = event_data
    active_context_state["l2_data"] = data

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

chat_history = [
    {
        "role": "system",
        "content": "You are a quantitative crypto assistant helping analyze Kraken L2 order book snapshots and market news.",
    }
]

# Single unified header
with ui.header().classes("bg-primary text-white p-4 shadow-md justify-between items-center"):
    ui.label("Bitcoin Liquidity Dashboard").classes("text-2xl font-bold tracking-wider")

# BACKGROUND LAYER: Two-column layout with bottom padding
with ui.row().classes("w-full p-4 pb-80 gap-6 no-wrap"):

    # Left column: Recent Market Triggers
    with ui.column().classes("w-1/3 bg-gray-50 p-4 rounded shadow"):
        ui.label("Recent Market Triggers").classes("text-xl font-extrabold mb-4 text-gray-800")

        events = fetch_recent_events()
        for event in events:
            with ui.card().classes(
                "w-full mb-3 border-l-4 border-emerald-500 hover:shadow-lg transition-shadow cursor-pointer"
            ) as card:
                ui.label(f"{event['asset']} - {event['event_category']}").classes("font-bold text-lg text-primary")
                ui.label(f"Sentiment: {event['vllm_sentiment_score']}").classes("text-sm text-gray-600")
                ui.label(event["raw_text"]).classes("text-xs text-gray-500 italic mt-1 line-clamp-2")

                # --- MODIFIED: Pass the entire event object instead of just the ID ---
                card.on("click", lambda e, ev=event: render_chart(ev))

    # Right column: L2 Spread Anomaly 
    with ui.column().classes("flex-grow p-4 bg-white rounded shadow"):
        ui.label("60-Second L2 Spread Anomaly").classes("text-xl font-bold mb-2 text-primary")
        status_msg = ui.label("Select a market trigger from the left to load L2 liquidity logs.").classes(
            "text-gray-500 italic"
        )

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
        chart = ui.echart(
            {
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {"type": "cross"},
                },
                "legend": {"data": ["Best Ask", "Best Bid", "Spread (bps)"], "top": "2%"},
                "grid": {"left": "5%", "right": "5%", "bottom": "15%", "containLabel": True},
                "xAxis": {
                    "type": "category",
                    "data": [],
                    "boundaryGap": False,
                    "axisLine": {"lineStyle": {"color": "#94a3b8"}},
                },
                "yAxis": [
                    {
                        "type": "value",
                        "name": "Asset Price",
                        "scale": True,
                        "splitLine": {"show": True, "lineStyle": {"type": "dashed", "color": "#f1f5f9"}},
                        "axisLabel": {"formatter": "${value}"},
                    },
                    {
                        "type": "value",
                        "name": "Spread (bps)",
                        "position": "right",
                        "splitLine": {"show": False},
                    },
                ],
                "series": [
                    {
                        "name": "Best Ask",
                        "type": "line",
                        "yAxisIndex": 0,
                        "data": [],
                        "itemStyle": {"color": "#ef4444"},
                        "showSymbol": False,
                        "lineStyle": {"width": 2},
                        "step": "end",
                    },
                    {
                        "name": "Best Bid",
                        "type": "line",
                        "yAxisIndex": 0,
                        "data": [],
                        "itemStyle": {"color": "#10b981"},
                        "showSymbol": False,
                        "lineStyle": {"width": 2},
                        "step": "end",
                    },
                    {
                        "name": "Spread (bps)",
                        "type": "bar",
                        "yAxisIndex": 1,
                        "data": [],
                        "itemStyle": {"color": "rgba(148, 163, 184, 0.15)"},
                        "barWidth": "70%",
                    },
                ],
                "dataZoom": [{"type": "inside"}, {"type": "slider", "bottom": "2%"}],
            }
        ).classes("w-full h-[450px]")

        chart.set_visibility(False)


# FOREGROUND OVERLAY: Floating Quant AI Assistant
async def send_message():
    user_text = text_input.value.strip()
    if not user_text:
        return
    text_input.value = ""

    with chat_container:
        ui.chat_message(user_text, name="You", sent=True)
        
    # Inject database context into system prompt
    if active_context_state["event"]:
        condensed_l2 = [
            {
                "time": d["timestamp"][11:19], 
                "bid": float(d["bid_price"]), 
                "ask": float(d["ask_price"]), 
                "spread_bps": float(d.get("spread_bps", 0))
            } 
            for d in active_context_state["l2_data"][-MAX_L2_CONTEXT_ROWS:]
        ]
        
        rag_prompt = (
            "You are a quantitative crypto assistant helping analyze Kraken L2 order book snapshots and market news.\n"
            "The user is currently viewing the following market anomaly in the dashboard:\n\n"
            f"EVENT TRIGGER:\n{active_context_state['event']}\n\n"
            f"RECENT L2 ORDER BOOK SAMPLES (latest {MAX_L2_CONTEXT_ROWS} rows):\n{condensed_l2}\n\n"
            "Use this exact data to answer the user's questions about market structure, sentiment, and price action. Do not invent data."
        )
        chat_history[0]["content"] = rag_prompt

    chat_history.append({"role": "user", "content": user_text})
    while len(chat_history) > 2 and (
        len(chat_history) - 1 > MAX_CHAT_HISTORY_MESSAGES
        or sum(len(message["content"]) for message in chat_history[1:]) > MAX_CHAT_HISTORY_CHARS
    ):
        del chat_history[1:3]
    chat_scroll.scroll_to(percent=1.0)

    with chat_container:
        response_msg = ui.chat_message(name="Analyst", sent=False)
        with response_msg:
            response_label = ui.markdown("")

    # stream response from Modal
    full_reply = ""
    try:
        stream = await llm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=chat_history,
            stream=True,
        )
        async for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            full_reply += token
            response_label.set_content(full_reply)
            chat_scroll.scroll_to(percent=1.0)
    except Exception as e:
        response_label.set_content(f"*Error communicating with LLM: {e}*")

    chat_history.append({"role": "assistant", "content": full_reply})


with ui.card().classes(
    "fixed bottom-4 left-1/2 -translate-x-1/2 z-50 "
    "w-[55%] min-w-[420px] max-w-[780px] h-[290px] "
    "flex flex-col no-wrap justify-between p-4 "
    "bg-white/95 backdrop-blur-md shadow-2xl border border-gray-200 rounded-xl"
) as chat_overlay:
    with ui.row().classes("w-full justify-between items-center pb-1 border-b shrink-0"):
        ui.label("Quant AI Assistant").classes("text-base font-bold text-primary")

        def toggle_chat():
            if "h-[290px]" in chat_overlay._classes:
                chat_overlay.classes(remove="h-[290px]", add="h-[56px]")
                chat_scroll.set_visibility(False)
                input_row.set_visibility(False)
                toggle_btn.props("icon=expand_less")
            else:
                chat_overlay.classes(remove="h-[56px]", add="h-[290px]")
                chat_scroll.set_visibility(True)
                input_row.set_visibility(True)
                toggle_btn.props("icon=expand_more")

        toggle_btn = ui.button(icon="expand_more", on_click=toggle_chat).props("flat round dense size=sm")

    with ui.scroll_area().classes("w-full flex-grow min-h-0 my-1 pr-2") as chat_scroll:
        chat_container = ui.column().classes("w-full gap-2")

    with ui.row().classes("w-full no-wrap items-center gap-2 pt-1 shrink-0") as input_row:
        text_input = (
            ui.input(placeholder="Ask about an event...")
            .classes("flex-grow")
            .props("outlined dense rounded")
            .on("keydown.enter", send_message)
        )
        ui.button(icon="send", on_click=send_message).props("round color=primary")


ui.run(port=8088, title="L2 Dashboard", dark=False)