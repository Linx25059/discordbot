import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS update_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, last_version TEXT)''')
        await self.bot.db.db.commit()

        # --- 在這裡設定最新版本的更新內容 ---
        self.current_version = "1.3"
        self.changelog_title = f"✨ 機器人更新日誌 (v{self.current_version})"
        self.changelog_text = (
            "**🚀 v1.3 版本大更新發布！**\n"
            "• 🌤️ **天氣系統升級：** 支援個人專屬地點綁定 (`/setweather`)、每日早晨天氣推播 (`/dailyweather`)，並新增依據時區變化的日夜動態縮圖！\n"
            "• 🚗 **老司機車庫：** 新增群友投稿系統 (`/submit_av`) 與熱門車牌排行榜 (`/av_top`)，還能在抽籤時為喜歡的片單點讚！\n"
            "• ⚙️ **核心優化：** 解決斜線指令重複問題，新增一鍵清除指令快取，並支援開發者無縫動態更新環境變數 (`!update_env`)。\n"
        )

        # 啟動時檢查是否需要推播更新
        self.bot.loop.create_task(self.auto_push_updates())

        # 重新整理成大分類結構
        self.categorized_cogs = {
            "🎉 娛樂與遊戲": {
                "Fun": "🎉 趣味活動",
                "ImageGen": "🖼️ 圖片產生",
                "GameRouletteCog": "🎰 遊戲抽籤",
                "Music": "🎵 音樂播放",
                "JerkCounter": "💦 趣味計數"
            },
            "💸 經濟系統": {
                "Economy": "💸 帳戶與經濟",
                "Gamble": "🎲 娛樂賭場",
                "Finance": "📈 虛擬股市"
            },
            "🏆 等級系統": {
                "Leveling": "🏆 活躍排行榜",
                "Profile": "🪪 個人檔案"
            },
            "🛠️ 實用工具": {
                "AIChat": "🤖 AI 聊天助理",
                "Weather": "🌤️ 天氣查詢",
                "Food": "🍔 美食與飲品推薦",
                "Info": "ℹ️ 關於我"
            },
            "🔞 隱藏專區": {
                "NSFW": "🚗 我很好片"
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
        embed = discord.Embed(
            title="🤖 機器人指令清單",
            description="以下是目前所有可用的指令：\n*(提示：在對話框輸入 `/` 可以查看各指令的詳細說明喔！)*",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # 依據分類動態加入指令
        categorized_cog_names = []
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
                    
                    # 過濾掉管理員專用的指令 (即使呼叫者是管理員，也不在普通 help 顯示)
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
                        allowed = False # 缺乏權限或其他錯誤則隱藏
                        
                    if allowed:
                        usage = f" {cmd.signature}" if cmd.signature else ""
                        category_cmds.append(f"**`/{cmd.name}{usage}`** - {cmd.short_doc or '無說明'}")
            
            if category_cmds:
                embed.add_field(name=category, value="\n".join(category_cmds), inline=False)

        # 處理未分類的其他指令 (例如 Help 模組內的指令)
        other_cmds = []
        for cmd in self.bot.commands:
            if cmd.hidden or cmd.cog_name in categorized_cog_names:
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
                other_cmds.append(f"**`/{cmd.name}{usage}`** - {cmd.short_doc or '無說明'}")
                
        if other_cmds:
            embed.add_field(name="📌 其他指令", value="\n".join(other_cmds), inline=False)

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
        # 這樣當機器人下次帶著新版本號重啟時，版本比對 (last_version != self.current_version) 才會是 True，進而觸發更新推播。
        await self.bot.db.db.execute('INSERT OR REPLACE INTO update_settings (guild_id, channel_id, last_version) VALUES (?, ?, ?)', 
                       (ctx.guild.id, ctx.channel.id, "0.0.0"))
        await self.bot.db.db.commit()

    @commands.hybrid_command(name="adminhelp", aliases=["allcmds", "ah"], help="【管理員專用】查看所有指令 (包含隱藏及管理權限指令)")
    @commands.has_permissions(administrator=True)
    async def admin_help(self, ctx):
        embed = discord.Embed(
            title="🛠️ 管理員指令清單",
            description="以下列出目前系統載入的**所有指令**（包含隱藏與管理員專用指令）：",
            color=discord.Color.red()
        )

        # 整理所有指令並依據 Cog 分類
        cogs_dict = {}
        for cmd in self.bot.commands:
            cog_name = cmd.cog_name or "未分類指令"
            if cog_name not in cogs_dict:
                cogs_dict[cog_name] = []
            cogs_dict[cog_name].append(cmd)

        for cog_name, cmds in sorted(cogs_dict.items()):
            cmd_list = []
            for cmd in sorted(cmds, key=lambda c: c.name):
                usage = f" {cmd.signature}" if cmd.signature else ""
                hidden_tag = " 👻*(隱藏)*" if cmd.hidden else ""
                
                # 標記管理權限指令
                is_admin_cmd = False
                for check in cmd.checks:
                    qualname = getattr(check, '__qualname__', '')
                    if 'has_permissions' in qualname or 'has_guild_permissions' in qualname or 'is_owner' in qualname:
                        is_admin_cmd = True
                        break
                admin_tag = " 🛡️*(管理)*" if is_admin_cmd else ""
                
                cmd_list.append(f"**`/{cmd.name}{usage}`**{hidden_tag}{admin_tag} - {cmd.short_doc or '無說明'}")
            
            value = "\n".join(cmd_list)
            # 防止字數超過 Discord Embed 欄位限制的 1024 字元
            if len(value) > 1024:
                value = value[:1020] + "..."
            
            embed.add_field(name=f"📌 {cog_name}", value=value, inline=False)

        embed.set_footer(text=f"查詢者: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Help(bot))