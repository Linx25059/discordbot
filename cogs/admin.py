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

    # 🛡️ 功能 4：一鍵熱修復 (Hotfix) - 重新載入所有模組並同步指令
    @commands.command(name="hotfix", aliases=["熱修", "reloadall"], help="【機器人擁有者專用】一鍵重新載入所有模組並同步斜線指令")
    @commands.is_owner() # 為了安全與避免觸發 Discord API 速率限制，限制只有機器人開發者能使用
    async def hotfix(self, ctx):
        msg = await ctx.send("🔄 開始執行熱修復程序...\n正在重新載入所有模組...")
        
        loaded_cogs = list(self.bot.extensions.keys())
        success_count = 0
        error_list = []
        
        for cog in loaded_cogs:
            try:
                await self.bot.reload_extension(cog)
                success_count += 1
            except Exception as e:
                error_list.append(f"`{cog}`: {e}")
                
        await msg.edit(content="🔄 模組重新載入完畢，正在同步斜線指令 (這可能會花幾秒鐘)...")
        
        try:
            synced = await self.bot.tree.sync()
            sync_msg = f"✅ 成功同步了 {len(synced)} 個斜線指令！"
        except Exception as e:
            sync_msg = f"❌ 同步斜線指令失敗: {e}"
            
        embed = discord.Embed(title="🛠️ 熱修復 (Hotfix) 執行結果", color=discord.Color.green() if not error_list else discord.Color.orange())
        embed.add_field(name="模組重新載入", value=f"成功: {success_count} / {len(loaded_cogs)}", inline=False)
        if error_list:
            embed.add_field(name="⚠️ 載入失敗的模組", value="\n".join(error_list)[:1024], inline=False)
        embed.add_field(name="斜線指令", value=sync_msg, inline=False)
        
        await msg.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot))