import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS update_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, last_version TEXT)''')
        await self.bot.db.db.commit()

        # --- 在這裡設定最新版本的更新內容 ---
        self.current_version = "1.3.1"
        self.changelog_title = f"✨ 機器人更新日誌 (v{self.current_version})"
        self.changelog_text = (
            "**🌐 跨國聊天翻譯功能上線 & Threads 連結修復增強！**\n"
            "• 🌐 **新增 Gemini 聊天翻譯系統：** 串接 Gemini 3.5 Flash 高速模型。支援 `/translate` 翻譯指令、訊息右鍵選單 `翻譯此訊息` (貼心自動判斷中英)、國旗 Emoji 反應直接翻譯，以及 `/translation_setup` 可設定特定頻道自動翻譯所有外文。\n"
            "• 🔗 **修復 Threads 手機分享網址：** 解決了從 Threads 手機 App 複製的分享連結 (`/share/...` 格式短網址) 導致預覽失效的問題，已升級為自動追蹤重新導向並解析還原為標準貼文網址。"
        )

        # 啟動時檢查是否需要推播更新
        self.bot.loop.create_task(self.auto_push_updates())

        # 重新整理成大分類結構
        self.categorized_cogs = {
            "🔍 查詢與資訊": {
                "Weather": "🌤️ 天氣預報查詢"
            },
            "🎵 影音與趣味互動": {
                "Music": "🎧 音樂點播",
                "ImageGen": "🖼️ 迷因與頭貼",
                "Food": "🍔 美食手搖推薦"
            },
            "🎮 遊戲與娛樂": {
                "GameRouletteCog": "🎰 遊戲抽籤面板",
                "Fun": "🎁 抽獎與活動"
            },
            "🛠️ 實用工具與自動化": {
                "LinkFixer": "🔗 社群連結修復",
                "Translation": "🌐 跨國聊天翻譯",
                "AutoVoice": "🎙️ 動態語音頻道",
                "Broadcast": "📡 新聞與遊戲推播",
                "AutoReply": "💬 自動回覆系統",
                "Logger": "📝 伺服器日誌紀錄",
                "Admin": "🛡️ 伺服器與機器人管理"
            },
            "ℹ️ 系統與資訊": {
                "Info": "📜 關於與狀態",
                "Help": "✨ 更新與幫助",
                "BugReport": "🚨 報錯單系統"
            }
        }

    async def auto_push_updates(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.db.execute('SELECT guild_id, channel_id, last_version FROM update_settings') as cursor:
            settings = await cursor.fetchall()

        for guild_id, channel_id, last_version in settings:
            if last_version != self.current_version:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    embed = discord.Embed(title=self.changelog_title, description=self.changelog_text, color=discord.Color.gold())
                    embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                    embed.set_footer(text="未來有新功能都會自動推播到這裡喔！")
                    try:
                        await channel.send("🚀 **機器人有新的更新內容囉！**", embed=embed)
                        await self.bot.db.db.execute('UPDATE update_settings SET last_version = ? WHERE guild_id = ?', (self.current_version, guild_id))
                        await self.bot.db.db.commit()
                    except Exception as e:
                        print(f"推播更新失敗 (Guild: {guild_id}): {e}")

    @commands.hybrid_command(name="help", aliases=["幫助", "指令", "h"], help="顯示所有可用的指令清單")
    async def custom_help(self, ctx):
        categorized_cog_names = []
        mapping = {} # 用來儲存分類與對應指令的字典
        for category, cogs in self.categorized_cogs.items():
            category_cmds = []
            for cog_name in cogs.keys():
                categorized_cog_names.append(cog_name)
                cog = self.bot.get_cog(cog_name)
                if not cog:
                    continue
                for cmd in cog.get_commands():
                    if cmd.hidden:
                        continue
                    
                    # 過濾掉管理員專用的指令 (不顯示)
                    is_admin_cmd = False
                    for check in cmd.checks:
                        qualname = getattr(check, '__qualname__', '')
                        if 'has_permissions' in qualname or 'has_guild_permissions' in qualname or 'is_owner' in qualname:
                            is_admin_cmd = True
                            break
                    if is_admin_cmd:
                        continue

                    allowed = True
                    try:
                        await cmd.can_run(ctx)
                    except commands.CommandOnCooldown:
                        allowed = True # 例：指令在冷卻中依然顯示
                    except Exception:
                        allowed = False # 缺乏權限則隱藏
                        
                    if allowed:
                        usage = f" {cmd.signature}" if cmd.signature else ""
                        prefix = "/" if isinstance(cmd, commands.HybridCommand) else "!"
                        category_cmds.append(f"**`{prefix}{cmd.name}{usage}`** - {cmd.short_doc or '無說明'}")
            
            if category_cmds:
                mapping[category] = category_cmds

        # 處理未分類的其他指令 (例如 Help 模組內的指令)
        other_cmds = []
        for cmd in self.bot.commands:
            if cmd.hidden or cmd.cog_name in categorized_cog_names or cmd.cog_name == "NSFW":
                continue
                
            # 過濾未分類的管理員指令
            is_admin_cmd = False
            for check in cmd.checks:
                qualname = getattr(check, '__qualname__', '')
                if 'has_permissions' in qualname or 'has_guild_permissions' in qualname or 'is_owner' in qualname:
                    is_admin_cmd = True
                    break
            if is_admin_cmd:
                continue

            allowed = True
            try:
                await cmd.can_run(ctx)
            except commands.CommandOnCooldown:
                allowed = True
            except Exception:
                allowed = False
                
            if allowed:
                usage = f" {cmd.signature}" if cmd.signature else ""
                prefix = "/" if isinstance(cmd, commands.HybridCommand) else "!"
                other_cmds.append(f"**`{prefix}{cmd.name}{usage}`** - {cmd.short_doc or '無說明'}")
                
        if other_cmds:
            mapping["📌 其他指令"] = other_cmds

        # 建立 Embed 顯示所有可用指令 (直接呈現，不使用下拉選單)
        embed = discord.Embed(title="🤖 機器人可用指令清單", description="以下是您目前可以使用的所有指令：", color=discord.Color.blurple())
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        for cat, cmds in mapping.items():
            embed.add_field(name=cat, value="\n".join(cmds), inline=False)
            
        embed.set_footer(text=f"查詢者: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="changelog", aliases=["update", "更新", "更新日誌"], help="查看機器人的最新更新內容")
    async def changelog(self, ctx):
        embed = discord.Embed(
            title=self.changelog_title,
            description=self.changelog_text,
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="若想知道未來的更新內容，也可以隨時使用此指令查看！", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="setupdate", aliases=["設定更新推播"], help="設定自動接收機器人更新公告的頻道")
    @commands.has_permissions(manage_channels=True)
    async def set_update_channel(self, ctx):
        embed = discord.Embed(
            title=self.changelog_title,
            description=self.changelog_text,
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="未來有新功能都會自動推播到這裡喔！", icon_url=ctx.author.display_avatar.url)
        
        await ctx.send(f"✅ 設定成功！未來最新的更新資訊都會發布在 {ctx.channel.mention}。", embed=embed)
        
        # 核心修復：設定頻道時，故意將資料庫中的版本號設為一個舊的或不存在的值 (例如 "0.0.0")
        await self.bot.db.db.execute('INSERT OR REPLACE INTO update_settings (guild_id, channel_id, last_version) VALUES (?, ?, ?)', 
                       (ctx.guild.id, ctx.channel.id, "0.0.0"))
        await self.bot.db.db.commit()

async def setup(bot):
    await bot.add_cog(Help(bot))