import discord
from discord.ext import commands

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="info", aliases=["關於", "botinfo", "介紹"], help="查看機器人的簡單介紹與功能特色")
    async def info(self, ctx):
        embed = discord.Embed(
            title="👋 關於我 (Discord Community Bot)",
            description="我是一個全方位的 Discord 社群多功能機器人，致力於提供最豐富的娛樂體驗與最便利的伺服器管理功能！\n以下是我的核心功能介紹：",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📢 廣播與自動化", 
            value="內建每日新聞與限免遊戲推播 (`/setnews`, `/setgames`)、自訂關鍵字自動回覆 (`/addreply`)，以及能自動產生專屬包廂的動態語音頻道 (`/setupvoice`)。", 
            inline=False
        )
        embed.add_field(
            name="🎁 活動與抽獎", 
            value="支援在頻道內舉辦自訂抽獎活動 (`/giveaway`)！", 
            inline=False
        )
        embed.add_field(
            name="🛠️ 實用管理工具", 
            value="包含完整的管理員功能，如一鍵清頻 (`!clear`)、自動歡迎新成員，以及熱重載機制 (`!hotfix`)，幫助管理員輕鬆維護伺服器。", 
            inline=False
        )
        
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

    @commands.hybrid_command(name="ping", aliases=["延遲"], help="測試機器人的網路連線延遲")
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"目前的系統連線延遲為：`{latency}ms`",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Info(bot))