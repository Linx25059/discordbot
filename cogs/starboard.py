import discord
from discord.ext import commands

class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # 初始化星標留言板所需的資料表
        # starboard_settings: 儲存伺服器的星標頻道與觸發門檻
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS starboard_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, threshold INTEGER DEFAULT 3)''')
        # starboard_messages: 紀錄已經轉發過的訊息，避免重複發布
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS starboard_messages (original_msg_id INTEGER PRIMARY KEY, starboard_msg_id INTEGER)''')
        await self.bot.db.db.commit()

    @commands.hybrid_command(name="setstarboard", aliases=["設定星標"], help="設定星標留言板頻道與觸發門檻")
    @commands.has_permissions(manage_channels=True)
    async def set_starboard(self, ctx, channel: discord.TextChannel, threshold: int = 3):
        if threshold < 1:
            return await ctx.send("❌ 門檻至少需要 1 顆星星喔！", ephemeral=True)
            
        await self.bot.db.db.execute('INSERT OR REPLACE INTO starboard_settings (guild_id, channel_id, threshold) VALUES (?, ?, ?)', (ctx.guild.id, channel.id, threshold))
        await self.bot.db.db.commit()
        
        embed = discord.Embed(
            title="🌟 星標留言板設定成功", 
            description=f"已將 {channel.mention} 設為星標留言板！\n只要訊息獲得 **{threshold}** 顆 ⭐ 以上，就會自動被收錄到這裡。", 
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._handle_star_reaction(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_star_reaction(payload)

    async def _handle_star_reaction(self, payload: discord.RawReactionActionEvent):
        # 只處理星星表情符號 (Emoji)
        if str(payload.emoji) != "⭐":
            return

        if not payload.guild_id:
            return

        # 獲取該伺服器的星標設定
        async with self.bot.db.db.execute('SELECT channel_id, threshold FROM starboard_settings WHERE guild_id = ?', (payload.guild_id,)) as cursor:
            settings = await cursor.fetchone()

        if not settings:
            return

        starboard_channel_id, threshold = settings
        
        # 不處理星標頻道本身的反應 (避免無限循環轉發)
        if payload.channel_id == starboard_channel_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        starboard_channel = guild.get_channel(starboard_channel_id)
        if not channel or not starboard_channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        # 計算星星數量
        star_reaction = discord.utils.get(message.reactions, element="⭐")
        star_count = star_reaction.count if star_reaction else 0

        # 檢查這則訊息是否已經在星標留言板中
        async with self.bot.db.db.execute('SELECT starboard_msg_id FROM starboard_messages WHERE original_msg_id = ?', (message.id,)) as cursor:
            result = await cursor.fetchone()

        if result:
            # 已經在留言板上，更新星星數量
            starboard_msg_id = result[0]
            try:
                starboard_msg = await starboard_channel.fetch_message(starboard_msg_id)
                content = f"⭐ **{star_count}** | {channel.mention}"
                
                if star_count < threshold:
                    # 如果有人收回星星導致數量低於門檻，自動刪除面板
                    await starboard_msg.delete()
                    await self.bot.db.db.execute('DELETE FROM starboard_messages WHERE original_msg_id = ?', (message.id,))
                    await self.bot.db.db.commit()
                else:
                    await starboard_msg.edit(content=content)
            except discord.NotFound:
                # 原星標訊息已被管理員手動刪除，從資料庫移除紀錄
                await self.bot.db.db.execute('DELETE FROM starboard_messages WHERE original_msg_id = ?', (message.id,))
                await self.bot.db.db.commit()
        else:
            # 尚未在留言板上，且達到了門檻
            if star_count >= threshold:
                embed = discord.Embed(description=message.content, color=discord.Color.gold(), timestamp=message.created_at)
                embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
                
                # 如果原訊息有圖片，將圖片附在面板上 (預設抓取第一張)
                if message.attachments:
                    for attachment in message.attachments:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            embed.set_image(url=attachment.url)
                            break
                
                # 加入原文跳轉按鈕
                embed.add_field(name="原文連結", value=f"[點擊跳轉到原訊息]({message.jump_url})", inline=False)
                
                content = f"⭐ **{star_count}** | {channel.mention}"
                starboard_msg = await starboard_channel.send(content=content, embed=embed)
                
                # 將紀錄存入資料庫
                await self.bot.db.db.execute('INSERT INTO starboard_messages (original_msg_id, starboard_msg_id) VALUES (?, ?)', (message.id, starboard_msg.id))
                await self.bot.db.db.commit()

async def setup(bot):
    await bot.add_cog(Starboard(bot))