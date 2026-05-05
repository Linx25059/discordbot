import discord
from discord.ext import commands, tasks
import sqlite3
import aiohttp
import xml.etree.ElementTree as ET
import datetime

class Broadcast(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('bot_database.db', timeout=10.0)
        self.c = self.conn.cursor()

        # 建立資料表：紀錄哪個伺服器在哪個頻道發送廣播，以及紀錄已經推播過的免費遊戲 (避免重複洗頻)
        self.c.execute('''CREATE TABLE IF NOT EXISTS server_settings (guild_id INTEGER PRIMARY KEY, broadcast_channel_id INTEGER)''')
        self.c.execute('''CREATE TABLE IF NOT EXISTS free_games (game_id TEXT PRIMARY KEY)''')
        self.conn.commit()

        # 啟動自動排程任務
        self.daily_news.start()
        self.check_free_games.start()

    def cog_unload(self):
        # 模組卸載時，停止任務
        self.daily_news.cancel()
        self.check_free_games.cancel()

    # 取得有設定廣播的頻道清單
    def get_broadcast_channels(self):
        self.c.execute('SELECT broadcast_channel_id FROM server_settings')
        return [row[0] for row in self.c.fetchall()]

    # 🛠️ 管理員指令：設定廣播頻道
    @commands.hybrid_command(name="setbroadcast", aliases=["設定廣播"], help="設定當前頻道為「自動新聞與免費遊戲」推播頻道")
    @commands.has_permissions(manage_channels=True)
    async def set_broadcast(self, ctx):
        guild_id = ctx.guild.id
        channel_id = ctx.channel.id
        
        self.c.execute('INSERT OR REPLACE INTO server_settings (guild_id, broadcast_channel_id) VALUES (?, ?)', (guild_id, channel_id))
        self.conn.commit()
        
        await ctx.send(f"✅ 成功！已將 {ctx.channel.mention} 設為自動推播頻道。\n機器人每天早上 8 點會在這裡播報新聞，並隨時監控 Epic/Steam 的限時免費遊戲！")

    # ⏰ 任務 1：每天早上 8 點 (台灣時間 UTC+8) 推播新聞與天氣
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    @tasks.loop(time=datetime.time(hour=8, minute=0, second=0, tzinfo=tz_tw))
    async def daily_news(self):
        channels = self.get_broadcast_channels()
        if not channels:
            return

        try:
            # 抓取 Google 新聞 RSS (台灣版)
            async with aiohttp.ClientSession() as session:
                async with session.get('https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant') as resp:
                    if resp.status == 200:
                        xml_data = await resp.text()
                        root = ET.fromstring(xml_data)
                        
                        embed = discord.Embed(title="☀️ 早安！今日熱門頭條", description="為您整理今天的最新重點新聞：", color=discord.Color.gold())
                        
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
    @tasks.loop(hours=4)
    async def check_free_games(self):
        channels = self.get_broadcast_channels()
        if not channels:
            return

        try:
            # 使用 GamerPower API 抓取限時免費遊戲
            url = "https://www.gamerpower.com/api/filter?platform=epic-games-store,steam&type=game"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        games = await resp.json()
                        
                        for game in games:
                            game_id = str(game.get('id'))
                            
                            # 檢查資料庫，看這個遊戲是不是已經播報過了
                            self.c.execute('SELECT game_id FROM free_games WHERE game_id = ?', (game_id,))
                            if self.c.fetchone() is None:
                                # 沒播報過，準備廣播！
                                embed = discord.Embed(title=f"🎮 【限時免費】{game.get('title')}", description=f"平台: **{game.get('platforms')}**\n趕快領取，以免向隅！", url=game.get('open_giveaway_url'), color=discord.Color.green())
                                embed.set_image(url=game.get('thumbnail'))
                                embed.set_footer(text=f"活動結束時間: {game.get('end_date') or '未知'}")
                                
                                for channel_id in channels:
                                    channel = self.bot.get_channel(channel_id)
                                    if channel:
                                        await channel.send("🚨 **發現新的限免遊戲啦！**", embed=embed)
                                        
                                self.c.execute('INSERT INTO free_games (game_id) VALUES (?)', (game_id,))
                                self.conn.commit()
        except Exception as e:
            print(f"檢查免費遊戲發生錯誤: {e}")

    @check_free_games.before_loop
    async def before_check_free_games(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Broadcast(bot))