import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import random
from datetime import datetime
import aiosqlite
from typing import Optional
import logging

class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- 基礎經濟指令 ---
    @commands.hybrid_command(name="bal", aliases=["balance", "錢包"], help="查看餘額")
    async def balance(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        balance = await self.bot.db.get_balance(member.id)
        
        embed = discord.Embed(title="💳 帳戶餘額", color=discord.Color.gold())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="帳戶持有人", value=member.mention, inline=True)
        embed.add_field(name="目前餘額", value=f"**{balance:,}** 金幣", inline=True)
        
        embed.set_footer(text="💡 提示：可以多使用 /work 打工來賺取金幣喔！")
        await ctx.send(embed=embed)

    @commands.cooldown(1, 86400, commands.BucketType.user)
    @commands.hybrid_command(name="daily", aliases=["每日", "簽到"], help="每日簽到領取金幣")
    async def daily(self, ctx: commands.Context):
        reward = 500
        await self.bot.db.update_balance(ctx.author.id, reward)
        
        embed = discord.Embed(title="📅 每日簽到", description=f"🎉 簽到成功！領取了 **{reward:,}** 金幣！", color=discord.Color.green())
        embed.set_footer(text=f"💰 目前餘額: {await self.bot.db.get_balance(ctx.author.id):,} 金幣")
        await ctx.send(embed=embed)

    @commands.cooldown(1, 600, commands.BucketType.user)
    @commands.hybrid_command(name="work", aliases=["打工"], help="打工賺取金幣")
    async def work(self, ctx: commands.Context):
        jobs = [
            "去麥當勞炸薯條", "在便利商店值大夜班", "幫忙鄰居修電腦", "去路口發傳單",
            "幫狗狗洗澡", "兼職做外送跑單", "在咖啡廳打工", "幫忙整理文件",
            "去夜市幫忙擺攤", "當網拍小幫手", "幫忙鄰居遛狗", "參加市調座談會",
            "幫忙代購排隊", "在書店安靜地排書", "兼職當活動工作人員"
        ]
        salary = random.randint(50, 150)
        await self.bot.db.update_balance(ctx.author.id, salary)
        
        ach_msg = ""
        now = datetime.now()
        if 2 <= now.hour < 5:
            # 直接使用 DatabaseManager 的優化方法！
            if await self.bot.db.check_and_add_achievement(ctx.author.id, '【夜貓子】'):
                ach_msg = "\n\n🦉 **成就解鎖！** 深夜還在努力打工，獲得稱號 **【夜貓子】**！"
                
        embed = discord.Embed(title="💼 打工順利", description=f"{ctx.author.mention} {random.choice(jobs)}，賺了 **{salary:,}** 金幣！辛苦啦！{ach_msg}", color=discord.Color.green())
        embed.set_footer(text=f"💰 目前餘額: {await self.bot.db.get_balance(ctx.author.id):,} 金幣")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pay", aliases=["轉帳"], help="轉帳金幣給其他玩家")
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0 or member.id == ctx.author.id:
            return await ctx.send(embed=discord.Embed(title="❌ 操作失敗", description="轉帳金額必須大於 0，且不能轉帳給自己喔！", color=discord.Color.red()), ephemeral=True)
        
        if await self.bot.db.get_balance(ctx.author.id) < amount:
            return await ctx.send(embed=discord.Embed(title="❌ 餘額不足", description=f"你的錢包餘額不足以轉帳 **{amount:,}** 金幣！", color=discord.Color.red()), ephemeral=True)
            
        await self.bot.db.update_balance(ctx.author.id, -amount)
        await self.bot.db.update_balance(member.id, amount)
        
        embed = discord.Embed(title="💸 轉帳成功", description=f"已成功將 **{amount:,}** 金幣轉給了 {member.mention}！", color=discord.Color.green())
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))