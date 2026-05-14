import discord
from discord.ext import commands, tasks
import aiohttp
import urllib.parse
import datetime
import asyncio

class Weather(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # 建立使用者預設天氣地點資料表
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS user_weather_location (user_id INTEGER PRIMARY KEY, location TEXT)''')
        # 建立每日天氣訂閱資料表
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS daily_weather_subs (user_id INTEGER PRIMARY KEY)''')
        await self.bot.db.db.commit()
        self.daily_weather_task.start()

    def cog_unload(self):
        self.daily_weather_task.cancel()

    @commands.hybrid_command(name="dailyweather", aliases=["每日天氣", "定時天氣"], help="開啟或關閉每日早上 8 點的天氣私訊推播")
    async def toggle_daily_weather(self, ctx):
        async with self.bot.db.db.execute('SELECT 1 FROM daily_weather_subs WHERE user_id = ?', (ctx.author.id,)) as cursor:
            is_sub = await cursor.fetchone()
        
        if is_sub:
            await self.bot.db.db.execute('DELETE FROM daily_weather_subs WHERE user_id = ?', (ctx.author.id,))
            await self.bot.db.db.commit()
            await ctx.send(embed=discord.Embed(description="🚫 已**關閉**每日早晨天氣推播！", color=discord.Color.red()))
        else:
            await self.bot.db.db.execute('INSERT INTO daily_weather_subs (user_id) VALUES (?)', (ctx.author.id,))
            await self.bot.db.db.commit()
            await ctx.send(embed=discord.Embed(description="✅ 已**開啟**每日早晨天氣推播！\n每天早上 8 點，我會將你綁定的預設地點天氣私訊給你喔！(若未綁定地點，將預設為台北)", color=discord.Color.green()))

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    @tasks.loop(time=datetime.time(hour=8, minute=0, second=0, tzinfo=tz_tw))
    async def daily_weather_task(self):
        # 撈出所有訂閱使用者的 ID 與他們綁定的地點
        async with self.bot.db.db.execute('''
            SELECT s.user_id, l.location 
            FROM daily_weather_subs s 
            LEFT JOIN user_weather_location l ON s.user_id = l.user_id
        ''') as cursor:
            subs = await cursor.fetchall()
            
        for user_id, location in subs:
            if not location:
                location = "台北" # 容錯處理
                
            try:
                user = self.bot.get_user(user_id)
                if not user:
                    user = await self.bot.fetch_user(user_id)
                    
                if user:
                    embed = await self.get_weather_embed(location, is_daily=True)
                    if embed:
                        await user.send(embed=embed)
            except Exception as e:
                print(f"推播每日天氣給 {user_id} 失敗: {e}")
                
            # 避免觸發 Discord API Rate Limit 和 wttr.in 請求限制
            await asyncio.sleep(2)

    @daily_weather_task.before_loop
    async def before_daily_weather(self):
        await self.bot.wait_until_ready()

    async def get_weather_embed(self, location: str, is_default: bool = False, is_daily: bool = False):
        try:
            # 處理使用者輸入的空格 (例如 "台北市 信義區" 轉換成 URL 安全格式)
            safe_location = urllib.parse.quote(location)
            url = f"https://wttr.in/{safe_location}?format=j1&lang=zh-tw"
            
            async with self.bot.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    current = data.get('current_condition', [{}])[0]
                    weather_forecast = data.get('weather', [])
                    
                    temp = current.get('temp_C', '未知')
                    feels_like = current.get('FeelsLikeC', '未知')
                    humidity = current.get('humidity', '未知')
                    wind = current.get('windspeedKmph', '未知')
                    precip = current.get('precipMM', '0.0')
                        
                    # 優先抓取中文天氣描述
                    desc = "未知"
                    if 'lang_zh-tw' in current and current['lang_zh-tw']:
                        desc = current['lang_zh-tw'][0].get('value', '未知')
                    elif 'weatherDesc' in current and current['weatherDesc']:
                        desc = current['weatherDesc'][0].get('value', '未知')

                    title = f"🌅 早安！{location} 今日天氣" if is_daily else f"🌤️ {location} 的天氣資訊"
                    color = discord.Color.gold() if is_daily else discord.Color.blue()
                    
                    embed = discord.Embed(title=title, description=f"目前天氣狀況：**{desc}**", color=color)
                    embed.add_field(name="🌡️ 溫度", value=f"{temp}°C (體感 {feels_like}°C)", inline=True)
                    embed.add_field(name="💧 濕度", value=f"{humidity}%", inline=True)
                    embed.add_field(name="💨 風速", value=f"{wind} km/h", inline=True)
                    embed.add_field(name="☔ 降雨量", value=f"{precip} mm", inline=True)
                    
                    # 未來天氣預報
                    if weather_forecast:
                        forecast_text = ""
                        for day in weather_forecast:
                            date = day.get('date', '')
                            max_t = day.get('maxtempC', '')
                            min_t = day.get('mintempC', '')
                            
                            hourly = day.get('hourly', [])
                            max_chance_of_rain = 0
                            for hour in hourly:
                                try:
                                    rain_chance = int(hour.get('chanceofrain', '0'))
                                    if rain_chance > max_chance_of_rain:
                                        max_chance_of_rain = rain_chance
                                except:
                                    pass
                            
                            # 取中午時段的天氣描述
                            day_desc = "未知"
                            midday = hourly[4] if len(hourly) > 4 else (hourly[0] if hourly else {})
                                
                            if 'lang_zh-tw' in midday and midday['lang_zh-tw']:
                                day_desc = midday['lang_zh-tw'][0].get('value', '未知')
                            elif 'weatherDesc' in midday and midday['weatherDesc']:
                                day_desc = midday['weatherDesc'][0].get('value', '未知')

                            forecast_text += f"**{date}**: {day_desc} | {min_t}°C ~ {max_t}°C | ☔ 降雨機率 {max_chance_of_rain}%\n"
                            
                        if forecast_text:
                            embed.add_field(name="📅 近期天氣預報", value=forecast_text, inline=False)
                            
                    footer_text = "天氣資料來源: wttr.in"
                    if is_daily:
                        footer_text += "\n💡 提示: 這是您的每日早晨推播，如想取消請輸入 /dailyweather"
                    elif is_default:
                        footer_text += "\n💡 提示: 這是你綁定的預設地點。如要更改請使用 /setweather，或是在指令後方加上指定地點。"
                    
                    embed.set_footer(text=footer_text)
                    return embed
                return None
        except Exception as e:
            print(f"獲取天氣發生錯誤: {e}")
            return None

    @commands.hybrid_command(name="setweather", aliases=["設定天氣地點", "綁定天氣"], help="綁定你的專屬預設天氣查詢地點")
    async def set_weather(self, ctx, *, location: str):
        await self.bot.db.db.execute('INSERT OR REPLACE INTO user_weather_location (user_id, location) VALUES (?, ?)', (ctx.author.id, location))
        await self.bot.db.db.commit()
        await ctx.send(embed=discord.Embed(description=f"✅ 已成功將你的預設天氣地點綁定為 **{location}**！\n以後只要直接輸入 `/weather` 就會自動為你查詢這個地點囉！", color=discord.Color.green()))

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.hybrid_command(name="weather", aliases=["天氣", "w"], help="查詢即時天氣與未來預報")
    async def weather(self, ctx, *, location: str = None):
        is_default = False
        # 若沒有輸入地點，則去資料庫尋找使用者的綁定紀錄
        if not location:
            async with self.bot.db.db.execute('SELECT location FROM user_weather_location WHERE user_id = ?', (ctx.author.id,)) as cursor:
                result = await cursor.fetchone()
            if result:
                location = result[0]
                is_default = True
            else:
                return await ctx.send(embed=discord.Embed(description="❌ 你沒有輸入地點，也沒有綁定過預設地點喔！\n請先使用 `/setweather <地點>` 來綁定，或是直接輸入 `/weather <地點>` 來查詢。", color=discord.Color.red()), ephemeral=True)
            
        async with ctx.typing():
            embed = await self.get_weather_embed(location, is_default=is_default)
            if embed:
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ 找不到 **{location}** 的天氣資訊，或伺服器連線異常，請確認有沒有打錯字！")

async def setup(bot):
    await bot.add_cog(Weather(bot))