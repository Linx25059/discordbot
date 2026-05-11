import discord
from discord.ext import commands, tasks

import aiohttp
import xml.etree.ElementTree as ET
import datetime

class Broadcast(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # 啟動自動排程任務
        self.daily_news.start()
        self.check_free_games.start()

    async def cog_load(self):
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS news_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS games_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS free_games (game_id TEXT PRIMARY KEY)''')
        await self.bot.db.db.commit()
        
    def cog_unload(self):
        # 模組卸載時，停止任務
        self.daily_news.cancel()
        self.check_free_games.cancel()

    # 取得有設定新聞推播的頻道清單
    async def get_news_channels(self):
        async with self.bot.db.db.execute('SELECT channel_id FROM news_settings') as cursor:
            return [row[0] async for row in cursor]

    # 取得有設定免費遊戲推播的頻道清單
    async def get_games_channels(self):
        async with self.bot.db.db.execute('SELECT channel_id FROM games_settings') as cursor:
            return [row[0] async for row in cursor]

    # 🛠️ 管理員指令：設定新聞頻道
    @commands.hybrid_command(name="setnews", aliases=["設定新聞"], help="設定當前頻道為「每日新聞」自動推播頻道")
    @commands.has_permissions(manage_channels=True)
    async def set_news(self, ctx):
        guild_id = ctx.guild.id
        channel_id = ctx.channel.id
        
        await self.bot.db.db.execute('INSERT OR REPLACE INTO news_settings (guild_id, channel_id) VALUES (?, ?)', (guild_id, channel_id))
        await self.bot.db.db.commit()
        
        embed = discord.Embed(title="📡 新聞頻道設定成功", description=f"已經把 {ctx.channel.mention} 設為新聞頻道囉！\n每天早上 8 點會幫大家整理最新新聞。", color=discord.Color.green())
        await ctx.send(embed=embed)

    # 🛠️ 管理員指令：設定免費遊戲頻道
    @commands.hybrid_command(name="setgames", aliases=["設定免費遊戲"], help="設定當前頻道為「限時免費遊戲」推播頻道")
    @commands.has_permissions(manage_channels=True)
    async def set_games(self, ctx):
        guild_id = ctx.guild.id
        channel_id = ctx.channel.id
        
        await self.bot.db.db.execute('INSERT OR REPLACE INTO games_settings (guild_id, channel_id) VALUES (?, ?)', (guild_id, channel_id))
        await self.bot.db.db.commit()
        
        embed = discord.Embed(title="🎮 免費遊戲推播設定成功", description=f"已經把 {ctx.channel.mention} 設為免費遊戲通知頻道囉！\n只要有免費遊戲都會立刻通知大家。", color=discord.Color.blue())
        await ctx.send(embed=embed)

    # ⏰ 任務 1：每天早上 8 點 (台灣時間 UTC+8) 推播新聞與天氣
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    @tasks.loop(time=datetime.time(hour=8, minute=0, second=0, tzinfo=tz_tw))
    async def daily_news(self):
        channels = await self.get_news_channels()
        if not channels:
            return

        try:
            # 抓取 Google 新聞 RSS (台灣版)
            async with self.bot.session.get('https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant') as resp:
                if resp.status == 200:
                    xml_data = await resp.text()
                    # 企業級優化：將同步的 XML 解析丟入背景執行緒，防阻塞事件迴圈
                    root = await self.bot.loop.run_in_executor(None, ET.fromstring, xml_data)
                    
                    embed = discord.Embed(title="☀️ 早安！今日重點新聞", description="為大家整理今天的熱門新聞：", color=discord.Color.gold())
                        
                    # 抓取前 5 則新聞
                    for i, item in enumerate(root.findall('./channel/item')):
                        if i >= 5:
                            break
                        title = item.find('title').text
                        link = item.find('link').text
                        embed.add_field(name=f"🗞️ {title}", value=f"[點擊閱讀詳細內容]({link})", inline=False)
                    
                    embed.set_footer(text="新聞來源：Google 新聞")

                    # 發送到所有有設定廣播的頻道
                    for channel_id in channels:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            await channel.send(embed=embed)
        except Exception as e:
            print(f"每日新聞推播發生錯誤: {e}")

    @daily_news.before_loop
    async def before_daily_news(self):
        await self.bot.wait_until_ready()

    # ⏰ 任務 2：每 4 小時檢查一次有沒有新的免費遊戲
    @tasks.loop(hours=2)
    async def check_free_games(self):
        # 🛠️ 修復：非同步函式必須被 await，否則會回傳 coroutine 物件導致 TypeError
        channels = await self.get_games_channels()
        if not channels:
            return

        try:
            # 使用 GamerPower API 抓取限時免費遊戲
            url = "https://www.gamerpower.com/api/filter?platform=epic-games-store,steam&type=game"
            async with self.bot.session.get(url) as resp:
                if resp.status == 200:
                    games = await resp.json()
                    
                    # 🛡️ 防禦性編程：確保 API 回傳的是陣列。若 API 發生異常回傳 dict 錯誤訊息，提早退出避免 AttributeError
                    if not isinstance(games, list):
                        logging.error(f"廣播系統 GamerPower API 回傳格式異常: {games}")
                        return

                    for game in games:
                        game_id = str(game.get('id'))
                        
                        # 檢查資料庫，看這個遊戲是不是已經播報過了
                        async with self.bot.db.db.execute('SELECT game_id FROM free_games WHERE game_id = ?', (game_id,)) as cursor:
                            is_sent = await cursor.fetchone()
                        if not is_sent:
                            # 沒播報過，準備廣播！
                            embed = discord.Embed(title=f"🎮 【限時免費】{game.get('title')}", description=f"平台: **{game.get('platforms')}**\n趕快去領取吧，錯過就可惜了！", url=game.get('open_giveaway_url'), color=discord.Color.green())
                            embed.set_image(url=game.get('thumbnail'))
                            embed.set_footer(text=f"活動結束時間: {game.get('end_date') or '未知'}")
                            
                            for channel_id in channels:
                                channel = self.bot.get_channel(channel_id)
                                if channel:
                                    await channel.send("🚨 **發現新的限免遊戲囉！**", embed=embed)
                                    
                            await self.bot.db.db.execute('INSERT INTO free_games (game_id) VALUES (?)', (game_id,))
                            await self.bot.db.db.commit()
        except Exception as e:
            print(f"檢查免費遊戲發生錯誤: {e}")

    @check_free_games.before_loop
    async def before_check_free_games(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Broadcast(bot))