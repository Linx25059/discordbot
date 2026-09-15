import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, set_key, find_dotenv
from utils.db_manager import DatabaseManager
import logging
import traceback
import aiohttp
from logging.handlers import TimedRotatingFileHandler

# 載入 .env 檔案
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# 企業級日誌輪替系統 (避免單一 Log 檔無限膨脹撐爆伺服器硬碟)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d - %(funcName)s): %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
file_handler = TimedRotatingFileHandler('bot_system.log', when='midnight', interval=1, backupCount=7, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# 設定 Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

class TechBot(commands.Bot):
    """自訂機器人類別，託管連線池資源與生命週期優雅關閉機制"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = DatabaseManager('bot_database.db')
        self.session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        # 初始化全域的 HTTP 連線池 (ClientSession)
        self.session = aiohttp.ClientSession()

        # 啟動時先連線資料庫
        await self.db.connect()
        await self.db.init_tables()

        # ⛔ 設定要暫時關閉/停用的模組檔案名稱清單
        ignored_cogs = []

        # 啟動時自動載入 cogs 資料夾內的模組
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename not in ignored_cogs:
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f'已載入模組: {filename}')
                except Exception as e:
                    logging.error(f'載入 {filename} 失敗: {e}')
                    traceback.print_exc()

    async def close(self):
        logging.info("正準備優雅關閉 Bot，釋放連線資源...")
        if self.session and not self.session.closed:
            await self.session.close()
            logging.info("已成功關閉 aiohttp ClientSession")
        if self.db:
            await self.db.close()
            logging.info("已成功關閉 SQLite 資料庫連線")
        await super().close()

# 建立機器人實例
bot = TechBot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    logging.info(f'機器人已登入為 {bot.user}')
    logging.info(f'目前服務於 {len(bot.guilds)} 個伺服器')

# 追蹤使用者執行了什麼指令
@bot.event
async def on_command(ctx):
    logging.info(f'[指令呼叫] 使用者: {ctx.author} (ID: {ctx.author.id}) | 指令: {ctx.command} | 頻道: #{ctx.channel} | 伺服器: {ctx.guild}')

@bot.event
async def on_command_completion(ctx):
    logging.info(f'[指令完成] 使用者: {ctx.author} (ID: {ctx.author.id}) | 指令: {ctx.command}')

# 加入手動同步斜線指令的文字指令
@bot.command(name="sync", help="【機器人擁有者專用】手動同步斜線指令")
@commands.is_owner()
async def sync_commands(ctx, scope: str = ""):
    await ctx.send("⏳ 正在同步斜線指令，這可能需要幾秒鐘...")
    try:
        if scope == "clear":
            bot.tree.clear_commands(guild=ctx.guild)
            await bot.tree.sync(guild=ctx.guild)
            await ctx.send("🧹 已成功清除當前伺服器的專屬指令！（這能完美解決指令重複、舊指令卡住的問題）\n👉 **請按 `Ctrl + R` 或重新載入 Discord 來讓畫面更新。**")
        elif scope == "clear_global":
            bot.tree.clear_commands(guild=None)
            await bot.tree.sync()
            await ctx.send("🧹 已成功清除全域 (Global) 的斜線指令！所有舊的、殘留的斜線指令已從 Discord 官方伺服器移除。")
        elif scope == "here":
            bot.tree.copy_global_to(guild=ctx.guild)
            synced = await bot.tree.sync(guild=ctx.guild)
            await ctx.send(f"✅ 同步完成！已更新 {len(synced)} 個指令。\n👉 **請按 `Ctrl + R` 或重新載入 Discord 來讓指令生效。**")
        else:
            synced = await bot.tree.sync()
            await ctx.send(f"✅ 全域同步完成！已更新 {len(synced)} 個指令。\n⚠️ **注意**：全域同步最多可能需要 1 小時才會完全生效。若急需測試，請使用 `!sync here`。")
    except Exception as e:
        await ctx.send(f"❌ 同步失敗：{e}")

@bot.command(name="update_env", help="【開發者專用】更新或新增 .env 檔案中的環境變數")
@commands.is_owner()
async def update_env(ctx, key: str, value: str):
    dotenv_path = find_dotenv()
    if not dotenv_path:
        # 如果找不到 .env 檔案，就在當前目錄預設建立一個
        dotenv_path = '.env'
        
    # 將新的鍵值對寫入 .env 檔案，並同步更新當下 os.environ 環境變數
    set_key(dotenv_path, key, value)
    os.environ[key] = value
    
    await ctx.send(f"✅ 已成功將環境變數 `{key}` 更新並永久儲存至 `.env` 檔案中！")

if __name__ == "__main__":
    bot.run(TOKEN)