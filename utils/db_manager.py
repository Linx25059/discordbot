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
        """初始化系統所需的所有核心資料表"""
        await self.db.execute('''CREATE TABLE IF NOT EXISTS achievements (user_id INTEGER, badge TEXT, PRIMARY KEY (user_id, badge))''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS leveling (guild_id INTEGER, user_id INTEGER, xp INTEGER, level INTEGER, PRIMARY KEY (guild_id, user_id))''')
        
        # --- 清除已經棄用的舊版經濟、股市與 AI 成就 ---
        deprecated_badges = ['【天選之人】', '【賭神】', '【股票大亨】', '【AI 詠唱者】', '【大慈善家】', '【破產仔】', '【超級大韭菜】']
        for badge in deprecated_badges:
            await self.db.execute('DELETE FROM achievements WHERE badge = ?', (badge,))
            
        await self.db.commit()

    # --- 🏅 成就系統共用邏輯 ---
    async def check_and_add_achievement(self, user_id: int, badge: str) -> bool:
        """檢查並給予成就。如果獲得新成就，回傳 True；若已擁有則回傳 False"""
        async with self.db.execute('SELECT 1 FROM achievements WHERE user_id = ? AND badge = ?', (user_id, badge)) as cursor:
            if await cursor.fetchone():
                return False
        
        await self.db.execute('INSERT INTO achievements (user_id, badge) VALUES (?, ?)', (user_id, badge))
        await self.db.commit()
        return True
        
    async def get_achievements(self, user_id: int) -> List[str]:
        """取得使用者擁有的所有成就列表"""
        async with self.db.execute('SELECT badge FROM achievements WHERE user_id = ?', (user_id,)) as cursor:
            return [row[0] async for row in cursor]
