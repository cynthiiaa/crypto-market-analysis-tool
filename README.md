# Event-Driven Crypto Market Analysis Tool

## Goal
Create a lightweight, automated pipeline that captures both high-frequency crypto market data and high-signal news events.

## Tech Stack:
**Compute:** Digital Ocean GPU Droplet
**AI Inference:** vLLM and Modal
**Database:** Supabase
**Dependency Management:** uv
**Data Feeds:** Kraken WebSocket API and Crypto News RSS Feeds

### Modal
Modal is a code-first approach to setting up cloud infrastructure like GPUs, network ports, and container dependencies. If you aren't a fan of messing around with stack files Dockerfiles/YAML files then consider tinkering with Modal.

Also, Modal functions are serverless, so GPU will spin down completely when there's no new events to process.

```bash
# installing Modal
uv add modal

# authenticating with Modal
python -m modal setup

# deploying to the cloud
modal deploy <APP_SCRIPT>
```

Python is insufferable when it comes to finding local packages
```bash
PYTHONPATH=. uv run src/crypto_analysis_tool/main.py
```