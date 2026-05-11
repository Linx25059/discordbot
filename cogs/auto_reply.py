import discord
from discord.ext import commands

class AutoReply(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # 檢查舊的 auto_replies 是否缺少 guild_id 欄位
        async with self.bot.db.db.execute("PRAGMA table_info(auto_replies)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            
        if columns and "guild_id" not in columns:
            # 執行資料表遷移 (Schema Migration)
            await self.bot.db.db.execute("ALTER TABLE auto_replies RENAME TO auto_replies_backup")
            await self.bot.db.db.execute('''CREATE TABLE auto_replies (guild_id INTEGER, keyword TEXT, reply TEXT, PRIMARY KEY (guild_id, keyword))''')
            # 將舊資料移入新表，預設 guild_id = 0 (作為全域回覆)
            await self.bot.db.db.execute("INSERT INTO auto_replies (guild_id, keyword, reply) SELECT 0, keyword, reply FROM auto_replies_backup")
            await self.bot.db.db.execute("DROP TABLE auto_replies_backup")
            
        # 確保資料表結構正確
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS auto_replies (guild_id INTEGER, keyword TEXT, reply TEXT, PRIMARY KEY (guild_id, keyword))''')
        
        # 清除我們先前產生出來的暫時性資料表
        await self.bot.db.db.execute("DROP TABLE IF EXISTS server_auto_replies")
        await self.bot.db.db.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        # 忽略機器人自己或私訊
        if message.author.bot or message.guild is None:
            return

        # 從資料庫抓取該伺服器所有的自動回覆設定 (包含 guild_id = 0 的全域回覆)
        async with self.bot.db.db.execute('SELECT keyword, reply FROM auto_replies WHERE guild_id = ? OR guild_id = 0', (message.guild.id,)) as cursor:
            replies = await cursor.fetchall()

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
        await self.bot.db.db.execute('INSERT OR REPLACE INTO auto_replies (guild_id, keyword, reply) VALUES (?, ?, ?)', (ctx.guild.id, keyword, reply))
        await self.bot.db.db.commit()
        await ctx.send(embed=discord.Embed(title="✅ 新增自動回覆成功", description=f"**觸發關鍵字：** `{keyword}`\n**機器人回覆：** {reply}", color=discord.Color.green()))

    @commands.hybrid_command(name="delreply", aliases=["刪除回覆"], help="【管理員】刪除自訂關鍵字自動回覆")
    @commands.has_permissions(manage_messages=True)
    async def del_reply(self, ctx, keyword: str):
        async with self.bot.db.db.execute('SELECT 1 FROM auto_replies WHERE guild_id = ? AND keyword = ?', (ctx.guild.id, keyword)) as cursor:
            exists = await cursor.fetchone()
        
        if not exists:
            # 檢查是不是全域的回覆
            async with self.bot.db.db.execute('SELECT 1 FROM auto_replies WHERE guild_id = 0 AND keyword = ?', (keyword,)) as cursor:
                if await cursor.fetchone():
                    return await ctx.send(embed=discord.Embed(description=f"❌ `{keyword}` 是全域自動回覆，一般的刪除指令無法處理喔。", color=discord.Color.red()), ephemeral=True)
            return await ctx.send(embed=discord.Embed(description=f"❌ 找不到關鍵字 `{keyword}` 的自動回覆設定喔。", color=discord.Color.red()), ephemeral=True)

        await self.bot.db.db.execute('DELETE FROM auto_replies WHERE guild_id = ? AND keyword = ?', (ctx.guild.id, keyword))
        await self.bot.db.db.commit()
        await ctx.send(embed=discord.Embed(description=f"🗑️ 已成功刪除關鍵字 `{keyword}` 的自動回覆。", color=discord.Color.green()))

    @commands.hybrid_command(name="listreplies", aliases=["回覆清單"], help="【管理員】列出目前伺服器所有的自動回覆設定")
    @commands.has_permissions(manage_messages=True)
    async def list_replies(self, ctx):
        async with self.bot.db.db.execute('SELECT guild_id, keyword, reply FROM auto_replies WHERE guild_id = ? OR guild_id = 0', (ctx.guild.id,)) as cursor:
            replies = await cursor.fetchall()

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
        await self.bot.db.db.execute('INSERT OR REPLACE INTO auto_replies (guild_id, keyword, reply) VALUES (?, ?, ?)', (0, keyword, reply))
        await self.bot.db.db.commit()
        await ctx.send(embed=discord.Embed(title="🌍 新增全域自動回覆成功", description=f"**觸發關鍵字：** `{keyword}`\n**機器人回覆：** {reply}\n*(此回覆將在所有伺服器生效)*", color=discord.Color.green()))

    @commands.hybrid_command(name="delglobalreply", aliases=["刪除全域回覆"], help="【機器人擁有者專用】刪除全域自動回覆")
    @commands.is_owner()
    async def del_global_reply(self, ctx, keyword: str):
        async with self.bot.db.db.execute('SELECT 1 FROM auto_replies WHERE guild_id = 0 AND keyword = ?', (keyword,)) as cursor:
            exists = await cursor.fetchone()
        
        if not exists:
            return await ctx.send(embed=discord.Embed(description=f"❌ 找不到關鍵字 `{keyword}` 的全域自動回覆設定喔。", color=discord.Color.red()), ephemeral=True)

        await self.bot.db.db.execute('DELETE FROM auto_replies WHERE guild_id = 0 AND keyword = ?', (keyword,))
        await self.bot.db.db.commit()
        await ctx.send(embed=discord.Embed(description=f"🗑️ 已成功刪除全域關鍵字 `{keyword}` 的自動回覆。", color=discord.Color.green()))

async def setup(bot):
    await bot.add_cog(AutoReply(bot))