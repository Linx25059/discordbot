import discord
from discord.ext import commands
import aiohttp
import urllib.parse

class Weather(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.hybrid_command(name="weather", aliases=["天氣", "w"], help="查詢即時天氣與未來預報")
    async def weather(self, ctx, *, location: str):
        async with ctx.typing():
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

                        embed = discord.Embed(
                            title=f"🌤️ {location} 的天氣資訊",
                            description=f"目前天氣狀況：**{desc}**",
                            color=discord.Color.blue()
                        )
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
                                
                                # 計算當日最高降雨機率
                                max_chance_of_rain = 0
                                for hour in hourly:
                                    try:
                                        rain_chance = int(hour.get('chanceofrain', '0'))
                                        if rain_chance > max_chance_of_rain:
                                            max_chance_of_rain = rain_chance
                                    except:
                                        pass
                                
                                # 取中午時段(通常是 hourly[4] 約 12:00)的天氣描述
                                day_desc = "未知"
                                midday = hourly[4] if len(hourly) > 4 else (hourly[0] if hourly else {})
                                    
                                if 'lang_zh-tw' in midday and midday['lang_zh-tw']:
                                    day_desc = midday['lang_zh-tw'][0].get('value', '未知')
                                elif 'weatherDesc' in midday and midday['weatherDesc']:
                                    day_desc = midday['weatherDesc'][0].get('value', '未知')

                                forecast_text += f"**{date}**: {day_desc} | {min_t}°C ~ {max_t}°C | ☔ 降雨機率 {max_chance_of_rain}%\n"
                                
                            if forecast_text:
                                embed.add_field(name="📅 近期天氣預報", value=forecast_text, inline=False)
                                
                        embed.set_footer(text="天氣資料來源: wttr.in")
                        
                        await ctx.send(embed=embed)
                    else:
                        await ctx.send(f"❌ 找不到 **{location}** 的天氣資訊，要不要確認一下有沒有打錯字？")
            except Exception as e:
                await ctx.send(f"⚠️ 查詢天氣時發生了一點問題：{e}")

async def setup(bot):
    await bot.add_cog(Weather(bot))