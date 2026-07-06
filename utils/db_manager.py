import aiosqlite
from typing import Optional, List

class DatabaseManager:
    """統一管理所有非同步 SQLite 連線與共用邏輯的管理器"""
    def __init__(self, db_path: str = 'bot_database.db'):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        if not self.db:
            self.db = await aiosqlite.connect(self.db_path)

    async def close(self):
        if self.db:
            await self.db.close()

    async def init_tables(self):
        """初始化系統所需的所有核心資料表 (目前各模組獨立建立資料表，此處留空備用)"""
        pass

