import aiohttp
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class GamerPowerService:
    """負責連線 GamerPower API 抓取限時免費遊戲資訊的服務"""
    API_URL = "https://www.gamerpower.com/api/filter?platform=epic-games-store,steam&type=game"

    @classmethod
    async def fetch_free_games(cls, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """
        獲取目前 Epic Games Store / Steam 的免費遊戲列表
        """
        try:
            async with session.get(cls.API_URL) as resp:
                if resp.status != 200:
                    logger.error(f"GamerPower API 回傳異常狀態碼: {resp.status}")
                    return []

                games = await resp.json()
                if not isinstance(games, list):
                    logger.error(f"GamerPower API 回傳格式非 List 陣列: {games}")
                    return []

                return games
        except Exception as e:
            logger.error(f"抓取 GamerPower 免費遊戲 API 時發生異常: {e}", exc_info=True)
            return []
