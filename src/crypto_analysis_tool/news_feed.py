import os
import asyncio
import aiohttp
import json
import logging
from dotenv import load_dotenv
from src.crypto_analysis_tool.database import flush_to_supabase

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

CRYPTO_NEWS_URL = os.environ["CRYPTO_NEWS_URL"]
MODAL_URL = os.environ["MODAL_URL"]
SYSTEM_PROMPT = """
You are a quantitative crypto analyst. Your job is to extract structured entity data and sentiment from raw crypto news.

CRYPTO SLANG DICTIONARY:
- "Rug Pull" / "REKT": A scam or devastating loss. Extreme bearish sentiment (-10). Maps to HACK_OR_EXPLOIT.
- "Whale": A trader with massive capital. If they are moving funds TO an exchange, it's bearish. If OFF an exchange, it's bullish. Maps to ON_CHAIN_WHALE_MOVEMENT.
- "Goblin Town": A sustained, brutal bear market or price crash. Highly bearish (-8).
- "HODL" / "Buy the F*ing Dip (BTFD)": Retail accumulation during a crash. Usually neutral or slightly bullish sentiment, but rarely actionable for market makers. Maps to NOISE.
- "When Lambo" / "When Moon" / "Money Printer Go Brrr": Extreme retail euphoria. Bullish sentiment (+8). 
- "Degen": High-risk retail speculation. Maps to NOISE unless tied to a specific smart contract exploit.
- "Altseason": When capital rotates from Bitcoin into smaller altcoins. Bullish for the specific altcoin mentioned.
- "Tokenization" / "RWA" / "SEC Exemption": TradFi institutional adoption of blockchain. Highly bullish (+8). Maps to INSTITUTIONAL_ADOPTION or EXCHANGE_LISTING.

RULES:
1. Extract the primary asset ticker.
2. Determine the core event category.
3. Score the immediate market sentiment (-10 to 10).
4. Flag if this is a high-volatility actionable event (e.g., Hacks, Exchange Listings).
5. If the text is just general commentary or opinion, categorize as NOISE.

OUTPUT FORMAT:
You must return ONLY a valid JSON object using this exact schema:
{
    "primary_asset_ticker": STRING,
    "core_event_category": STRING,
    "sentiment": INT,
    "is_actionable_event": BOOLEAN,
    "high_volatility_event": BOOLEAN,
    "event_description": STRING
}
If the headline is spam or macro news, set "core_event_category" to "NOISE" and "high_volatility_event" to false.
"""

seen_articles = set() # don't want duplicate articles read

async def analyze_headline(session, title):
    """Send headlines to Modal vLLM endpoint for classification."""
    payload = {
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": title}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": "Bearer dummy-token",
        "Content-Type": "application/json"
    }

    try:
        async with session.post(MODAL_URL, json=payload, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                return json.loads(result["choices"][0]["message"]["content"])
    except Exception as e:
        logger.error(f"Error with vLLM: {e}")
    return None

async def poll_news_feed(shared_buffer):
    logger.info("\nBooting up news aggregator...")

    async with aiohttp.ClientSession() as session:
        # populate the seen_articles with historical articles
        try:
            async with session.get(CRYPTO_NEWS_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    for article in data.get("articles", []):
                        article_id = article.get("pubDate", "") + article.get("source", "")
                        if article_id:
                            seen_articles.add(article_id)

                    logger.info(f"\nLoaded {len(seen_articles)} historical articles. Now listening for breaking news...")
        except Exception as e:
            logger.error(f"\nError fetching initial cache: {e}")

        # continuous polling
        while True:
            try:
                async with session.get(CRYPTO_NEWS_URL) as response:
                    if response.status == 200:
                        data = await response.json()

                        for article in data.get("articles"):
                            article_id = article.get("pubDate") + article.get("source")

                            if article_id and article_id not in seen_articles:
                                seen_articles.add(article_id)

                                title = article.get("title", "No Title")
                                logger.info(f"\nBreaking News: {title}")

                                # send headline to vLLM endpoint
                                analysis = await analyze_headline(session, title)

                                if analysis and analysis.get("events"):
                                    for event in analysis["events"]:
                                        if event.get("is_actionable"):
                                            logger.info(f"ACTIONABLE EVENT DETECTED: {event.get('primary_asset_ticker')} | Sentiment: {event.get('sentiment_score')}")
                                            
                                            flushed_metrics = []
                                            while not shared_buffer.empty():
                                                try:
                                                    metric = shared_buffer.get_nowait()
                                                    flushed_metrics.append(metric)
                                                    shared_buffer.task_done()
                                                except asyncio.QueueEmpty:
                                                    break

                                            flush_to_supabase(analysis, title, flushed_metrics)
            
            except Exception as e:
                logger.error(f"Error polling API: {e}")

            # poll every 15 seconds
            await asyncio.sleep(15)

if __name__ == "__main__":
    asyncio.run(poll_news_feed())

 