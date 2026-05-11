import discord
from discord import app_commands
from discord.ext import commands
import random

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
            embed.color = discord.Color.dark_grey()
            embed.description += "\n\n😢 **時間到！因為沒有人參加，獎金已退還給發起人。**"
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
        embed.description += f"\n\n⏰ **時間到自動開獎！恭喜 {winner_mention} 贏得了 {self.prize_amount:,} 金幣！**\n*(獎金已匯入錢包)*"
        embed.color = discord.Color.gold()
        try:
            await self.message.edit(embed=embed, view=self)
            await self.message.channel.send(f"🎉 恭喜 {winner_mention} 抽中了 {self.host.mention} 提供的 **{self.prize_amount:,}** 金幣！")
        except: pass

    @discord.ui.button(label="🎉 參加抽獎", style=discord.ButtonStyle.success)
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.host.id:
            return await interaction.response.send_message("❌ 你是發起人，不能參加自己的抽獎喔！", ephemeral=True)
            
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("❌ 你已經參加過了喔！", ephemeral=True)
            
        self.participants.add(interaction.user.id)
        
        embed = interaction.message.embeds[0]
        embed.set_footer(text=f"目前參加人數：{len(self.participants)} 人 | 5 分鐘後自動開獎")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏆 提早開獎 (發起人專用)", style=discord.ButtonStyle.primary)
    async def draw_winner(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host.id:
            return await interaction.response.send_message("❌ 只有發起人可以提早開獎喔！", ephemeral=True)
            
        self.stop() # 停止計時器，避免觸發 on_timeout
        
        if not self.participants:
            # 退還金額
            await self.cog.bot.db.update_balance(self.host.id, self.prize_amount)
            for child in self.children:
                child.disabled = True
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.dark_grey()
            embed.description += "\n\n😢 **抽獎結束，沒有人參加，獎金已退還給發起人。**"
            return await interaction.response.edit_message(embed=embed, view=self)

        winner_id = random.choice(list(self.participants))
        await self.cog.bot.db.update_balance(winner_id, self.prize_amount)
        
        for child in self.children:
            child.disabled = True
            
        winner = interaction.guild.get_member(winner_id)
        winner_mention = winner.mention if winner else f"<@{winner_id}>"
        
        embed = interaction.message.embeds[0]
        embed.description += f"\n\n🎉 **抽獎結束！恭喜 {winner_mention} 贏得了 {self.prize_amount:,} 金幣！**\n*(獎金已匯入錢包)*"
        embed.color = discord.Color.gold()
        
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.channel.send(f"🎉 恭喜 {winner_mention} 抽中了 {self.host.mention} 提供的 **{self.prize_amount:,}** 金幣！")

class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="giveaway", aliases=["抽獎"], help="發起金幣抽獎，發放給伺服器的大家！")
    @app_commands.describe(amount="要抽出的金幣總額")
    async def giveaway(self, ctx: commands.Context, amount: int):
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(title="❌ 操作失敗", description="抽獎金額必須大於 0 喔！", color=discord.Color.red()), ephemeral=True)

        # 檢查發起人錢包餘額
        balance = await self.bot.db.get_balance(ctx.author.id)
        if balance < amount:
            return await ctx.send(embed=discord.Embed(title="❌ 餘額不足", description=f"你的錢包裡只有 **{balance:,}** 金幣，不夠發起抽獎！", color=discord.Color.red()), ephemeral=True)

        # 立即扣除發起人的金幣
        await self.bot.db.update_balance(ctx.author.id, -amount)

        embed = discord.Embed(
            title="🎁 金幣大放送！",
            description=f"{ctx.author.mention} 發起了抽獎活動！\n\n💰 **總獎金：** `{amount:,}` 金幣\n👇 點擊下方按鈕立刻參加！",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="目前參加人數：0 人 | 5 分鐘後自動開獎")

        view = GiveawayView(self, ctx.author, amount)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

async def setup(bot):
    await bot.add_cog(Fun(bot))