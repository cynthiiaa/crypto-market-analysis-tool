import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import os
    import marimo as mo
    import pandas as pd
    from dotenv import load_dotenv
    import plotly.graph_objects as go
    from supabase import create_client

    load_dotenv()
    return create_client, go, mo, os, pd


@app.cell
def _(create_client, os, pd):
    supabase = create_client(supabase_url=os.environ["SUPABASE_URL"], supabase_key=os.environ["SUPABASE_KEY"])
    response = supabase.table("market_events").select("*").order("created_at", desc=True).limit(50).execute()
    events_df = pd.DataFrame(response.data)

    event_options = {
        f"{row['asset']} | Sentiment: {row['vllm_sentiment_score']} | {(row['raw_text'] or '')[:40]}... ({str(row['id'])[:6]})": row["id"]
        for _, row in events_df.iterrows()
    }
    return event_options, supabase


@app.cell
def _(event_options, mo):
    mo.md("## Select a Market Event to Analyze")
    event_selector = mo.ui.dropdown(
        options=event_options.keys(),
        value=list(event_options.keys())[0] if event_options else None,
        label="Breaking News Event:"
    )
    event_selector
    return (event_selector,)


@app.cell
def _(event_options, event_selector, pd, supabase):
    event_id = event_options.get(event_selector.value)
    if event_id:
        l2_response = supabase.table("liquidity_snapshots").select("*").eq("event_id", event_id).order("timestamp").execute()
        l2_df = pd.DataFrame(l2_response.data)
        if not l2_df.empty:
            l2_df["timestamp"] = pd.to_datetime(l2_df["timestamp"])
    else:
        l2_df = pd.DataFrame()
    return (l2_df,)


@app.cell
def _(go, l2_df, mo):
    if not l2_df.empty:
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=l2_df["timestamp"], y=l2_df["ask_price"],
            mode="lines", name="Best Ask", line=dict(color="red", width=2)
        ))

        fig.add_trace(go.Scatter(
            x=l2_df["timestamp"], y=l2_df["bid_price"],
            mode="lines", name="Best Bid", line=dict(color="green", width=2)
        ))

        fig.update_layout(
            title="L2 Book Depth Analysis",
            xaxis_title="Time",
            yaxis_title="Price (USD)",
            template="plotly_dark",
            hovermode="x unified",
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )

        view = mo.ui.plotly(fig)
    else:
        view = mo.md("*Waiting for event data...*")
    return (view,)


@app.cell
def _(view):
    view
    return


if __name__ == "__main__":
    app.run()
