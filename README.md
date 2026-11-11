# Event-Driven Crypto Market Analysis Tool

## Goal
Create a lightweight, automated pipeline that captures both high-frequency crypto market data and high-signal news events.

## Caveat
Right now I'm only tracking Bitcoin against the USD. I plan to add other coins later.

## Tech Stack:
**Compute:** Digital Ocean GPU Droplet

**AI Inference:** vLLM and Modal

**Database:** Supabase

**Dependency Management:** uv

**Data Feeds:** Kraken WebSocket API and Crypto News RSS Feeds

**UI**: niceGUI

## Scripts
### `src/crypto_analysis_tool/...`
`main.py`: Entry point of the pipeline.

#### Infrastructure
`database.py`: Writes to the `market_events` and `liquidity_snapshots` tables in Supabase.

`modal_setup.py`: Setup the Modal vLLM endpoint. I'm using **meta-llama/Llama-3.1-8B-Instruct**.

#### Data
`l2_book.py`: Connect to Kraken L2 data to derive **best_bid**, **best_ask**, and aggregate **basis_points**.

`news_feed.py`: Sending crypto news feeds to the LLM to rank each event on whether or not it's actionable.

## What I Have So Far

![alt text](./src/assets/image.gif "Quick Demo of Project")

### Modal
Modal is a code-first approach to setting up cloud infrastructure like GPUs, network ports, and container dependencies. If you aren't a fan of messing around with static files like Dockerfiles/YAML files then consider tinkering with Modal.

Also, Modal functions are serverless, so GPU will spin down completely when there's no new events to process.

```bash
# installing Modal
uv add modal

# authenticating with Modal
python -m modal setup

# deploying to the cloud
modal deploy <APP_SCRIPT>
```

Python is insufferable when it comes to finding local packages 🤦🏾‍♀️
```bash
PYTHONPATH=. uv run src/crypto_analysis_tool/main.py
```

## Future Goals
Eventually, when I get enough data, I might fine tune a small model instead of relying on prompt engineering. Basically, I want to change the underlying behavior of the LLM to align with this project rather than using a general model and prompting my way to a "good enough" solution.