import discord
from discord.ext import commands

class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="profile", aliases=["個人檔案", "檔案"], help="查看金幣、等級與成就徽章")
    async def profile(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user_id = member.id

        # 1. 查詢財富餘額
        balance = await self.bot.db.get_balance(user_id)

        # 2. 查詢等級資訊
        if ctx.guild:
            async with self.bot.db.db.execute('SELECT xp, level FROM leveling WHERE guild_id = ? AND user_id = ?', (ctx.guild.id, user_id)) as cursor:
                lvl_result = await cursor.fetchone()
        else:
            lvl_result = None

        if lvl_result:
            xp, level = lvl_result
            xp_needed = 5 * (level ** 2) + 50 * level + 100
            lvl_str = f"**Lv.{level}**\n`{xp} / {xp_needed}` XP"
        else:
            lvl_str = "**Lv.1**\n`0 / 105` XP"

        # 3. 查詢成就稱號
        badges = await self.bot.db.get_achievements(user_id)
        
        # 定義成就對應的專屬圖示 (依照稀有度或主題設定)
        badge_icons = {
            "【天選之人】": "👑",       # 稀有掉落
            "【百烈金右手】": "🌟",     # 隱藏計數成就
            "【賭神】": "🎰",         # 賭場大贏家
            "【股票大亨】": "📈",       # 股市翻倍
            "【AI 詠唱者】": "🤖",      # 消耗大量 Token
            "【夜貓子】": "🦉",         # 深夜活動
            "【大慈善家】": "💸",       # 賭場大輸家
            "【破產仔】": "📉",         # 餘額歸零
            "【超級大韭菜】": "🥬"      # 股市慘賠
        }
        
        if badges:
            badge_str = "\n".join([f"{badge_icons.get(b, '🏅')} {b}" for b in badges])
        else:
            badge_str = "尚未獲得任何稱號..."

        embed = discord.Embed(title=f"🪪 {member.display_name} 的個人檔案", color=discord.Color.purple())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="💰 財富餘額", value=f"**{balance:,}** 金幣", inline=True)
        embed.add_field(name="🏆 活躍等級", value=lvl_str, inline=True)
        embed.add_field(name="🎖️ 收集稱號", value=badge_str, inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Profile(bot))