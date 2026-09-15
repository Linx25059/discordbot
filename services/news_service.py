import aiohttp
import xml.etree.ElementTree as ET
import asyncio
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

class NewsService:
    """負責抓取與解析新聞 RSS 訂閱的服務"""
    GOOGLE_NEWS_RSS_URL = 'https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant'

    @classmethod
    async def fetch_top_news(cls, session: aiohttp.ClientSession, limit: int = 5) -> List[Tuple[str, str]]:
        """
        獲取熱門新聞標題與連結 [(title, link), ...]
        """
        try:
            async with session.get(cls.GOOGLE_NEWS_RSS_URL) as resp:
                if resp.status != 200:
                    logger.error(f"Google News RSS 回傳異常狀態碼: {resp.status}")
                    return []

                xml_data = await resp.text()
                loop = asyncio.get_running_loop()
                root = await loop.run_in_executor(None, ET.fromstring, xml_data)

                news_items = []
                for i, item in enumerate(root.findall('./channel/item')):
                    if i >= limit:
                        break
                    title_elem = item.find('title')
                    link_elem = item.find('link')
                    if title_elem is not None and link_elem is not None:
                        news_items.append((title_elem.text, link_elem.text))
                return news_items
        except Exception as e:
            logger.error(f"抓取 Google 新聞 RSS 時發生異常: {e}", exc_info=True)
            return []
