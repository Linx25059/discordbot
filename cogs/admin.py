import discord
from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 🛡️ 功能 1：一鍵清單 (!clear <數量>)
    @commands.hybrid_command(name="clear", help="清除指定數量的訊息 (預設為1則)")
    @commands.has_permissions(manage_messages=True) # 防護機制：只有具備「管理訊息」權限的人才能用
    async def clear(self, ctx, amount: int = 2):
        # amount + 1 是為了連同使用者剛輸入的 !clear 指令本身一起刪掉
        deleted = await ctx.channel.purge(limit=amount + 1)
        # 傳送提示，並設定 delete_after=3.0，讓這個提示 3 秒後自動消失，保持版面乾淨
        await ctx.send(f"🧹 已成功清除 {len(deleted)-1} 則訊息。", delete_after=3.0)

    # 🛡️ 功能 2：歡迎新成員系統 (自動觸發，不用打指令)
    @commands.Cog.listener()
    async def on_member_join(self, member):
        # 尋找伺服器中叫做 "一般" 的頻道 (你可以改成你群組裡的閒聊頻道名稱)
        channel = discord.utils.get(member.guild.text_channels, name="一般")
        
        if channel:
            # 建立一個精美的 Embed (嵌入式面板)
            embed = discord.Embed(
                title=f"🎉 歡迎 {member.name} 來到伺服器！",
                description=f"大家快來跟他打聲招呼吧！\n你是我們第 **{member.guild.member_count}** 位成員喔！",
                color=discord.Color.green()
            )
            # 把新成員的大頭貼放在面板右上角
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await channel.send(f"歡迎 {member.mention}！", embed=embed)

    # 🛡️ 功能 3：熱重載模組 (開發除錯必備)
    @commands.command(name="reload", help="【管理員】重新載入特定模組 (例如: !reload finance)")
    @commands.has_permissions(administrator=True)
    async def reload_cog(self, ctx, cog_name: str):
        try:
            # 如果模組一開始完全沒載入成功，要使用 load_extension；如果是要更新，則用 reload_extension
            if f"cogs.{cog_name}" in self.bot.extensions:
                await self.bot.reload_extension(f"cogs.{cog_name}")
            else:
                await self.bot.load_extension(f"cogs.{cog_name}")
            await ctx.send(f"✅ 成功載入模組：`cogs/{cog_name}.py`")
        except Exception as e:
            await ctx.send(f"❌ 載入 `{cog_name}` 失敗：\n```py\n{e}\n```")

async def setup(bot):
    await bot.add_cog(Admin(bot))