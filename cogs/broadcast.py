import discord
from discord.ext import commands, tasks
import datetime
import logging
from services.news_service import NewsService
from services.game_service import GamerPowerService

logger = logging.getLogger(__name__)

class Broadcast(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # 啟動自動排程任務
        self.daily_news.start()
        self.check_free_games.start()

    async def cog_load(self):
        pass
        
    def cog_unload(self):
        # 模組卸載時，停止任務
        self.daily_news.cancel()
        self.check_free_games.cancel()

    # 取得有設定新聞推播的頻道清單
    async def get_news_channels(self):
        return await self.bot.db.get_news_channels()

    # 取得有設定免費遊戲推播的頻道清單
    async def get_games_channels(self):
        return await self.bot.db.get_games_channels()

    # 🛠️ 管理員指令：設定新聞頻道
    @commands.hybrid_command(name="setnews", aliases=["設定新聞"], help="設定當前頻道為「每日新聞」自動推播頻道")
    @commands.has_permissions(manage_channels=True)
    async def set_news(self, ctx):
        guild_id = ctx.guild.id
        channel_id = ctx.channel.id
        
        await self.bot.db.set_news_channel(guild_id, channel_id)
        
        embed = discord.Embed(title="📡 新聞頻道設定成功", description=f"已經把 {ctx.channel.mention} 設為新聞頻道囉！\n每天早上 8 點會幫大家整理最新新聞。", color=discord.Color.green())
        await ctx.send(embed=embed)

    # 🛠️ 管理員指令：設定免費遊戲頻道
    @commands.hybrid_command(name="setgames", aliases=["設定免費遊戲"], help="設定當前頻道為「限時免費遊戲」推播頻道")
    @commands.has_permissions(manage_channels=True)
    async def set_games(self, ctx):
        guild_id = ctx.guild.id
        channel_id = ctx.channel.id
        
        await self.bot.db.set_games_channel(guild_id, channel_id)
        
        embed = discord.Embed(title="🎮 免費遊戲推播設定成功", description=f"已經把 {ctx.channel.mention} 設為免費遊戲通知頻道囉！\n只要有免費遊戲都會擴發通知大家。", color=discord.Color.blue())
        await ctx.send(embed=embed)

    # ⏰ 任務 1：每天早上 8 點 (台灣時間 UTC+8) 推播新聞與天氣
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    @tasks.loop(time=datetime.time(hour=8, minute=0, second=0, tzinfo=tz_tw))
    async def daily_news(self):
        channels = await self.get_news_channels()
        if not channels:
            return

        try:
            news_items = await NewsService.fetch_top_news(self.bot.session, limit=5)
            if not news_items:
                return

            embed = discord.Embed(title="☀️ 早安！今日重點新聞", description="為大家整理今天的熱門新聞：", color=discord.Color.gold())
            for title, link in news_items:
                embed.add_field(name=f"🗞️ {title}", value=f"[點擊閱讀詳細內容]({link})", inline=False)
            
            embed.set_footer(text="新聞來源：Google 新聞")

            for channel_id in channels:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"每日新聞推播任務發生異常: {e}", exc_info=True)

    @daily_news.before_loop
    async def before_daily_news(self):
        await self.bot.wait_until_ready()

    # ⏰ 任務 2：每 2 小時檢查一次有沒有新的免費遊戲
    @tasks.loop(hours=2)
    async def check_free_games(self):
        channels = await self.get_games_channels()
        if not channels:
            return

        try:
            games = await GamerPowerService.fetch_free_games(self.bot.session)
            for game in games:
                game_id = str(game.get('id'))
                
                is_sent = await self.bot.db.is_free_game_sent(game_id)
                if not is_sent:
                    embed = discord.Embed(title=f"🎮 【限時免費】{game.get('title')}", description=f"平台: **{game.get('platforms')}**\n趕快去領取吧，錯過就可惜了！", url=game.get('open_giveaway_url'), color=discord.Color.green())
                    embed.set_image(url=game.get('thumbnail'))
                    embed.set_footer(text=f"活動結束時間: {game.get('end_date') or '未知'}")
                    
                    for channel_id in channels:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            await channel.send("🚨 **發現新的限免遊戲囉！**", embed=embed)
                            
                    await self.bot.db.add_free_game(game_id)
        except Exception as e:
            logger.error(f"檢查免費遊戲任務發生異常: {e}", exc_info=True)

    @check_free_games.before_loop
    async def before_check_free_games(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Broadcast(bot))