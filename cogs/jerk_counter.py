import discord
from discord.ext import commands
import random

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
            
            # --- 100 次黃金廣播與隱藏成就 ---
            if new_count == 100:
                achieved = await self.bot.db.check_and_add_achievement(message.author.id, '【百烈金右手】')
                ach_text = "\n\n✨ **解鎖隱藏成就：【百烈金右手】**" if achieved else ""
                
                embed = discord.Embed(
                    title="🏆 系統黃金廣播 🏆",
                    description=f"🎉 **狂賀！** {message.author.mention} 達成了史無前例的 **100 次** 傳統手藝紀錄！\n\n這是一條漫長且艱辛的道路，讓我們為他的毅力（與右手）致上最高的敬意！" + ach_text,
                    color=discord.Color.gold()
                )
                try:
                    await message.channel.send(embed=embed)
                except:
                    pass
                return

            # 給個超派的活網回應
            funny_replies = [
                "👀 抓到啦！{mention} 提到了關鍵字！這是第 **{count}** 次紀錄了喔！",
                "👮‍♂️ 警察叔叔就是這個人！{mention} 又在瑟瑟了，這已經是第 **{count}** 次啦！",
                "💦 節制一點啊 {mention}！這已經是你第 **{count}** 次被我抓到了，再這樣下去身體會吃不消的！",
                "📉 警告：{mention} 的生命值正在急速下降... 目前清槍次數已達 **{count}** 次！",
                "🏆 掌聲鼓勵！{mention} 達成了第 **{count}** 次清槍成就！難道這就是傳說中的尻神？",
                "🧘‍♂️ 施主，色即是空，空即是色。{mention}，你已經累積 **{count}** 次了...",
                "🙈 我什麼都沒看到... 但系統無情地記錄下 {mention} 發動了第 **{count}** 次傳統手藝。"
            ]
            reply_text = random.choice(funny_replies).format(mention=message.author.mention, count=new_count)
            try:
                await message.reply(reply_text, mention_author=False)
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
            
            # 第一名專屬動態頭銜
            dynamic_title = " 👑 **【傳說中的神之右手】**" if i == 0 else ""
            
            embed.add_field(name=f"{medal} 第 {i+1} 名：{name}{dynamic_title}", value=f"共觸發了 **{count}** 次", inline=False)
            
        embed.set_footer(text="💡 提示：只要在聊天中提到特定關鍵字就會列入統計喔！")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(JerkCounter(bot))