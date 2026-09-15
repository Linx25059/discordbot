import discord
from discord.ext import commands

class AutoReply(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        pass

    @commands.Cog.listener()
    async def on_message(self, message):
        # 忽略機器人自己或私訊
        if message.author.bot or message.guild is None:
            return

        # 從資料庫抓取該伺服器所有的自動回覆設定 (包含 guild_id = 0 的全域回覆)
        replies = await self.bot.db.get_matching_auto_replies(message.guild.id)

        # 檢查訊息中是否包含關鍵字
        for keyword, reply in replies:
            if keyword in message.content:
                try:
                    await message.reply(reply, mention_author=False)
                    break # 觸發一次後就跳出，避免一句話觸發多個回覆造成洗頻
                except discord.HTTPException:
                    pass

    @commands.hybrid_command(name="addreply", aliases=["新增回覆"], help="【管理員】新增自訂關鍵字自動回覆")
    @commands.has_permissions(manage_messages=True)
    async def add_reply(self, ctx, keyword: str, *, reply: str):
        await self.bot.db.add_auto_reply(ctx.guild.id, keyword, reply)
        await ctx.send(embed=discord.Embed(title="✅ 新增自動回覆成功", description=f"**觸發關鍵字：** `{keyword}`\n**機器人回覆：** {reply}", color=discord.Color.green()))

    @commands.hybrid_command(name="delreply", aliases=["刪除回覆"], help="【管理員】刪除自訂關鍵字自動回覆")
    @commands.has_permissions(manage_messages=True)
    async def del_reply(self, ctx, keyword: str):
        exists = await self.bot.db.check_auto_reply_exists(ctx.guild.id, keyword)
        
        if not exists:
            # 檢查是不是全域的回覆
            is_global = await self.bot.db.check_auto_reply_exists(0, keyword)
            if is_global:
                return await ctx.send(embed=discord.Embed(description=f"❌ `{keyword}` 是全域自動回覆，一般的刪除指令無法處理喔。", color=discord.Color.red()), ephemeral=True)
            return await ctx.send(embed=discord.Embed(description=f"❌ 找不到關鍵字 `{keyword}` 的自動回覆設定喔。", color=discord.Color.red()), ephemeral=True)

        await self.bot.db.remove_auto_reply(ctx.guild.id, keyword)
        await ctx.send(embed=discord.Embed(description=f"🗑️ 已成功刪除關鍵字 `{keyword}` 的自動回覆。", color=discord.Color.green()))

    @commands.hybrid_command(name="listreplies", aliases=["回覆清單"], help="【管理員】列出目前伺服器所有的自動回覆設定")
    @commands.has_permissions(manage_messages=True)
    async def list_replies(self, ctx):
        replies = await self.bot.db.get_guild_auto_replies(ctx.guild.id)

        if not replies:
            return await ctx.send(embed=discord.Embed(description="📋 目前伺服器沒有設定任何自動回覆喔！", color=discord.Color.light_grey()))

        embed = discord.Embed(title="📋 自動回覆清單", color=discord.Color.blue())
        for guild_id, keyword, reply in replies:
            # 限制顯示長度，避免 Embed 欄位爆掉
            display_reply = reply[:50] + "..." if len(reply) > 50 else reply
            prefix = "🌍 [全域] " if guild_id == 0 else ""
            embed.add_field(name=f"{prefix}關鍵字：{keyword}", value=f"回覆：{display_reply}", inline=False)
            
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="addglobalreply", aliases=["新增全域回覆"], help="【機器人擁有者專用】新增全域自動回覆")
    @commands.is_owner()
    async def add_global_reply(self, ctx, keyword: str, *, reply: str):
        await self.bot.db.add_auto_reply(0, keyword, reply)
        await ctx.send(embed=discord.Embed(title="🌍 新增全域自動回覆成功", description=f"**觸發關鍵字：** `{keyword}`\n**機器人回覆：** {reply}\n*(此回覆將在所有伺服器生效)*", color=discord.Color.green()))

    @commands.hybrid_command(name="delglobalreply", aliases=["刪除全域回覆"], help="【機器人擁有者專用】刪除全域自動回覆")
    @commands.is_owner()
    async def del_global_reply(self, ctx, keyword: str):
        exists = await self.bot.db.check_auto_reply_exists(0, keyword)
        
        if not exists:
            return await ctx.send(embed=discord.Embed(description=f"❌ 找不到關鍵字 `{keyword}` 的全域自動回覆設定喔。", color=discord.Color.red()), ephemeral=True)

        await self.bot.db.remove_auto_reply(0, keyword)
        await ctx.send(embed=discord.Embed(description=f"🗑️ 已成功刪除全域關鍵字 `{keyword}` 的自動回覆。", color=discord.Color.green()))

async def setup(bot):
    await bot.add_cog(AutoReply(bot))