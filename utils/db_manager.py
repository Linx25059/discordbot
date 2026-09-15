import aiosqlite
from typing import Optional, List, Tuple

class DatabaseManager:
    """統一管理所有非同步 SQLite 連線、Schema 初始化與共用資料 CRUD 的管理器"""
    def __init__(self, db_path: str = 'bot_database.db'):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        if not self.db:
            self.db = await aiosqlite.connect(self.db_path, timeout=10.0)
            await self.db.execute("PRAGMA journal_mode=WAL;")
            await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    async def init_tables(self):
        """初始化系統所需的所有核心資料表並執行 Schema 遷移"""
        if not self.db:
            return

        # 1. Weather
        await self.db.execute('''CREATE TABLE IF NOT EXISTS user_weather_location (user_id INTEGER PRIMARY KEY, location TEXT)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS daily_weather_subs (user_id INTEGER PRIMARY KEY)''')

        # 2. Broadcast
        await self.db.execute('''CREATE TABLE IF NOT EXISTS news_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS games_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS free_games (game_id TEXT PRIMARY KEY)''')

        # 3. Game Panel
        await self.db.execute('''CREATE TABLE IF NOT EXISTS server_games (guild_id INTEGER, game_name TEXT)''')

        # 4. Logger & Help / Update
        await self.db.execute('''CREATE TABLE IF NOT EXISTS log_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS update_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, last_version TEXT)''')

        # 5. Translation
        await self.db.execute('''CREATE TABLE IF NOT EXISTS translation_channels (
            guild_id INTEGER,
            channel_id INTEGER PRIMARY KEY,
            target_language TEXT
        )''')

        # 6. Auto Voice
        await self.db.execute('''CREATE TABLE IF NOT EXISTS auto_voice_generators (channel_id INTEGER PRIMARY KEY)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS auto_voice_temp (channel_id INTEGER PRIMARY KEY)''')

        # 7. Auto Reply Schema 檢查與遷移
        async with self.db.execute("PRAGMA table_info(auto_replies)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]

        if columns and "guild_id" not in columns:
            await self.db.execute("ALTER TABLE auto_replies RENAME TO auto_replies_backup")
            await self.db.execute('''CREATE TABLE auto_replies (guild_id INTEGER, keyword TEXT, reply TEXT, PRIMARY KEY (guild_id, keyword))''')
            await self.db.execute("INSERT INTO auto_replies (guild_id, keyword, reply) SELECT 0, keyword, reply FROM auto_replies_backup")
            await self.db.execute("DROP TABLE auto_replies_backup")

        await self.db.execute('''CREATE TABLE IF NOT EXISTS auto_replies (guild_id INTEGER, keyword TEXT, reply TEXT, PRIMARY KEY (guild_id, keyword))''')
        await self.db.execute("DROP TABLE IF EXISTS server_auto_replies")

        await self.db.commit()

    # ==================== 1. Weather CRUD ====================
    async def set_user_weather_location(self, user_id: int, location: str):
        await self.db.execute('INSERT OR REPLACE INTO user_weather_location (user_id, location) VALUES (?, ?)', (user_id, location))
        await self.db.commit()

    async def get_user_weather_location(self, user_id: int) -> Optional[str]:
        async with self.db.execute('SELECT location FROM user_weather_location WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def toggle_daily_weather_sub(self, user_id: int) -> bool:
        """切換訂閱狀態，回傳 True 表示開啟，False 表示關閉"""
        async with self.db.execute('SELECT 1 FROM daily_weather_subs WHERE user_id = ?', (user_id,)) as cursor:
            is_sub = await cursor.fetchone()

        if is_sub:
            await self.db.execute('DELETE FROM daily_weather_subs WHERE user_id = ?', (user_id,))
            await self.db.commit()
            return False
        else:
            await self.db.execute('INSERT INTO daily_weather_subs (user_id) VALUES (?)', (user_id,))
            await self.db.commit()
            return True

    async def get_daily_weather_subs(self) -> List[Tuple[int, Optional[str]]]:
        async with self.db.execute('''
            SELECT s.user_id, l.location 
            FROM daily_weather_subs s 
            LEFT JOIN user_weather_location l ON s.user_id = l.user_id
        ''') as cursor:
            return await cursor.fetchall()

    # ==================== 2. Broadcast CRUD ====================
    async def set_news_channel(self, guild_id: int, channel_id: int):
        await self.db.execute('INSERT OR REPLACE INTO news_settings (guild_id, channel_id) VALUES (?, ?)', (guild_id, channel_id))
        await self.db.commit()

    async def get_news_channels(self) -> List[int]:
        async with self.db.execute('SELECT channel_id FROM news_settings') as cursor:
            return [row[0] async for row in cursor]

    async def set_games_channel(self, guild_id: int, channel_id: int):
        await self.db.execute('INSERT OR REPLACE INTO games_settings (guild_id, channel_id) VALUES (?, ?)', (guild_id, channel_id))
        await self.db.commit()

    async def get_games_channels(self) -> List[int]:
        async with self.db.execute('SELECT channel_id FROM games_settings') as cursor:
            return [row[0] async for row in cursor]

    async def is_free_game_sent(self, game_id: str) -> bool:
        async with self.db.execute('SELECT 1 FROM free_games WHERE game_id = ?', (game_id,)) as cursor:
            return await cursor.fetchone() is not None

    async def add_free_game(self, game_id: str):
        await self.db.execute('INSERT INTO free_games (game_id) VALUES (?)', (game_id,))
        await self.db.commit()

    # ==================== 3. Game Panel CRUD ====================
    async def has_server_game(self, guild_id: int, game_name: str) -> bool:
        async with self.db.execute('SELECT 1 FROM server_games WHERE guild_id = ? AND game_name = ?', (guild_id, game_name)) as cursor:
            return await cursor.fetchone() is not None

    async def get_server_games_count(self, guild_id: int) -> int:
        async with self.db.execute('SELECT COUNT(*) FROM server_games WHERE guild_id = ?', (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def add_server_game(self, guild_id: int, game_name: str):
        await self.db.execute('INSERT INTO server_games (guild_id, game_name) VALUES (?, ?)', (guild_id, game_name))
        await self.db.commit()

    async def remove_server_game(self, guild_id: int, game_name: str):
        await self.db.execute('DELETE FROM server_games WHERE guild_id = ? AND game_name = ?', (guild_id, game_name))
        await self.db.commit()

    async def get_server_games(self, guild_id: int) -> List[str]:
        async with self.db.execute('SELECT game_name FROM server_games WHERE guild_id = ?', (guild_id,)) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

    # ==================== 4. Logger & Help CRUD ====================
    async def set_log_channel(self, guild_id: int, channel_id: int):
        await self.db.execute('INSERT OR REPLACE INTO log_settings (guild_id, channel_id) VALUES (?, ?)', (guild_id, channel_id))
        await self.db.commit()

    async def get_log_channel(self, guild_id: int) -> Optional[int]:
        async with self.db.execute('SELECT channel_id FROM log_settings WHERE guild_id = ?', (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_update_channel(self, guild_id: int, channel_id: int, version: str):
        await self.db.execute('INSERT OR REPLACE INTO update_settings (guild_id, channel_id, last_version) VALUES (?, ?, ?)', (guild_id, channel_id, version))
        await self.db.commit()

    async def get_all_update_settings(self) -> List[Tuple[int, int, Optional[str]]]:
        async with self.db.execute('SELECT guild_id, channel_id, last_version FROM update_settings') as cursor:
            return await cursor.fetchall()

    async def update_last_version(self, guild_id: int, version: str):
        await self.db.execute('UPDATE update_settings SET last_version = ? WHERE guild_id = ?', (version, guild_id))
        await self.db.commit()

    # ==================== 5. Translation CRUD ====================
    async def set_translation_channel(self, guild_id: int, channel_id: int, target_lang: str):
        await self.db.execute('INSERT OR REPLACE INTO translation_channels (guild_id, channel_id, target_language) VALUES (?, ?, ?)', (guild_id, channel_id, target_lang))
        await self.db.commit()

    async def remove_translation_channel(self, channel_id: int):
        await self.db.execute('DELETE FROM translation_channels WHERE channel_id = ?', (channel_id,))
        await self.db.commit()

    async def get_translation_channel_lang(self, channel_id: int) -> Optional[str]:
        async with self.db.execute('SELECT target_language FROM translation_channels WHERE channel_id = ?', (channel_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_guild_translation_channels(self, guild_id: int) -> List[Tuple[int, str]]:
        async with self.db.execute('SELECT channel_id, target_language FROM translation_channels WHERE guild_id = ?', (guild_id,)) as cursor:
            return await cursor.fetchall()

    # ==================== 6. Auto Voice CRUD ====================
    async def add_auto_voice_generator(self, channel_id: int):
        await self.db.execute('INSERT OR IGNORE INTO auto_voice_generators (channel_id) VALUES (?)', (channel_id,))
        await self.db.commit()

    async def is_auto_voice_generator(self, channel_id: int) -> bool:
        async with self.db.execute('SELECT 1 FROM auto_voice_generators WHERE channel_id = ?', (channel_id,)) as cursor:
            return await cursor.fetchone() is not None

    async def add_auto_voice_temp(self, channel_id: int):
        await self.db.execute('INSERT INTO auto_voice_temp (channel_id) VALUES (?)', (channel_id,))
        await self.db.commit()

    async def is_auto_voice_temp(self, channel_id: int) -> bool:
        async with self.db.execute('SELECT 1 FROM auto_voice_temp WHERE channel_id = ?', (channel_id,)) as cursor:
            return await cursor.fetchone() is not None

    async def remove_auto_voice_temp(self, channel_id: int):
        await self.db.execute('DELETE FROM auto_voice_temp WHERE channel_id = ?', (channel_id,))
        await self.db.commit()

    # ==================== 7. Auto Reply CRUD ====================
    async def add_auto_reply(self, guild_id: int, keyword: str, reply: str):
        await self.db.execute('INSERT OR REPLACE INTO auto_replies (guild_id, keyword, reply) VALUES (?, ?, ?)', (guild_id, keyword, reply))
        await self.db.commit()

    async def remove_auto_reply(self, guild_id: int, keyword: str):
        await self.db.execute('DELETE FROM auto_replies WHERE guild_id = ? AND keyword = ?', (guild_id, keyword))
        await self.db.commit()

    async def check_auto_reply_exists(self, guild_id: int, keyword: str) -> bool:
        async with self.db.execute('SELECT 1 FROM auto_replies WHERE guild_id = ? AND keyword = ?', (guild_id, keyword)) as cursor:
            return await cursor.fetchone() is not None

    async def get_matching_auto_replies(self, guild_id: int) -> List[Tuple[str, str]]:
        async with self.db.execute('SELECT keyword, reply FROM auto_replies WHERE guild_id = ? OR guild_id = 0', (guild_id,)) as cursor:
            return await cursor.fetchall()

    async def get_guild_auto_replies(self, guild_id: int) -> List[Tuple[int, str, str]]:
        async with self.db.execute('SELECT guild_id, keyword, reply FROM auto_replies WHERE guild_id = ? OR guild_id = 0', (guild_id,)) as cursor:
            return await cursor.fetchall()


