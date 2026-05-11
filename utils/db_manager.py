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
        await self.db.execute('''CREATE TABLE IF NOT EXISTS economy (user_id INTEGER PRIMARY KEY, balance INTEGER)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item_name TEXT, amount INTEGER)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS achievements (user_id INTEGER, badge TEXT, PRIMARY KEY (user_id, badge))''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS virtual_stocks (symbol TEXT PRIMARY KEY, name TEXT, price INTEGER, prev_price INTEGER, next_price INTEGER)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS leveling (guild_id INTEGER, user_id INTEGER, xp INTEGER, level INTEGER, PRIMARY KEY (guild_id, user_id))''')
        await self.db.commit()

    # --- 💰 經濟系統共用邏輯 ---
    async def get_balance(self, user_id: int) -> int:
        async with self.db.execute('SELECT balance FROM economy WHERE user_id = ?', (user_id,)) as cursor:
            result = await cursor.fetchone()
        if result is None:
            await self.db.execute('INSERT INTO economy (user_id, balance) VALUES (?, ?)', (user_id, 0))
            await self.db.commit()
            return 0
        return result[0]

    async def update_balance(self, user_id: int, amount: int) -> int:
        balance = await self.get_balance(user_id)
        new_balance = balance + amount
        await self.db.execute('UPDATE economy SET balance = ? WHERE user_id = ?', (new_balance, user_id))
        await self.db.commit()
        return new_balance

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
