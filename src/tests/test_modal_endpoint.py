import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODAL_URL = os.environ["MODAL_URL_TEST"]
SYSTEM_PROMPT = """
You are a quantitative crypto analyst. Your job is to extract structured entity data and sentiment from raw crypto news, tweets, and on-chain alerts.

CRYPTO SLANG DICTIONARY:
- "Rug Pull" / "REKT": A scam or devastating loss. Extreme bearish sentiment (-10). Maps to HACK_OR_EXPLOIT.
- "Whale": A trader with massive capital. If they are moving funds TO an exchange, it's bearish. If OFF an exchange, it's bullish. Maps to ON_CHAIN_WHALE_MOVEMENT.
- "Goblin Town": A sustained, brutal bear market or price crash. Highly bearish (-8).
- "HODL" / "Buy the F*ing Dip (BTFD)": Retail accumulation during a crash. Usually neutral or slightly bullish sentiment, but rarely actionable for market makers. Maps to NOISE.
- "When Lambo" / "When Moon" / "Money Printer Go Brrr": Extreme retail euphoria. Bullish sentiment (+8). 
- "Degen": High-risk retail speculation. Maps to NOISE unless tied to a specific smart contract exploit.
- "Altseason": When capital rotates from Bitcoin into smaller altcoins. Bullish for the specific altcoin mentioned.

RULES:
1. Extract the primary asset ticker.
2. Determine the core event category.
3. Score the immediate market sentiment (-10 to 10).
4. Flag if this is a high-volatility actionable event (e.g., Hacks, Exchange Listings).
5. If the text is just spam, retail chatter, or meme phrases without a catalyst, categorize as NOISE with an empty list.
"""

client = OpenAI(base_url=MODAL_URL, api_key="don't-got-one")
response = client.chat.completions.create(model="meta-llama/Llama-3.1-8B-Instruct",
                                    messages=[
                                        {"role": "system", "content": SYSTEM_PROMPT},
                                        {"role": "user", "content": "Extract data: $100M BTC stolen from major exchange."}
                                    ]
                                )

print(response.choices[0].message.content)