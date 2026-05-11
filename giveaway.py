import discord
from discord.ext import commands
import asyncio
import random
import re
from datetime import datetime, timedelta

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 持久化視圖
        self.participants = set()

    @discord.ui.button(label="🎉 參加抽獎", style=discord.ButtonStyle.success, custom_id="giveaway_join_btn")
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            self.participants.remove(interaction.user.id)
            await interaction.response.send_message("❌ 幫你取消囉，不想抽了嗎？", ephemeral=True)
        else:
            self.participants.add(interaction.user.id)
            await interaction.response.send_message("✅ 報名成功！祝你中大獎啦！", ephemeral=True)
        
        # 即時更新面板上的參加人數
        embed = interaction.message.embeds[0]
        embed.set_footer(text=f"目前參加人數: {len(self.participants)} 人")
        await interaction.message.edit(embed=embed)

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(GiveawayView()) # 註冊持久化按鈕

    @commands.hybrid_command(name="giveaway", aliases=["抽獎"], help="舉辦一場抽獎活動 (時間格式: 10m, 1h, 1d)")
    @commands.has_permissions(manage_messages=True)
    async def start_giveaway(self, ctx, time_str: str, *, prize: str):
        # 解析時間字串
        time_dict = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        match = re.match(r"(\d+)([smhd])", time_str.lower())
        if not match:
            return await ctx.send("❌ 時間格式錯誤！請使用數字加上單位 (s秒, m分, h時, d天)\n👉 例如：`/giveaway 10m 1000金幣`", ephemeral=True)
            
        seconds = int(match.group(1)) * time_dict[match.group(2)]
        end_time = datetime.now() + timedelta(seconds=seconds)
        end_timestamp = int(end_time.timestamp())

        embed = discord.Embed(title="🎉 抽獎活動開始啦！", description=f"**🎁 獎品：** {prize}\n**⏳ 結束時間：** <t:{end_timestamp}:R>\n\n點擊下方按鈕即可參加！", color=discord.Color.gold())
        embed.set_footer(text="目前參加人數: 0 人")
        
        view = GiveawayView()
        msg = await ctx.send(embed=embed, view=view)
        
        # 在背景等待指定的時間
        await asyncio.sleep(seconds)
        
        if not view.participants:
            return await ctx.send(f"❌ **{prize}** 抽獎結束，結果竟然沒半個人來抽，太雖了吧...")
            
        # 開獎
        winner_id = random.choice(list(view.participants))
        end_embed = discord.Embed(title="🎊 抽獎活動已結束！", description=f"**🎁 獎品：** {prize}\n**👑 得獎者：** <@{winner_id}>\n\n總參加人數: {len(view.participants)} 人", color=discord.Color.dark_gray())
        await msg.edit(embed=end_embed, view=None)
        await ctx.send(f"🎉 太爽了吧！恭喜 <@{winner_id}> 抽中 **{prize}**！")

async def setup(bot):
    await bot.add_cog(Giveaway(bot))