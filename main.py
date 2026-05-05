import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# 設定 Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# 建立機器人實例 (指令前綴設為 '!')
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

async def setup_bot():
    # 啟動時自動載入 cogs 資料夾內的模組
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'已載入模組: {filename}')
            except Exception as e:
                print(f'載入 {filename} 失敗: {e}')
                
    # 同步斜線指令 (Slash Commands) 到 Discord 伺服器
    try:
        synced = await bot.tree.sync()
        print(f"✅ 已成功同步 {len(synced)} 個斜線指令！")
    except Exception as e:
        print(f"❌ 斜線指令同步失敗: {e}")

bot.setup_hook = setup_bot

@bot.event
async def on_ready():
    print(f'機器人已登入為 {bot.user}')

if __name__ == "__main__":
    bot.run(TOKEN)