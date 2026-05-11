import discord
from discord.ext import commands
from datetime import datetime

class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # 快取邀請連結，用來追蹤是誰邀請新成員的
        self.invites_cache = {}
        self.bot.loop.create_task(self.update_all_invites())

    async def cog_load(self):
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS log_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        await self.bot.db.db.commit()

    # 啟動時先將伺服器目前的邀請連結狀態存入快取
    async def update_all_invites(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                self.invites_cache[guild.id] = await guild.invites()
            except discord.Forbidden:
                pass # 如果沒有「管理伺服器」權限就跳過

    async def get_log_channel(self, guild):
        async with self.bot.db.db.execute('SELECT channel_id FROM log_settings WHERE guild_id = ?', (guild.id,)) as cursor:
            result = await cursor.fetchone()
        if result:
            return guild.get_channel(result[0])
        return None

    @commands.hybrid_command(name="setlog", aliases=["設定日誌"], help="設定當前頻道為「伺服器日誌」紀錄頻道")
    @commands.has_permissions(manage_channels=True)
    async def set_log(self, ctx):
        await self.bot.db.db.execute('INSERT OR REPLACE INTO log_settings (guild_id, channel_id) VALUES (?, ?)', (ctx.guild.id, ctx.channel.id))
        await self.bot.db.db.commit()
        await ctx.send(f"✅ 設定成功！已將 {ctx.channel.mention} 設為伺服器的日誌紀錄頻道。")

    # 🗑️ 紀錄刪除訊息
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: # 不紀錄機器人自己的刪除
            return
        log_channel = await self.get_log_channel(message.guild)
        if log_channel:
            content = message.content if message.content else "(無文字內容或只有附件)"
            content = content[:1000] + "..." if len(content) > 1000 else content
            
            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message.author.name} 在 #{message.channel.name} 刪除了訊息: {content}"
            await log_channel.send(msg)

    # ✏️ 紀錄編輯訊息
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        # 如果是機器人，或是單純因為載入網址預覽而觸發的編輯，則忽略
        if before.author.bot or before.content == after.content:
            return
        log_channel = await self.get_log_channel(before.guild)
        if log_channel:
            b_content = before.content[:1000] + "..." if len(before.content) > 1000 else (before.content or "(無內容)")
            a_content = after.content[:1000] + "..." if len(after.content) > 1000 else (after.content or "(無內容)")

            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {before.author.name} 在 #{before.channel.name} 編輯了訊息 | 原內容: {b_content} -> 新內容: {a_content}"
            await log_channel.send(msg)

    # 📥 紀錄成員加入與邀請者
    @commands.Cog.listener()
    async def on_member_join(self, member):
        log_channel = await self.get_log_channel(member.guild)
        if log_channel:
            inviter = "未知"
            try:
                # 比對邀請連結的使用次數，找出是誰邀請的
                old_invites = self.invites_cache.get(member.guild.id, [])
                new_invites = await member.guild.invites()
                for old_invite in old_invites:
                    for new_invite in new_invites:
                        if old_invite.code == new_invite.code and new_invite.uses > old_invite.uses:
                            inviter = new_invite.inviter.name
                            break
                self.invites_cache[member.guild.id] = new_invites
            except discord.Forbidden:
                pass

            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {member.name} 加入了伺服器 (邀請者: {inviter})"
            await log_channel.send(msg)

    # 📤 紀錄成員離開
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        log_channel = await self.get_log_channel(member.guild)
        if log_channel:
            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {member.name} 離開了伺服器"
            await log_channel.send(msg)

    # ⚙️ 紀錄指令使用 (成功執行時觸發)
    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if ctx.guild is None:
            return
        log_channel = await self.get_log_channel(ctx.guild)
        if log_channel:
            # 判斷是否為斜線指令 (Slash Command)
            if ctx.interaction:
                # 組合出指令名稱與後方的參數
                args = " ".join([f"{k}:{v}" for k, v in ctx.kwargs.items()])
                command_text = f"/{ctx.command.qualified_name} {args}".strip()
            else:
                # 如果是傳統前綴指令 (!指令)
                command_text = ctx.message.content
                
            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {ctx.author.name} 在 #{ctx.channel.name} 執行了指令: {command_text}"
            await log_channel.send(msg)

    # ❌ 紀錄錯誤/不存在的指令
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # 只捕捉「找不到指令」的錯誤
        if isinstance(error, commands.CommandNotFound):
            if ctx.guild is None:
                return
            log_channel = await self.get_log_channel(ctx.guild)
            if log_channel:
                msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {ctx.author.name} 在 #{ctx.channel.name} 嘗試執行不存在的指令: {ctx.message.content}"
                await log_channel.send(msg)

    # 🎙️ 紀錄語音頻道動態
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        log_channel = await self.get_log_channel(member.guild)
        if not log_channel:
            return

        if before.channel is None and after.channel is not None:
            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {member.name} 加入了語音頻道: {after.channel.name}"
            await log_channel.send(msg)
        elif before.channel is not None and after.channel is None:
            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {member.name} 離開了語音頻道: {before.channel.name}"
            await log_channel.send(msg)
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {member.name} 將語音頻道從 {before.channel.name} 移動到了 {after.channel.name}"
            await log_channel.send(msg)

    # 📁 紀錄頻道建立
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        log_channel = await self.get_log_channel(channel.guild)
        if log_channel:
            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 頻道被建立: {channel.name} ({channel.type})"
            await log_channel.send(msg)

    # 🗑️ 紀錄頻道刪除
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        log_channel = await self.get_log_channel(channel.guild)
        if log_channel:
            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 頻道被刪除: {channel.name} ({channel.type})"
            await log_channel.send(msg)

async def setup(bot):
    await bot.add_cog(Logger(bot))