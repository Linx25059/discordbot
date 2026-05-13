import discord
from discord.ext import commands

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="info", aliases=["關於", "botinfo", "介紹"], help="查看機器人的簡單介紹與功能特色")
    async def info(self, ctx):
        embed = discord.Embed(
            title="👋 關於我",
            description="我是一個多功能的 Discord 機器人，提供許多實用和娛樂的功能喔！\n無論是想賺金幣、找人聊天，還是聽聽音樂，我都可以幫忙！",
            color=discord.Color.blue()
        )
        embed.add_field(name="💰 經濟系統", value="打工賺錢、轉帳、各種賭場小遊戲，以及具備走勢圖的虛擬股市。", inline=False)
        embed.add_field(name="🤖 AI 聊天", value="內建聰明的 AI 助理，支援多種人格切換（如傲嬌、貓娘），隨時陪你暢聊！", inline=False)
        embed.add_field(name="🎵 音樂與娛樂", value="點播 YouTube 音樂、產生趣味迷因圖，以及專屬的老司機深夜福利推播。", inline=False)
        embed.add_field(name="🛠️ 實用工具", value="天氣查詢、動態語音頻道管理、新聞推播、社群連結自動修復！", inline=False)
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="💡 提示：輸入 `/help` 可以查看完整的指令清單喔！")
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="status", aliases=["狀態", "資訊"], help="查看機器人的連線狀態與版本資訊")
    async def status_command(self, ctx):
        # 從 Help 模組取得目前的版本號
        help_cog = self.bot.get_cog('Help')
        version = help_cog.current_version if help_cog else "未知版本"
        
        embed = discord.Embed(
            title="📈 機器人即時狀態",
            description=f"**目前版本：** `v{version}`\n\n*(如想查看最新的更新內容，可使用 `/changelog`)*",
            color=discord.Color.green()
        )
        
        # 顯示基本的機器人狀態
        embed.add_field(name="🏓 系統延遲", value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)
        embed.add_field(name="🌍 服務伺服器數量", value=f"`{len(self.bot.guilds)}` 個", inline=True)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Info(bot))