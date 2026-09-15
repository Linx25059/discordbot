import pytest
import pytest_asyncio
import os
import aiohttp
from services.news_service import NewsService
from services.game_service import GamerPowerService
from utils.db_manager import DatabaseManager

@pytest.mark.asyncio
async def test_db_manager_lifecycle():
    test_db_path = "test_temp.db"
    db_mgr = DatabaseManager(test_db_path)
    await db_mgr.connect()
    assert db_mgr.db is not None

    await db_mgr.init_tables()
    
    # 測試 Weather CRUD API
    await db_mgr.set_user_weather_location(123456789, "台北")
    loc = await db_mgr.get_user_weather_location(123456789)
    assert loc == "台北"
    
    await db_mgr.close()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

@pytest.mark.asyncio
async def test_news_service_parsing():
    async with aiohttp.ClientSession() as session:
        news = await NewsService.fetch_top_news(session)
        assert isinstance(news, list)

@pytest.mark.asyncio
async def test_game_service_parsing():
    async with aiohttp.ClientSession() as session:
        games = await GamerPowerService.fetch_free_games(session)
        assert isinstance(games, list)

