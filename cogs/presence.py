import discord
from discord.ext import commands, tasks
import itertools
import logging

class DynamicPresence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 定義想要輪播的狀態 (可以自由新增或修改)
        self.status_cycle = itertools.cycle([
            discord.Game(name="!help | 獲取幫助"),
            discord.Activity(type=discord.ActivityType.listening, name="使用者的呼喚"),
            "DYNAMIC_GUILD_COUNT"  # 這是一個特殊標記，我們會在下方動態轉換它
        ])
        # 啟動背景迴圈
        self.change_status.start()

    def cog_unload(self):
        # 當模組被卸載時 (例如使用 reload 時)，停止迴圈以避免重複執行
        self.change_status.cancel()

    @tasks.loop(minutes=5)  # 設定每 5 分鐘切換一次狀態
    async def change_status(self):
        status = next(self.status_cycle)
        
        # 如果遇到特殊標記，就動態抓取目前的伺服器數量
        if status == "DYNAMIC_GUILD_COUNT":
            activity = discord.Activity(
                type=discord.ActivityType.watching, 
                name=f"{len(self.bot.guilds)} 個伺服器"
            )
        else:
            activity = status
            
        await self.bot.change_presence(activity=activity)

    @change_status.before_loop
    async def before_change_status(self):
        # 等待機器人完全準備好後才開始執行迴圈，避免剛啟動時抓不到伺服器資料
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(DynamicPresence(bot))