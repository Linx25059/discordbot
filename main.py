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

# 建立機器人實例 (指令前綴設為 '!')
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# 初始化全域資料庫管理器
bot.db = DatabaseManager('bot_database.db')

async def setup_bot():
    # 初始化全域的 HTTP 連線池 (ClientSession)，大幅減少 Socket 負擔與建立連線的延遲
    bot.session = aiohttp.ClientSession()

    # 啟動時先連線資料庫，確保所有 Cog 都能直接使用
    await bot.db.connect()
    await bot.db.init_tables()

    # 啟動時自動載入 cogs 資料夾內的模組
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logging.info(f'已載入模組: {filename}')
            except Exception as e:
                logging.error(f'載入 {filename} 失敗: {e}')
                traceback.print_exc()  # 🛡️ 防禦：印出完整的錯誤堆疊，秒速抓漏
                
    # ⚠️ 為了避免觸發 Discord 429 速率限制，我們將自動同步關閉，改為使用 !sync 指令手動同步
    # try:
    #     synced = await bot.tree.sync()
    #     print(f"✅ 已成功同步 {len(synced)} 個斜線指令！")
    # except Exception as e:
    #     print(f"❌ 斜線指令同步失敗: {e}")

bot.setup_hook = setup_bot

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

# 🛡️ 全域錯誤處理：捕捉錯誤並給予友善提示，避免機器人崩潰
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # 忽略找不到指令的錯誤
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ 您沒有權限執行此指令！")
    else:
        logging.error(f'執行指令 {ctx.command} 時發生錯誤: {error}')
        traceback.print_exception(type(error), error, error.__traceback__)
        await ctx.send("⚠️ 發生未預期的錯誤，請聯絡開發人員。")

# 加入手動同步斜線指令的文字指令
@bot.command(name="sync", help="【管理員專用】手動同步斜線指令")
@commands.has_permissions(administrator=True)
async def sync_commands(ctx, scope: str = ""):
    await ctx.send("⏳ 正在同步斜線指令，這可能需要幾秒鐘...")
    try:
        if scope == "clear":
            bot.tree.clear_commands(guild=ctx.guild)
            await bot.tree.sync(guild=ctx.guild)
            await ctx.send("🧹 已成功清除當前伺服器的專屬指令！（這能完美解決指令重複、舊指令卡住的問題）\n👉 **請按 `Ctrl + R` 或重新載入 Discord 來讓畫面更新。**")
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