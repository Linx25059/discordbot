import discord
from discord.ext import commands
import sqlite3

class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('bot_database.db', timeout=10.0)
        self.c = self.conn.cursor()

        # 建立資料表：紀錄每個伺服器將日誌發送到哪個頻道
        self.c.execute('''CREATE TABLE IF NOT EXISTS log_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        self.conn.commit()

        # 快取邀請連結，用來追蹤是誰邀請新成員的
        self.invites_cache = {}
        self.bot.loop.create_task(self.update_all_invites())

    # 啟動時先將伺服器目前的邀請連結狀態存入快取
    async def update_all_invites(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                self.invites_cache[guild.id] = await guild.invites()
            except discord.Forbidden:
                pass # 如果沒有「管理伺服器」權限就跳過

    def get_log_channel(self, guild):
        self.c.execute('SELECT channel_id FROM log_settings WHERE guild_id = ?', (guild.id,))
        result = self.c.fetchone()
        if result:
            return guild.get_channel(result[0])
        return None

    @commands.hybrid_command(name="setlog", aliases=["設定日誌"], help="設定當前頻道為「伺服器日誌」紀錄頻道")
    @commands.has_permissions(manage_channels=True)
    async def set_log(self, ctx):
        self.c.execute('INSERT OR REPLACE INTO log_settings (guild_id, channel_id) VALUES (?, ?)', (ctx.guild.id, ctx.channel.id))
        self.conn.commit()
        await ctx.send(f"✅ 成功！已將 {ctx.channel.mention} 設為伺服器日誌頻道。\n我會開始在這裡紀錄**訊息刪除/編輯**，以及**成員進出與邀請狀態**！")

    # 🗑️ 紀錄刪除訊息
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: # 不紀錄機器人自己的刪除
            return
        log_channel = self.get_log_channel(message.guild)
        if log_channel:
            content = message.content if message.content else "(無文字內容或只有附件)"
            content = content[:1000] + "..." if len(content) > 1000 else content
            
            msg = f"🗑️ **訊息被刪除**\n**發送者**: {message.author.mention} (`{message.author.id}`)\n**頻道**: {message.channel.mention}\n**內容**: {content}"
            await log_channel.send(msg)

    # ✏️ 紀錄編輯訊息
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        # 如果是機器人，或是單純因為載入網址預覽而觸發的編輯，則忽略
        if before.author.bot or before.content == after.content:
            return
        log_channel = self.get_log_channel(before.guild)
        if log_channel:
            b_content = before.content[:1000] + "..." if len(before.content) > 1000 else (before.content or "(無內容)")
            a_content = after.content[:1000] + "..." if len(after.content) > 1000 else (after.content or "(無內容)")

            msg = f"✏️ **訊息被編輯**\n**發送者**: {before.author.mention} (`{before.author.id}`)\n**頻道**: {before.channel.mention} | 跳轉至訊息\n**📝 修改前**: {b_content}\n**📝 修改後**: {a_content}"
            await log_channel.send(msg)

    # 📥 紀錄成員加入與邀請者
    @commands.Cog.listener()
    async def on_member_join(self, member):
        log_channel = self.get_log_channel(member.guild)
        if log_channel:
            inviter = "未知 (可能使用了自訂連結或權限不足)"
            try:
                # 比對邀請連結的使用次數，找出是誰邀請的
                old_invites = self.invites_cache.get(member.guild.id, [])
                new_invites = await member.guild.invites()
                for old_invite in old_invites:
                    for new_invite in new_invites:
                        if old_invite.code == new_invite.code and new_invite.uses > old_invite.uses:
                            inviter = f"{new_invite.inviter.mention} (`{new_invite.code}`)"
                            break
                self.invites_cache[member.guild.id] = new_invites
            except discord.Forbidden:
                pass

            msg = f"📥 **成員加入**: {member.mention}\n**ID**: `{member.id}`\n**帳號建立時間**: {discord.utils.format_dt(member.created_at, style='F')}\n**邀請者**: {inviter}"
            await log_channel.send(msg)

    # 📤 紀錄成員離開
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        log_channel = self.get_log_channel(member.guild)
        if log_channel:
            msg = f"📤 **成員離開**: {member.name} ({member.mention})\n**ID**: `{member.id}`\n**原本加入時間**: {discord.utils.format_dt(member.joined_at, style='F') if member.joined_at else '未知'}"
            await log_channel.send(msg)

    # ⚙️ 紀錄指令使用 (成功執行時觸發)
    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if ctx.guild is None:
            return
        log_channel = self.get_log_channel(ctx.guild)
        if log_channel:
            msg = f"⚙️ **指令執行**\n**使用者**: {ctx.author.mention} (`{ctx.author.id}`)\n**頻道**: {ctx.channel.mention}\n**指令**: `{ctx.message.content}`"
            await log_channel.send(msg)

    # 🎙️ 紀錄語音頻道動態
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        log_channel = self.get_log_channel(member.guild)
        if not log_channel:
            return

        if before.channel is None and after.channel is not None:
            msg = f"🎙️ **加入語音**\n**使用者**: {member.mention} (`{member.id}`)\n**頻道**: {after.channel.mention}"
            await log_channel.send(msg)
        elif before.channel is not None and after.channel is None:
            msg = f"🔇 **離開語音**\n**使用者**: {member.mention} (`{member.id}`)\n**頻道**: {before.channel.mention}"
            await log_channel.send(msg)
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            msg = f"↔️ **移動語音**\n**使用者**: {member.mention} (`{member.id}`)\n**從**: {before.channel.mention} ➡️ {after.channel.mention}"
            await log_channel.send(msg)

    # 📁 紀錄頻道建立
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        log_channel = self.get_log_channel(channel.guild)
        if log_channel:
            msg = f"📁 **頻道建立**\n**名稱**: {channel.mention} (`{channel.name}`)\n**類型**: {channel.type}"
            await log_channel.send(msg)

    # 🗑️ 紀錄頻道刪除
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        log_channel = self.get_log_channel(channel.guild)
        if log_channel:
            msg = f"🗑️ **頻道刪除**\n**名稱**: `{channel.name}`\n**類型**: {channel.type}"
            await log_channel.send(msg)

async def setup(bot):
    await bot.add_cog(Logger(bot))