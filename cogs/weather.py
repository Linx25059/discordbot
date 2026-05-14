import discord
from discord.ext import commands, tasks
import aiohttp
import urllib.parse
import datetime
import asyncio

# --- 彈出式輸入視窗 (用來綁定地點) ---
class WeatherBindModal(discord.ui.Modal, title='🌍 綁定預設天氣地點'):
    location_input = discord.ui.TextInput(
        label='請輸入你的預設地點 (例如: 台北, 高雄市, 東京)',
        placeholder='地點名稱...',
        required=True,
        max_length=50
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        location = self.location_input.value.strip()
        # 寫入資料庫
        await self.cog.bot.db.db.execute('INSERT OR REPLACE INTO user_weather_location (user_id, location) VALUES (?, ?)', (interaction.user.id, location))
        await self.cog.bot.db.db.commit()
        
        await interaction.response.send_message(f"✅ 已成功將預設地點綁定為 **{location}**！正在為你查詢...", ephemeral=True)
        
        # 綁定完成後自動幫使用者查一次天氣
        embed = await self.cog.get_weather_embed(location, is_default=True)
        if embed:
            await interaction.channel.send(content=f"{interaction.user.mention} 查詢的預設天氣：", embed=embed)
        else:
            await interaction.followup.send(f"❌ 找不到 **{location}** 的天氣資訊，或伺服器連線異常，請確認有沒有打錯字！", ephemeral=True)

# --- 提供綁定按鈕的 View ---
class WeatherBindView(discord.ui.View):
    def __init__(self, cog, author_id):
        super().__init__(timeout=120)
        self.cog = cog
        self.author_id = author_id

    @discord.ui.button(label="🌍 立即綁定地點", style=discord.ButtonStyle.success)
    async def bind_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 這是給別人的設定按鈕喔！請自己輸入 /weather 來綁定。", ephemeral=True)
        # 呼叫彈出式視窗
        await interaction.response.send_modal(WeatherBindModal(self.cog))

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

    def translate_weather(self, eng_desc: str) -> str:
        """內建天氣翻譯字典，補足 API 的中文翻譯缺失"""
        mapping = {
            "Clear": "晴朗", "Sunny": "晴天", "Partly cloudy": "多雲時晴", "Cloudy": "多雲",
            "Overcast": "陰天", "Mist": "薄霧", "Patchy rain possible": "局部降雨", "Patchy snow possible": "局部降雪",
            "Patchy sleet possible": "局部雨夾雪", "Patchy freezing drizzle possible": "局部凍毛毛雨",
            "Thundery outbreaks possible": "可能有雷陣雨", "Blowing snow": "吹雪", "Blizzard": "暴風雪",
            "Fog": "霧", "Freezing fog": "凍霧", "Patchy light drizzle": "局部輕毛毛雨", "Light drizzle": "輕微毛毛雨",
            "Freezing drizzle": "凍毛毛雨", "Heavy freezing drizzle": "強凍毛毛雨", "Patchy light rain": "局部小雨",
            "Light rain": "小雨", "Moderate rain at times": "偶有中雨", "Moderate rain": "中雨",
            "Heavy rain at times": "偶有大雨", "Heavy rain": "大雨", "Light freezing rain": "輕微凍雨",
            "Moderate or heavy freezing rain": "中度或大凍雨", "Light sleet": "小雨夾雪", "Moderate or heavy sleet": "中大雨夾雪",
            "Patchy light snow": "局部小雪", "Light snow": "小雪", "Patchy moderate snow": "局部中雪",
            "Moderate snow": "中雪", "Patchy heavy snow": "局部大雪", "Heavy snow": "大雪", "Ice pellets": "冰雹",
            "Light rain shower": "小陣雨", "Moderate or heavy rain shower": "中大陣雨", "Torrential rain shower": "暴陣雨",
            "Light sleet showers": "小陣雨夾雪", "Moderate or heavy sleet showers": "中大陣雨夾雪",
            "Light snow showers": "小陣雪", "Moderate or heavy snow showers": "中大陣雪",
            "Light showers of ice pellets": "小冰雹陣雨", "Moderate or heavy showers of ice pellets": "中大冰雹陣雨",
            "Patchy light rain with thunder": "局部小雷陣雨", "Moderate or heavy rain with thunder": "中大雷陣雨",
            "Patchy light snow with thunder": "局部小雷陣雪", "Moderate or heavy snow with thunder": "中大雷陣雪",
            "Moderate or heavy rain in area with thunder": "局部中大雷陣雨", "Patchy light rain in area with thunder": "局部小雷陣雨",
            "Thundery outbreaks in nearby": "附近有雷陣雨",
            "Patchy rain nearby": "附近有局部降雨"
        }
        text = eng_desc.strip()
        return mapping.get(text, mapping.get(text.capitalize(), text))

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
                        
                    # 內部輔助函式：用來獲取最精準的中文天氣描述
                    def get_zh_desc(weather_node):
                        eng_desc = ""
                        if 'weatherDesc' in weather_node and weather_node['weatherDesc']:
                            eng_desc = weather_node['weatherDesc'][0].get('value', '').strip()
                            
                        # 先查我們的字典
                        translated = self.translate_weather(eng_desc)
                        if translated != eng_desc:
                            return translated
                            
                        # 字典沒有的話，再看看 API 有沒有給其他中文翻譯
                        for lang_key in ['lang_zh-tw', 'lang_zh', 'lang_zh-cn']:
                            if lang_key in weather_node and weather_node[lang_key]:
                                zh_val = weather_node[lang_key][0].get('value', '').strip()
                                if zh_val:
                                    return zh_val
                                    
                        return eng_desc if eng_desc else "未知"

                    desc = get_zh_desc(current)

                    # --- 動態日夜與縮圖判斷邏輯 ---
                    # 1. 抓取日出與日落時間
                    astronomy = weather_forecast[0].get('astronomy', [{}])[0] if weather_forecast else {}
                    sunrise_str = astronomy.get('sunrise', '06:00 AM')
                    sunset_str = astronomy.get('sunset', '06:00 PM')
                    
                    try:
                        sunrise_time = datetime.datetime.strptime(sunrise_str, '%I:%M %p').time()
                        sunset_time = datetime.datetime.strptime(sunset_str, '%I:%M %p').time()
                    except:
                        sunrise_time = datetime.time(6, 0)
                        sunset_time = datetime.time(18, 0)

                    # 2. 取得查詢地點的當地時間 (若無法解析則預設使用台灣時間)
                    local_time_str = current.get('localObsDateTime', '')
                    try:
                        time_part = " ".join(local_time_str.split(' ')[1:])
                        if 'AM' in time_part or 'PM' in time_part:
                            current_time = datetime.datetime.strptime(time_part, '%I:%M %p').time()
                        else:
                            current_time = datetime.datetime.strptime(time_part, '%H:%M').time()
                    except:
                        current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).time()

                    # 3. 判斷是否為白天
                    is_day = sunrise_time <= current_time <= sunset_time

                    time_emoji = "🌤️" if is_day else "🌙"
                    title = f"🌅 早安！{location} 今日天氣" if is_daily else f"{time_emoji} {location} 的即時天氣"
                    
                    # 如果是白天或早安推播就顯示金色，晚上則顯示深藍色
                    color = discord.Color.gold() if (is_day or is_daily) else discord.Color.dark_blue()
                    
                    # 將即時資訊整合，讓排版更簡潔乾淨
                    description = (
                        f"**{desc}**\n"
                        f"🌡️ **氣溫:** {temp}°C (體感 {feels_like}°C)\n"
                        f"💧 **濕度:** {humidity}% ｜ 💨 **風速:** {wind} km/h ｜ ☔ **降雨:** {precip} mm\n"
                        f"🌅 **日出:** {sunrise_str} ｜ 🌇 **日落:** {sunset_str}\n"
                    )
                    
                    embed = discord.Embed(title=title, description=description, color=color)
                    # 根據日夜動態替換 3D 高畫質縮圖
                    embed.set_thumbnail(url="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Travel%20and%20places/Sun.png" if is_day else "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Travel%20and%20places/Crescent%20Moon.png")
                    
                    # 未來天氣預報
                    if weather_forecast:
                        forecast_text = ""
                        for day in weather_forecast:
                            date = day.get('date', '')
                            # 簡化日期顯示 (例如 2026-05-14 變成 05-14)
                            short_date = date[5:] if len(date) > 5 else date
                            
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
                            midday = hourly[4] if len(hourly) > 4 else (hourly[0] if hourly else {})
                            day_desc = get_zh_desc(midday)

                            # 將未來天氣轉為更緊湊的一行格式
                            forecast_text += f"`{short_date}` {day_desc} ({min_t}~{max_t}°C) ｜ ☔ {max_chance_of_rain}%\n"
                            
                        if forecast_text:
                            embed.add_field(name="📅 近期預報", value=forecast_text, inline=False)
                            
                    footer_text = "來源: wttr.in"
                    if is_daily:
                        footer_text += " | 輸入 /dailyweather 可取消推播"
                    elif is_default:
                        footer_text += " | 這是預設地點，使用 /setweather 可更改"
                    
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
                view = WeatherBindView(self, ctx.author.id)
                embed = discord.Embed(
                    description="❌ 你沒有輸入地點，也沒有綁定過預設地點喔！\n點擊下方按鈕立刻綁定，或者直接在指令後方輸入 `/weather <地點>` 來查詢。", 
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed, view=view, ephemeral=True)
            
        async with ctx.typing():
            embed = await self.get_weather_embed(location, is_default=is_default)
            if embed:
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ 找不到 **{location}** 的天氣資訊，或伺服器連線異常，請確認有沒有打錯字！")

async def setup(bot):
    await bot.add_cog(Weather(bot))