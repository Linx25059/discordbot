import discord
from discord.ext import commands

# --- 幫助選單下拉控制 UI ---
class HelpSelect(discord.ui.Select):
    def __init__(self, mapping, bot):
        self.mapping = mapping
        self.bot = bot
        options = [discord.SelectOption(label="🏠 首頁 (Home)", description="回到幫助選單首頁", emoji="🏠", value="Home")]
        for cat_name in mapping.keys():
            options.append(discord.SelectOption(label=cat_name, description=f"查看 {cat_name} 的指令", value=cat_name))
            
        super().__init__(placeholder="👇 請選擇一個指令分類來查看詳細內容...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        if category == "Home":
            embed = discord.Embed(title="🤖 機器人指令清單", description="以下是目前所有可用的指令分類：\n*(提示：點擊下方選單選擇分類，或在對話框輸入 `/` 查看詳細說明！)*", color=discord.Color.blurple())
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            for cat, cmds in self.mapping.items():
                embed.add_field(name=cat, value=f"包含 {len(cmds)} 個指令", inline=True)
        else:
            embed = discord.Embed(title=f"{category} 指令清單", description="\n".join(self.mapping[category]), color=discord.Color.blue())
        
        await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    def __init__(self, mapping, author_id, bot):
        super().__init__(timeout=180) # 3分鐘後選單自動失效
        self.author_id = author_id
        self.add_item(HelpSelect(mapping, bot))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 這是別人的幫助選單喔！請自己輸入 /help 來查詢。", ephemeral=True)
            return False
        return True

# --- 管理員幫助選單下拉控制 UI ---
class AdminHelpSelect(discord.ui.Select):
    def __init__(self, mapping, bot):
        self.mapping = mapping
        self.bot = bot
        options = [discord.SelectOption(label="🏠 總覽首頁", description="回到管理員指令總覽", emoji="🏠", value="Home")]
        for cat_name in mapping.keys():
            options.append(discord.SelectOption(label=cat_name, description=f"查看 {cat_name} 的指令", value=cat_name))
            
        super().__init__(placeholder="🛡️ 請選擇一個分類來查看管理員指令...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        if category == "Home":
            embed = discord.Embed(title="🛠️ 管理員指令清單 (總覽)", description="以下是目前系統載入的**所有指令**（包含隱藏與管理權限指令）：\n*(提示：點擊下方選單選擇分類查看詳細說明！)*", color=discord.Color.red())
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            for cat, cmds in self.mapping.items():
                cmd_count = sum(block.count("**`") for block in cmds)
                embed.add_field(name=cat, value=f"包含 {cmd_count} 個指令", inline=True)
        else:
            embed = discord.Embed(title=f"🛠️ {category} (管理員視角)", description="", color=discord.Color.dark_red())
            
            # 將指令分塊加入 Embed，避免超過 4096 字元限制
            chunk = ""
            for block in self.mapping[category]:
                if len(chunk) + len(block) + 2 > 4000:
                    embed.description = chunk.strip()
                    break
                chunk += block + "\n\n"
            
            embed.description = chunk.strip()
        
        await interaction.response.edit_message(embed=embed)

class AdminHelpView(discord.ui.View):
    def __init__(self, mapping, author_id, bot):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.add_item(AdminHelpSelect(mapping, bot))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 這是別人的幫助選單喔！請自己輸入 /adminhelp 來查詢。", ephemeral=True)
            return False
        return True

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS update_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, last_version TEXT)''')
        await self.bot.db.db.commit()

        # --- 在這裡設定最新版本的更新內容 ---
        self.current_version = "1.5"
        self.changelog_title = f"✨ 機器人更新日誌 (v{self.current_version})"
        self.changelog_text = (
            "**🚀 實用資訊版機器人全新轉型！**\n"
            "• 🧹 **移除經濟與等級系統：** 刪除等級、經驗值、個人檔案與趣味計數等娛樂系統，回歸極簡與實用定位。\n"
            "• 🛠️ **架構優化：** 移除資料庫中不必要的資料表，提升機器人響應效能與穩定度。\n"
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

        # 建立首頁的 Embed
        embed = discord.Embed(title="🤖 機器人指令清單", description="以下是目前所有可用的指令分類：\n*(提示：點擊下方選單選擇分類，或在對話框輸入 `/` 查看詳細說明！)*", color=discord.Color.blurple())
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        for cat, cmds in mapping.items():
            embed.add_field(name=cat, value=f"包含 {len(cmds)} 個指令", inline=True)
        embed.set_footer(text=f"查詢者: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        # 綁定下拉式選單 View
        view = HelpView(mapping, ctx.author.id, self.bot)
        await ctx.send(embed=embed, view=view)

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
        categorized_cog_names = []
        mapping = {} 

        for category, cogs in self.categorized_cogs.items():
            category_cmds = []
            for cog_name, cog_desc in cogs.items():
                categorized_cog_names.append(cog_name)
                cog = self.bot.get_cog(cog_name)
                if not cog:
                    continue
                
                cog_cmds = []
                for cmd in sorted(cog.get_commands(), key=lambda c: c.name):
                    usage = f" {cmd.signature}" if cmd.signature else ""
                    hidden_tag = " 👻*(隱藏)*" if cmd.hidden else ""
                    
                    is_admin_cmd = False
                    for check in cmd.checks:
                        qualname = getattr(check, '__qualname__', '')
                        if 'has_permissions' in qualname or 'has_guild_permissions' in qualname or 'is_owner' in qualname:
                            is_admin_cmd = True
                            break
                    admin_tag = " 🛡️*(管理)*" if is_admin_cmd else ""
                    
                    # 優化排版，將參數與說明分層
                    prefix = "/" if isinstance(cmd, commands.HybridCommand) else "!"
                    cog_cmds.append(f"**`{prefix}{cmd.name}{usage}`**{hidden_tag}{admin_tag}\n└ {cmd.short_doc or '無說明'}")
                
                if cog_cmds:
                    category_cmds.append(f"**【 {cog_desc} 】**\n" + "\n".join(cog_cmds))
            
            if category_cmds:
                mapping[category] = category_cmds

        other_cmds = []
        for cmd in sorted(self.bot.commands, key=lambda c: c.name):
            if cmd.cog_name == "NSFW" or cmd.cog_name in categorized_cog_names:
                continue
            
            usage = f" {cmd.signature}" if cmd.signature else ""
            hidden_tag = " 👻*(隱藏)*" if cmd.hidden else ""
            
            is_admin_cmd = False
            for check in cmd.checks:
                qualname = getattr(check, '__qualname__', '')
                if 'has_permissions' in qualname or 'has_guild_permissions' in qualname or 'is_owner' in qualname:
                    is_admin_cmd = True
                    break
            admin_tag = " 🛡️*(管理)*" if is_admin_cmd else ""
            
            prefix = "/" if isinstance(cmd, commands.HybridCommand) else "!"
            other_cmds.append(f"**`{prefix}{cmd.name}{usage}`**{hidden_tag}{admin_tag}\n└ {cmd.short_doc or '無說明'}")
            
        if other_cmds:
            mapping["📌 其他未分類指令"] = [ "\n".join(other_cmds) ]

        embed = discord.Embed(title="🛠️ 管理員指令清單 (總覽)", description="以下是目前系統載入的**所有指令**（包含隱藏與管理權限指令）：\n*(提示：點擊下方選單選擇分類查看詳細說明！)*", color=discord.Color.red())
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        for cat, cmds in mapping.items():
            cmd_count = sum(block.count("**`") for block in cmds)
            embed.add_field(name=cat, value=f"包含 {cmd_count} 個指令", inline=True)
            
        embed.set_footer(text=f"查詢者: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        view = AdminHelpView(mapping, ctx.author.id, self.bot)
        await ctx.send(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Help(bot))