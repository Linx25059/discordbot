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
            "**🚀 v1.3 重大更新發布！**\n"
            "• 🏦 **全新銀行系統：** 新增存款 (`/deposit`) 與提款 (`/withdraw`) 功能，每日凌晨會發放 1% 存款利息！更有全服富豪榜 (`/richest`) 等你來挑戰！\n"
            "• 🖼️ **圖片惡搞升級：** 新增打碼 (`/pixelate`)、遺照 (`/wasted`)、詛咒負片 (`/invert`) 與近視模糊 (`/blur`) 功能！\n"
            "• 💸 **經濟與升級平衡：** 聊天隨機掉落金幣彩蛋，升級大紅包發放！股市也調整為更容易獲利的牛市環境。\n"
        )

        # 啟動時檢查是否需要推播更新
        self.bot.loop.create_task(self.auto_push_updates())

        # 重新整理成大分類結構
        self.categorized_cogs = {
            "🤖 智慧助理與查詢": {
                "AIChat": "🧠 智慧聊天助理",
                "Weather": "🌤️ 天氣預報查詢"
            },
            "🎵 影音與趣味互動": {
                "Music": "🎧 音樂點播",
                "ImageGen": "🖼️ 迷因與頭貼",
                "Food": "🍔 美食手搖推薦"
            },
            "🎮 遊戲與娛樂": {
                "GameRouletteCog": "🎰 遊戲抽籤面板",
                "Gamble": "🎲 娛樂城與賭博",
                "Fun": "🎁 抽獎大放送",
                "Giveaway": "🎉 限時抽獎系統",
                "JerkCounter": "💦 趣味計數"
            },
            "💸 經濟與財富": {
                "Economy": "💰 錢包與打工",
                "Finance": "📈 虛擬股票市場"
            },
            "🏆 活躍與個人": {
                "Leveling": "🏅 等級排行榜",
                "Profile": "🪪 個人專屬檔案"
            },
            "🛠️ 實用工具與自動化": {
                "LinkFixer": "🔗 社群連結修復",
                "AutoVoice": "🎙️ 動態語音頻道",
                "Broadcast": "📡 新聞與遊戲推播",
                "AutoReply": "💬 自動回覆系統"
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
                        category_cmds.append(f"**`/{cmd.name}{usage}`** - {cmd.short_doc or '無說明'}")
            
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
                other_cmds.append(f"**`/{cmd.name}{usage}`** - {cmd.short_doc or '無說明'}")
                
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
        # 整理所有指令並依據 Cog 分類
        cogs_dict = {}
        for cmd in self.bot.commands:
            if cmd.cog_name == "NSFW":
                continue
            cog_name = cmd.cog_name or "未分類指令"
            if cog_name not in cogs_dict:
                cogs_dict[cog_name] = []
            cogs_dict[cog_name].append(cmd)

        # --- 企業級修復：補回上次遺漏的變數初始化 ---
        cog_display_names = {}
        for category, cogs in self.categorized_cogs.items():
            for cog_key, desc in cogs.items():
                cog_display_names[cog_key] = desc

        embeds = []
        current_embed = discord.Embed(
            title="🛠️ 管理員指令清單",
            description="以下列出目前系統載入的**所有指令**（包含隱藏與管理權限指令）：",
            color=discord.Color.red()
        )
        field_count = 0

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
            
            display_name = cog_display_names.get(cog_name, f"🧩 {cog_name}")
            
            # 將指令列表分塊，完美迴避 Discord 單一欄位 1024 字元的限制
            chunk = ""
            part_num = 1
            for line in cmd_list:
                if len(chunk) + len(line) + 1 > 1024:
                    # 避免超過單一 Embed 最多 25 個欄位的限制
                    if field_count >= 25:
                        embeds.append(current_embed)
                        current_embed = discord.Embed(title="🛠️ 管理員指令清單 (續)", color=discord.Color.red())
                        field_count = 0
                        
                    field_name = f"📌 {display_name}" if part_num == 1 else f"📌 {display_name} (續)"
                    current_embed.add_field(name=field_name, value=chunk, inline=False)
                    field_count += 1
                    chunk = line + "\n"
                    part_num += 1
                else:
                    chunk += line + "\n"
                    
            if chunk:
                if field_count >= 25:
                    embeds.append(current_embed)
                    current_embed = discord.Embed(title="🛠️ 管理員指令清單 (續)", color=discord.Color.red())
                    field_count = 0
                
                field_name = f"📌 {display_name}" if part_num == 1 else f"📌 {display_name} (續)"
                current_embed.add_field(name=field_name, value=chunk, inline=False)
                field_count += 1

        if field_count > 0:
            embeds.append(current_embed)
            
        if embeds:
            embeds[-1].set_footer(text=f"查詢者: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        # 支援一次傳送多個 Embed 面板
        await ctx.send(embeds=embeds, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Help(bot))