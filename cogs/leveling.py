import discord
from discord.ext import commands
import random
from datetime import datetime, timedelta
import aiosqlite
from typing import Optional

class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = None
        
        # 避免玩家狂刷訊息洗經驗值，加入冷卻時間字典 (紀錄最後發話時間)
        self.cooldowns = {} 

    async def cog_load(self):
        # 改用 aiosqlite，避免監聽器卡死主執行緒
        self.db = await aiosqlite.connect('bot_database.db', timeout=10.0)
        await self.db.execute('''CREATE TABLE IF NOT EXISTS leveling (guild_id INTEGER, user_id INTEGER, xp INTEGER, level INTEGER, PRIMARY KEY (guild_id, user_id))''')
        await self.db.commit()

    async def cog_unload(self):
        if self.db:
            await self.db.close()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 不計算機器人的訊息，也不計算私訊
        if message.author.bot or message.guild is None:
            return

        # 檢查冷卻時間 (設定每 60 秒只能獲得一次經驗值)
        now = datetime.now()
        last_msg_time = self.cooldowns.get(message.author.id)
        if last_msg_time and now < last_msg_time + timedelta(seconds=60):
            return
        self.cooldowns[message.author.id] = now

        guild_id = message.guild.id
        user_id = message.author.id

        # 從資料庫獲取目前的等級
        async with self.db.execute('SELECT xp, level FROM leveling WHERE guild_id = ? AND user_id = ?', (guild_id, user_id)) as cursor:
            result = await cursor.fetchone()

        if result is None:
            await self.db.execute('INSERT INTO leveling (guild_id, user_id, xp, level) VALUES (?, ?, ?, ?)', (guild_id, user_id, 0, 1))
            xp, level = 0, 1
        else:
            xp, level = result

        # 隨機增加 15 ~ 25 點經驗值
        new_xp = xp + random.randint(15, 25)
        
        # 升級公式：所需 XP = 5*(等級^2) + 50*等級 + 100
        xp_needed = 5 * (level ** 2) + 50 * level + 100
        if new_xp >= xp_needed:
            new_level = level + 1
            new_xp -= xp_needed # 扣除升級耗費的 XP
            await self.db.execute('UPDATE leveling SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?', (new_xp, new_level, guild_id, user_id))
            embed = discord.Embed(title="🆙 升級通知", description=f"🎉 恭喜 {message.author.mention}，你升級到 **Lv.{new_level}** 囉！", color=discord.Color.gold())
            await message.channel.send(embed=embed)
        else:
            await self.db.execute('UPDATE leveling SET xp = ? WHERE guild_id = ? AND user_id = ?', (new_xp, guild_id, user_id))
        await self.db.commit()

    @commands.hybrid_command(name="rank", aliases=["等級", "xp"], help="查看自己的等級與經驗值進度")
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        async with self.db.execute('SELECT xp, level FROM leveling WHERE guild_id = ? AND user_id = ?', (ctx.guild.id, member.id)) as cursor:
            result = await cursor.fetchone()
        
        if result is None:
            return await ctx.send(f"❌ {member.display_name} 目前還沒有經驗值紀錄喔！多多在頻道聊天吧！")
            
        xp, level = result
        xp_needed = 5 * (level ** 2) + 50 * level + 100
        
        embed = discord.Embed(title=f"📊 {member.display_name} 的等級資訊", color=discord.Color.blue())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="目前等級", value=f"**Lv.{level}**", inline=True)
        embed.add_field(name="經驗值", value=f"**{xp} / {xp_needed} XP**", inline=True)
        
        # 產生經驗值進度條
        percentage = xp / xp_needed
        bar_length = 15
        filled = int(percentage * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        embed.add_field(name="升級進度", value=f"`{bar}` ({percentage*100:.1f}%)", inline=False)
        
        await ctx.send(embed=embed)
        
    @commands.hybrid_command(name="leaderboard", aliases=["排行榜", "top"], help="查看伺服器最活躍成員等級排行榜")
    async def leaderboard(self, ctx):
        async with self.db.execute('SELECT user_id, xp, level FROM leveling WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10', (ctx.guild.id,)) as cursor:
            results = await cursor.fetchall()
        
        if not results:
            return await ctx.send("❌ 目前伺服器內還沒有任何等級紀錄喔！")
            
        embed = discord.Embed(title="🏆 伺服器活躍等級排行榜", color=discord.Color.gold())
        
        for i, (user_id, xp, level) in enumerate(results, 1):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"未知使用者 ({user_id})"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            embed.add_field(name=f"{medal} {name}", value=f"**Lv.{level}** (目前 XP: {xp})", inline=False)
            
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Leveling(bot))