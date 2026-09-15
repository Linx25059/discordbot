import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class AutoVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        pass

    @commands.hybrid_command(name="setupvoice", aliases=["設定語音"], help="在當前類別建立一個「自動語音生成頻道」")
    @commands.has_permissions(manage_channels=True)
    async def setup_voice(self, ctx):
        category = ctx.channel.category
        
        # 在與輸入指令相同的類別 (Category) 中建立一個語音頻道
        new_channel = await ctx.guild.create_voice_channel(name="➕ 點我建立頻道", category=category)
        
        await self.bot.db.add_auto_voice_generator(new_channel.id)
        
        await ctx.send(embed=discord.Embed(title="🎙️ 動態語音已設定完成", description=f"請至 {new_channel.mention} 查看！\n未來有成員加入時，會自動幫他們建立專屬的語音頻道！", color=discord.Color.green()))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # 狀況 1：使用者「離開」了某個頻道，我們要檢查是不是動態包廂空了，空了就刪掉
        if before.channel is not None:
            is_temp = await self.bot.db.is_auto_voice_temp(before.channel.id)
            if is_temp:
                # 如果該包廂裡面已經沒有半個人了
                if len(before.channel.members) == 0:
                    try:
                        await before.channel.delete(reason="頻道內已無成員，自動刪除")
                        await self.bot.db.remove_auto_voice_temp(before.channel.id)
                    except Exception as e:
                        logger.error(f"刪除動態頻道時發生錯誤: {e}", exc_info=True)

        # 狀況 2：使用者「加入」了某個頻道，我們要檢查是不是踩到了生成器 (➕ 點我開房)
        if after.channel is not None:
            is_generator = await self.bot.db.is_auto_voice_generator(after.channel.id)
            if is_generator:
                try:
                    # 在母頻道所屬的類別底下，建立專屬包廂
                    new_channel = await member.guild.create_voice_channel(name=f"🎧 {member.display_name} 的語音頻道", category=after.channel.category)
                    
                    await self.bot.db.add_auto_voice_temp(new_channel.id)

                    # 把剛加入母頻道的人，立刻拉進專屬包廂
                    await member.move_to(new_channel)
                except Exception as e:
                    logger.error(f"建立動態頻道時發生錯誤: {e}", exc_info=True)

async def setup(bot):
    await bot.add_cog(AutoVoice(bot))