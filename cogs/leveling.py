import discord
from discord.ext import commands
import random
from datetime import datetime, timedelta
from typing import Optional

class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    async def cog_load(self):
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS leveling (guild_id INTEGER, user_id INTEGER, xp INTEGER, level INTEGER, PRIMARY KEY (guild_id, user_id))''')
        await self.bot.db.db.commit()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 不計算機器人的訊息，也不計算私訊
        if message.author.bot or message.guild is None:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        # 從資料庫獲取目前的等級
        async with self.bot.db.db.execute('SELECT xp, level FROM leveling WHERE guild_id = ? AND user_id = ?', (guild_id, user_id)) as cursor:
            result = await cursor.fetchone()

        if result is None:
            await self.bot.db.db.execute('INSERT INTO leveling (guild_id, user_id, xp, level) VALUES (?, ?, ?, ?)', (guild_id, user_id, 0, 1))
            xp, level = 0, 1
        else:
            xp, level = result

        # 隨機增加 5 ~ 10 點經驗值 (因無冷卻時間而調低)
        new_xp = xp + random.randint(5, 10)
        
        # 升級公式：所需 XP = 5*(等級^2) + 50*等級 + 100
        xp_needed = 5 * (level ** 2) + 50 * level + 100
        if new_xp >= xp_needed:
            new_level = level + 1
            new_xp -= xp_needed # 扣除升級耗費的 XP
            await self.bot.db.db.execute('UPDATE leveling SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?', (new_xp, new_level, guild_id, user_id))
            
            # --- 新增：升級發大財 (等級 * 1000 金幣) ---
            reward_coins = new_level * 1000
            await self.bot.db.update_balance(user_id, reward_coins)
            
            embed = discord.Embed(title="🆙 升級通知", description=f"🎉 恭喜 {message.author.mention}，你升級到 **Lv.{new_level}** 囉！\n💰 **升級獎勵：** 獲得了 **{reward_coins:,}** 金幣！", color=discord.Color.gold())
            await message.channel.send(embed=embed)
        else:
            await self.bot.db.db.execute('UPDATE leveling SET xp = ? WHERE guild_id = ? AND user_id = ?', (new_xp, guild_id, user_id))
            
        # --- 新增：聊天隨機金幣掉落 (15% 機率) ---
        if random.random() < 0.15:
            drop_coins = random.randint(100, 500)
            await self.bot.db.update_balance(user_id, drop_coins)
            
            msg_text = f"🪙 幸運兒！{message.author.mention} 在聊天時意外撿到了 **{drop_coins}** 金幣！"
            
            if drop_coins > 400:
                hidden_dialogues = [
                    "\n*(🕵️‍♂️ 系統聲音：哇塞！這該不會是版主不小心掉的私房錢吧...？)*",
                    "\n*(🌟 財神爺在你耳邊低語：年輕人，這筆鉅款可別亂花啊！)*",
                    "\n*(👀 路過的群友投以羨慕、嫉妒、恨的眼光...)*",
                    "\n*(🎰 運氣大爆棚！建議等等直接去賭場梭哈了啦！)*"
                ]
                msg_text += random.choice(hidden_dialogues)
            
            # 解鎖隱藏成就：天選之人
            if await self.bot.db.check_and_add_achievement(user_id, '【天選之人】'):
                msg_text += "\n\n✨ **成就解鎖！** 運氣爆棚，獲得稱號 **【天選之人】**！"
                
            try:
                # 自動刪除提示避免洗頻 (如果有觸發隱藏對話，多留幾秒讓幸運兒能截圖)
                delete_time = 8 if drop_coins > 400 else 5
                await message.channel.send(msg_text, delete_after=delete_time)
            except:
                pass
                
        await self.bot.db.db.commit()

    @commands.hybrid_command(name="rank", aliases=["等級", "xp"], help="查看自己的等級與經驗值進度")
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        async with self.bot.db.db.execute('SELECT xp, level FROM leveling WHERE guild_id = ? AND user_id = ?', (ctx.guild.id, member.id)) as cursor:
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
        async with self.bot.db.db.execute('SELECT user_id, xp, level FROM leveling WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10', (ctx.guild.id,)) as cursor:
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