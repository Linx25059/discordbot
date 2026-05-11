import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import random
from datetime import datetime
import aiosqlite
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

    # --- 基礎經濟指令 ---
    @commands.hybrid_command(name="bal", aliases=["balance", "錢包"], help="查看餘額")
    async def balance(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        balance = await self.bot.db.get_balance(member.id)
        
        embed = discord.Embed(title="💳 你的破財產", color=discord.Color.gold())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="窮鬼", value=member.mention, inline=True)
        embed.add_field(name="剩餘零用錢", value=f"**{balance:,}** 金幣", inline=True)
        
        embed.set_footer(text="💡 沒錢就乖乖去 /work 當社畜啦，賽博對帳一下！")
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
        now = datetime.now()
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

async def setup(bot):
    await bot.add_cog(Economy(bot))