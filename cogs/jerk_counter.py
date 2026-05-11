import discord
from discord.ext import commands

class JerkCounter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # 建立清槍計數資料庫
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS jerk_counts (user_id INTEGER PRIMARY KEY, count INTEGER)''')
        await self.bot.db.db.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        # 避免機器人自言自語無限迴圈
        if message.author.bot:
            return

        # 設定觸發關鍵字
        keywords = ["尻", "打手槍", "清槍", "打管", "擼","導管","撸管","撸","撸一撸","打飞机","打飛機","cum","jerk","masturbate","wank","fap","self pleasure","手淫","自慰"]
        
        if any(k in message.content for k in keywords):
            async with self.bot.db.db.execute('SELECT count FROM jerk_counts WHERE user_id = ?', (message.author.id,)) as cursor:
                row = await cursor.fetchone()
            
            if row:
                new_count = row[0] + 1
                await self.bot.db.db.execute('UPDATE jerk_counts SET count = ? WHERE user_id = ?', (new_count, message.author.id))
            else:
                new_count = 1
                await self.bot.db.db.execute('INSERT INTO jerk_counts (user_id, count) VALUES (?, ?)', (message.author.id, new_count))
            await self.bot.db.db.commit()
            
            # 給個超派的活網回應
            try:
                await message.reply(f"👀 抓到啦！{message.author.mention} 提到了關鍵字！這是第 **{new_count}** 次紀錄了喔！", mention_author=False)
            except:
                pass

    @commands.hybrid_command(name="jerkboard", aliases=["清槍榜", "尻尻排行榜", "jb"], help="查看群組內的關鍵字觸發排行榜")
    async def jerkboard(self, ctx):
        async with self.bot.db.db.execute('SELECT user_id, count FROM jerk_counts ORDER BY count DESC LIMIT 10') as cursor:
            results = await cursor.fetchall()
        
        if not results:
            return await ctx.send(embed=discord.Embed(description="🤔 目前群組裡面還沒有相關的紀錄喔！", color=discord.Color.light_grey()))
        
        embed = discord.Embed(title="🏆 關鍵字觸發排行榜", description="來看看目前的排行統計：", color=discord.Color.purple())
        
        for i, (user_id, count) in enumerate(results):
            user = self.bot.get_user(user_id)
            name = user.display_name if user else f"未知尻神 ({user_id})"
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
            embed.add_field(name=f"{medal} 第 {i+1} 名：{name}", value=f"共觸發了 **{count}** 次", inline=False)
            
        embed.set_footer(text="💡 提示：只要在聊天中提到特定關鍵字就會列入統計喔！")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(JerkCounter(bot))