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
            name="🤖 智慧 AI 助理", 
            value="內建 Google Gemini 2.5 Flash 模型，支援即時聯網搜尋。\n不僅能精準解答問題，還能透過 `/set_persona` 自由切換「傲嬌、毒舌、貓娘」等多重聊天人格，陪你無話不談！", 
            inline=False
        )
        embed.add_field(
            name="💹 經濟與虛擬股市", 
            value="體驗完整的虛擬人生！透過 `/work` 打工賺錢，並將現金存入銀行 (`/deposit`) 賺取每日利息。\n在賭場裡遊玩 21點、拉霸機等小遊戲，還有具備即時歷史折線圖的虛擬股市系統，讓你體驗低買高賣的快感！", 
            inline=False
        )
        embed.add_field(
            name="🎵 影音與趣味互動", 
            value="支援高音質 YouTube 音樂點播 (`/play`)，帶有控制面板與待播清單。\n提供多種惡搞頭貼指令 (`/pixelate` 等) 與迷因圖產生器。還有專屬的美食與手搖飲推薦 (`/eat`, `/drink`)、金幣抽獎 (`/giveaway`) 與趣味計數排行 (`/jerkboard`)！", 
            inline=False
        )
        embed.add_field(
            name="🛠️ 實用工具與管理", 
            value="內建自訂關鍵字回覆 (`/addreply`) 與完整的伺服器日誌系統 (`/setlog`)。\n自動修復社群連結預覽、自動建立動態語音頻道，並支援報錯單 (Ticket) 系統與天氣推播，幫助管理員輕鬆維護伺服器。", 
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

async def setup(bot):
    await bot.add_cog(Info(bot))