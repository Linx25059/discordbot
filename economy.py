import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import random
from datetime import datetime, time
import aiosqlite
import zoneinfo
from typing import Optional
import logging

class GiveawayView(discord.ui.View):
    def __init__(self, cog, host, prize_amount):
        super().__init__(timeout=300) # 5分鐘後自動開獎
        self.cog = cog
        self.host = host
        self.prize_amount = prize_amount
        self.participants = set()
        self.message = None

    async def on_timeout(self):
        if not self.message:
            return
            
        if not self.participants:
            # 退還金額
            await self.cog.bot.db.update_balance(self.host.id, self.prize_amount)
            for child in self.children:
                child.disabled = True
            embed = self.message.embeds[0]
            embed.color = discord.Color.red()
            embed.description += "\n\n😢 **時間到！連個貪財的都沒有，獎金退給原主啦，笑死！**"
            try:
                await self.message.edit(embed=embed, view=self)
            except: pass
            return

        winner_id = random.choice(list(self.participants))
        await self.cog.bot.db.update_balance(winner_id, self.prize_amount)
        
        for child in self.children:
            child.disabled = True
        winner = self.message.guild.get_member(winner_id)
        winner_mention = winner.mention if winner else f"<@{winner_id}>"
        embed = self.message.embeds[0]
        embed.description += f"\n\n⏰ **全對！開獎啦！恭喜 {winner_mention} 爽拿 {self.prize_amount:,} 金幣！**\n*(錢已經塞進你那破錢包了)*"
        embed.color = discord.Color.gold()
        try:
            await self.message.edit(embed=embed, view=self)
            await self.message.channel.send(f"🎉 靠北竟然抽中了！恭喜 {winner_mention} 白嫖了 {self.host.mention} 的 **{self.prize_amount:,}** 金幣！")
        except: pass

    @discord.ui.button(label="🎉 搶錢啦，與眾分", style=discord.ButtonStyle.success)
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.host.id:
            return await interaction.response.send_message("❌ 完全法克，你自己發錢還想自己搶喔？吃相難看，不是，哥們！", ephemeral=True)
            
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("❌ 你已經點過了啦，貪得無厭欸！", ephemeral=True)
            
        self.participants.add(interaction.user.id)
        
        embed = interaction.message.embeds[0]
        embed.set_footer(text=f"來蹭飯的：{len(self.participants)} 人 | 5 分鐘後自動開獎")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏆 提早發錢 (發起人專用)", style=discord.ButtonStyle.primary)
    async def draw_winner(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host.id:
            return await interaction.response.send_message("❌ 操蛋，你又不是發起人，亂按什麼開獎啦，你後面有車喔！", ephemeral=True)
            
        self.stop() # 停止計時器，避免觸發 on_timeout
        
        if not self.participants:
            # 退還金額
            await self.cog.bot.db.update_balance(self.host.id, self.prize_amount)
            for child in self.children:
                child.disabled = True
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.description += "\n\n😢 **抽獎結束！可撥，沒人要你的臭錢，全退回去了。**"
            return await interaction.response.edit_message(embed=embed, view=self)

        winner_id = random.choice(list(self.participants))
        await self.cog.bot.db.update_balance(winner_id, self.prize_amount)
        
        for child in self.children:
            child.disabled = True
            
        winner = interaction.guild.get_member(winner_id)
        winner_mention = winner.mention if winner else f"<@{winner_id}>"
        
        embed = interaction.message.embeds[0]
        embed.description += f"\n\n🎉 **抽獎結束！全對！恭喜 {winner_mention} 爽拿 {self.prize_amount:,} 金幣！**\n*(錢已進帳，趕快去賭掉)*"
        embed.color = discord.Color.gold()
        
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.channel.send(f"🎉 靠北真爽！恭喜 {winner_mention} 白嫖了 {self.host.mention} 的 **{self.prize_amount:,}** 金幣！")

class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # 建立銀行資料表
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS bank (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)''')
        await self.bot.db.db.commit()
        self.daily_interest_task.start()

    def cog_unload(self):
        self.daily_interest_task.cancel()

    tz_tw = zoneinfo.ZoneInfo("Asia/Taipei")
    @tasks.loop(time=time(hour=0, minute=0, second=0, tzinfo=tz_tw))
    async def daily_interest_task(self):
        # 每天台灣時間凌晨 00:00，自動發放 1% 存款利息給所有人
        await self.bot.db.db.execute('UPDATE bank SET balance = CAST(balance * 1.01 AS INTEGER) WHERE balance > 0')
        await self.bot.db.db.commit()

    @daily_interest_task.before_loop
    async def before_daily_interest(self):
        await self.bot.wait_until_ready()

    async def get_bank_balance(self, user_id: int) -> int:
        async with self.bot.db.db.execute('SELECT balance FROM bank WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def update_bank_balance(self, user_id: int, amount: int):
        async with self.bot.db.db.execute('SELECT balance FROM bank WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            await self.bot.db.db.execute('UPDATE bank SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        else:
            await self.bot.db.db.execute('INSERT INTO bank (user_id, balance) VALUES (?, ?)', (user_id, amount))
        await self.bot.db.db.commit()

    # --- 基礎經濟指令 ---
    @commands.hybrid_command(name="bal", aliases=["balance", "錢包", "存款"], help="查看現金與銀行餘額")
    async def balance(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        wallet_balance = await self.bot.db.get_balance(member.id)
        bank_balance = await self.get_bank_balance(member.id)
        total = wallet_balance + bank_balance
        
        embed = discord.Embed(title="💳 你的破財產", color=discord.Color.gold())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="窮鬼", value=member.mention, inline=False)
        embed.add_field(name="👛 錢包 (現金)", value=f"**{wallet_balance:,}** 金幣", inline=True)
        embed.add_field(name="🏦 銀行存款", value=f"**{bank_balance:,}** 金幣", inline=True)
        embed.add_field(name="💰 總資產", value=f"**{total:,}** 金幣", inline=True)
        
        embed.set_footer(text="💡 沒錢就乖乖去 /work 當社畜啦！\n(銀行存款每天凌晨會自動發放 1% 利息喔)")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="deposit", aliases=["存錢", "dep"], help="將現金存入銀行生利息")
    @app_commands.describe(amount="要存入的金額 (輸入 0 或不填代表全存)")
    async def deposit(self, ctx: commands.Context, amount: int = 0):
        if amount < 0:
            return await ctx.send(embed=discord.Embed(title="❌ 錯誤", description="想存負數？當我是詐騙集團喔！", color=discord.Color.red()), ephemeral=True)
            
        wallet = await self.bot.db.get_balance(ctx.author.id)
        if wallet <= 0:
            return await ctx.send(embed=discord.Embed(title="❌ 笑死", description="你錢包一毛錢都沒有，存個寂寞喔！", color=discord.Color.red()), ephemeral=True)
        
        if amount == 0:
            amount = wallet # 全存
        elif amount > wallet:
            return await ctx.send(embed=discord.Embed(title="❌ 餘額不足", description=f"你錢包只有 **{wallet:,}** 金幣，裝什麼闊？", color=discord.Color.red()), ephemeral=True)
            
        await self.bot.db.update_balance(ctx.author.id, -amount)
        await self.update_bank_balance(ctx.author.id, amount)
        
        embed = discord.Embed(title="🏦 存款成功", description=f"已將 **{amount:,}** 金幣存入銀行！\n每天凌晨會自動發放 1% 利息，錢滾錢計畫通！", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="withdraw", aliases=["提款", "領錢", "with"], help="從銀行提出現金")
    @app_commands.describe(amount="要提出的金額 (輸入 0 或不填代表全領)")
    async def withdraw(self, ctx: commands.Context, amount: int = 0):
        if amount < 0:
            return await ctx.send(embed=discord.Embed(title="❌ 錯誤", description="提負數是怎樣？想逆向詐騙銀行喔！", color=discord.Color.red()), ephemeral=True)
            
        bank = await self.get_bank_balance(ctx.author.id)
        if bank <= 0:
            return await ctx.send(embed=discord.Embed(title="❌ 笑死", description="你銀行戶頭是空的，想當搶匪喔！", color=discord.Color.red()), ephemeral=True)
        
        if amount == 0:
            amount = bank # 全領
        elif amount > bank:
            return await ctx.send(embed=discord.Embed(title="❌ 餘額不足", description=f"你戶頭只有 **{bank:,}** 金幣，是要透支逆？", color=discord.Color.red()), ephemeral=True)
            
        await self.update_bank_balance(ctx.author.id, -amount)
        await self.bot.db.update_balance(ctx.author.id, amount)
        
        embed = discord.Embed(title="🏧 提款成功", description=f"已從銀行提出 **{amount:,}** 金幣！\n拿去賭場發家致富還是乖乖花掉？", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.cooldown(1, 86400, commands.BucketType.user)
    @commands.hybrid_command(name="daily", aliases=["每日", "簽到"], help="每日簽到領取金幣")
    async def daily(self, ctx: commands.Context):
        reward = 500
        await self.bot.db.update_balance(ctx.author.id, reward)
        
        embed = discord.Embed(title="📅 每日領低保", description=f"🎉 簽到成功！爽領 **{reward:,}** 金幣！", color=discord.Color.green())
        embed.set_footer(text=f"💰 目前餘額: {await self.bot.db.get_balance(ctx.author.id):,} 金幣")
        await ctx.send(embed=embed)

    @commands.cooldown(1, 600, commands.BucketType.user)
    @commands.hybrid_command(name="work", aliases=["打工"], help="打工賺取金幣")
    async def work(self, ctx: commands.Context):
        jobs = [
            "在 Discord 當免錢網管", "去巷口偷賣香腸被抓", "幫群主洗腳", "去麥當勞炸薯條被客訴",
            "在夜市擺攤賣盤子雞排", "幫阿嬤過馬路順便黑她零用錢", "去工地搬磚閃到腰", 
            "幫同學寫作業賺黑心錢", "在路邊發傳單被狗咬", "開台被暈船仔瘋狂斗內", 
            "幫網紅刷流量", "大夜班遇到奧客直接破防", "外送跑單跑到雷殘", 
            "去西門町拍抖音", "當預制菜試吃員", "在電子廠輪班當無情的奴隸",
            "當臨時演員領便當", "去海邊撿垃圾拿去賣", "修 Bug 修到心態炸裂被施捨獎金"
        ]
        salary = random.randint(50, 150)
        await self.bot.db.update_balance(ctx.author.id, salary)
        
        ach_msg = ""
        now = datetime.now(zoneinfo.ZoneInfo("Asia/Taipei"))
        if 2 <= now.hour < 5:
            # 直接使用 DatabaseManager 的優化方法！
            if await self.bot.db.check_and_add_achievement(ctx.author.id, '【夜貓子】'):
                ach_msg = "\n\n🦉 **成就解鎖！** 半夜不睡覺跑來打工，獲得稱號 **【夜貓子】**！"
                
        embed = discord.Embed(title="💼 破防社畜日記", description=f"{ctx.author.mention} {random.choice(jobs)}，勉強賺了 **{salary:,}** 金幣，這波硬控30秒！{ach_msg}", color=discord.Color.green())
        embed.set_footer(text=f"💰 目前餘額: {await self.bot.db.get_balance(ctx.author.id):,} 金幣")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pay", aliases=["轉帳"], help="轉帳金幣給其他玩家")
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0 or member.id == ctx.author.id:
            return await ctx.send(embed=discord.Embed(title="❌ 完全法克", description="不是，哥們，金額填錯還是你想轉給自己刷存？想屁吃喔！", color=discord.Color.red()), ephemeral=True)
        
        if await self.bot.db.get_balance(ctx.author.id) < amount:
            return await ctx.send(embed=discord.Embed(title="❌ 笑死", description=f"你口袋連 **{amount:,}** 都拿不出來，窮逼！", color=discord.Color.red()), ephemeral=True)
            
        await self.bot.db.update_balance(ctx.author.id, -amount)
        await self.bot.db.update_balance(member.id, amount)
        
        embed = discord.Embed(title="💸 撒幣成功，根本天才", description=f"超派，錢撒出去啦！**{amount:,}** 金幣塞給 {member.mention} 了！", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="addmoney", aliases=["印鈔", "發錢"], help="【老闆專用】偷偷印鈔票塞給指定玩家")
    @commands.is_owner()
    async def add_money(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(title="❌ 錯誤", description="印鈔數量必須大於 0 啊老闆！", color=discord.Color.red()), ephemeral=True)
            
        await self.bot.db.update_balance(member.id, amount)
        
        embed = discord.Embed(title="🤫 國家機器動得很厲害", description=f"老闆特權發動！已偷偷將 **{amount:,}** 金幣塞進 {member.mention} 的破錢包裡！\n*(天知地知你知我知)*", color=discord.Color.dark_theme())
        await ctx.send(embed=embed, ephemeral=True) # 隱藏訊息，群友完全看不到你開了後門

    @commands.hybrid_command(name="richest", aliases=["富豪榜", "首富"], help="查看全服總資產 (現金 + 存款) 最多的前十名富豪")
    async def richest(self, ctx: commands.Context):
        # 利用 UNION ALL 把錢包 (economy) 和銀行 (bank) 的錢加總起來排序
        query = '''
            SELECT user_id, SUM(balance) as total_balance
            FROM (
                SELECT user_id, balance FROM economy
                UNION ALL
                SELECT user_id, balance FROM bank
            )
            GROUP BY user_id
            ORDER BY total_balance DESC
            LIMIT 10
        '''
        async with self.bot.db.db.execute(query) as cursor:
            results = await cursor.fetchall()
            
        if not results:
            return await ctx.send(embed=discord.Embed(description="🤔 伺服器裡目前連一個有錢人都沒有喔！", color=discord.Color.light_grey()))
            
        embed = discord.Embed(title="🏆 全服富豪排行榜", description="來看看誰是真正的首富乾爹大戶 (現金 + 存款)：", color=discord.Color.gold())
        
        for i, (user_id, total) in enumerate(results):
            user = self.bot.get_user(user_id)
            name = user.display_name if user else f"低調富豪 ({user_id})"
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
            
            embed.add_field(name=f"{medal} 第 {i+1} 名：{name}", value=f"總資產: **{int(total):,}** 金幣", inline=False)
            
        embed.set_footer(text="💡 想要上榜嗎？多打工、存銀行或是去賭場試試手氣吧！")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))