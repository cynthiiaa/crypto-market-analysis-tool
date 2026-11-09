import asyncio
import logging
from src.crypto_analysis_tool.l2_book import KrakenL2Buffer
from src.crypto_analysis_tool.news_feed import poll_news_feed

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[
                        logging.FileHandler("quant_pipeline.log"),  
                        logging.StreamHandler()                    
                    ]
                )
logger = logging.getLogger(__name__)

async def main():
    shared_l2_buffer = asyncio.Queue()
    logger.info("Booting Event-Driven Liquidity Pipeline...")
    try:
        kraken_buffer = KrakenL2Buffer()
        await asyncio.gather(kraken_buffer.connect_and_listen(shared_l2_buffer), poll_news_feed(shared_l2_buffer))
    except asyncio.CancelledError:
        logger.info("Pipeline shut down safely")
    except Exception as e:
        logger.error(f"FATAL: Pipeline crashed due to: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())