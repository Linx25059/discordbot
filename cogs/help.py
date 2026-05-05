import discord
from discord.ext import commands
import sqlite3

class HelpCommandView(discord.ui.View):
    def __init__(self, bot, author, category_name, commands_list, home_view, home_embed):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.home_view = home_view
        self.home_embed = home_embed

        # 第一排加入返回按鈕
        back_btn = discord.ui.Button(label="⬅️ 返回首頁", style=discord.ButtonStyle.danger)
        back_btn.callback = self.go_back
        self.add_item(back_btn)

        # 動態產生指令按鈕 (Discord 限制一個 View 最多 25 個按鈕，保留 1 個給返回)
        for cmd in commands_list[:24]:
            btn = discord.ui.Button(label=f"/{cmd.name}", style=discord.ButtonStyle.primary)
            btn.callback = self.make_cmd_callback(cmd)
            self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 這是別人的幫助選單，請自己輸入 `!help` 呼叫喔！", ephemeral=True)
            return False
        return True

    async def go_back(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.home_embed, view=self.home_view)

    def make_cmd_callback(self, cmd):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()

            # 建立一個虛擬的訊息物件來欺騙 Context
            class MockMessage:
                def __init__(self, interaction, command_name):
                    self.id = interaction.message.id
                    self.author = interaction.user
                    self.channel = interaction.channel
                    self.guild = interaction.guild
                    self.content = f"!{command_name}"
                    self.attachments = []
                    self.embeds = []
                    self.components = []
                    self.mentions = []
                    self.role_mentions = []
                    self.channel_mentions = []
                    self.flags = discord.MessageFlags()
                    self.type = discord.MessageType.default
                    self._state = getattr(interaction, '_state', None)
                    self.created_at = interaction.created_at
                    self.edited_at = None

                async def delete(self, *args, **kwargs):
                    pass # 避免被特定指令 (如 !poll) 誤刪除面板

            msg = MockMessage(interaction, cmd.name)
            ctx = await self.bot.get_context(msg)
            
            # 呼叫全域 invoke，觸發指令的所有生命週期與錯誤處理
            if ctx.command:
                await self.bot.invoke(ctx)

        return callback

class HelpView(discord.ui.View):
    def __init__(self, bot, cog_mapping, author, home_embed):
        super().__init__(timeout=300) # 5 分鐘後按鈕失效
        self.bot = bot
        self.cog_mapping = cog_mapping
        self.author = author
        self.home_embed = home_embed

        # 第一個按鈕：首頁
        home_btn = discord.ui.Button(label="🏠 首頁", style=discord.ButtonStyle.success)
        home_btn.callback = self.show_home
        self.add_item(home_btn)

        # 動態生成各模組的分類按鈕
        for cog_name, cog in self.bot.cogs.items():
            commands_list = [c for c in cog.get_commands() if not c.hidden]
            if not commands_list:
                continue
            
            display_name = self.cog_mapping.get(cog_name, f"📌 {cog_name}")
            btn = discord.ui.Button(label=display_name, style=discord.ButtonStyle.primary)
            btn.callback = self.make_callback(display_name, commands_list)
            self.add_item(btn)

    # 防止其他人亂點你的按鈕
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 這是別人的幫助選單，請自己輸入 `!help` 呼叫喔！", ephemeral=True)
            return False
        return True

    # 按下首頁的動作
    async def show_home(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.home_embed, view=self)

    # 按下各分類按鈕的動作
    def make_callback(self, display_name, commands_list):
        async def callback(interaction: discord.Interaction):
            embed = discord.Embed(
                title=f"{display_name} 指令",
                color=discord.Color.blue()
            )
            
            cmd_info = []
            for cmd in commands_list:
                desc = cmd.help if cmd.help else "未提供說明"
                cmd_info.append(f"**`!{cmd.name}`** - {desc}")
            
            embed.description = "👇 **點擊下方的按鈕，可以直接快速使用對應的指令喔！**\n\n" + "\n".join(cmd_info)
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.set_footer(text=f"你正在查看 {display_name} 分類", icon_url=self.author.display_avatar.url)
            
            # 切換為帶有具體指令按鈕的 View
            cmd_view = HelpCommandView(self.bot, self.author, display_name, commands_list, self, self.home_embed)
            await interaction.response.edit_message(embed=embed, view=cmd_view)
        return callback

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('bot_database.db', timeout=10.0)
        self.c = self.conn.cursor()
        self.c.execute('''CREATE TABLE IF NOT EXISTS update_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, last_version TEXT)''')
        self.conn.commit()

        # --- 在這裡設定最新版本的更新內容 ---
        self.current_version = "v2.2"
        self.changelog_title = f"✨ 機器人更新日誌 ({self.current_version})"
        self.changelog_text = (
            "**🆕 最新功能**\n"
            "• **全面導入下拉式選單 (Dropdown Menus)**：`/eat`、`/buy`、`/trade`、`/use`、`/coinflip` 等指令現在全面支援精美的下拉選單與圖示！再也不怕打錯字，點擊選單就能輕鬆操作！\n"
            "• **指令參數提示優化**：為各個指令的參數加上了詳細的中文引導說明。\n\n"
            "**🔧 修正與優化**\n"
            "• 修正了部分斜線指令與按鈕的衝突，並大幅提升了操作體驗與機器人穩定性。"
        )

        # 啟動時檢查是否需要推播更新
        self.bot.loop.create_task(self.auto_push_updates())

        self.cog_mapping = {
            "Economy": "💸 經濟系統",
            "Gamble": "🎲 賭博遊戲",
            "Fun": "🎉 娛樂功能",
            "AIChat": "🤖 AI 互動",
            "Admin": "🛡️ 管理員指令",
            "Broadcast": "📡 自動廣播",
            "Weather": "🌤️ 天氣資訊",
            "AutoVoice": "🎙️ 動態語音",
            "Logger": "📝 日誌系統",
            "Help": "ℹ️ 幫助系統",
            "ImageGen": "🖼️ 圖片生成",
            "LinkFixer": "🔗 連結修復",
            "Finance": "📈 金融市場"
        }

    async def auto_push_updates(self):
        await self.bot.wait_until_ready()
        self.c.execute('SELECT guild_id, channel_id, last_version FROM update_settings')
        settings = self.c.fetchall()

        for guild_id, channel_id, last_version in settings:
            if last_version != self.current_version:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    embed = discord.Embed(title=self.changelog_title, description=self.changelog_text, color=discord.Color.gold())
                    embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                    embed.set_footer(text="未來有新功能都會自動推播到這裡喔！")
                    try:
                        await channel.send("🚀 **機器人有新的更新囉！**", embed=embed)
                        self.c.execute('UPDATE update_settings SET last_version = ? WHERE guild_id = ?', (self.current_version, guild_id))
                        self.conn.commit()
                    except Exception as e:
                        print(f"推播更新失敗 (Guild: {guild_id}): {e}")

    @commands.hybrid_command(name="help", aliases=["幫助", "指令", "h"], help="顯示所有可用的指令清單")
    async def custom_help(self, ctx):
        embed = discord.Embed(
            title="🤖 機器人指令清單",
            description="請點擊下方的按鈕，選擇你想查看的指令分類！\n現在全面支援輸入 `/` 來快速呼叫指令囉！\n例如：`/work`、`/shop`、`/天氣`",
            color=discord.Color.blurple()
        )

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="提示：使用 / 斜線指令會有更好的體驗喔！", icon_url=ctx.author.display_avatar.url)
        
        # 產生帶有按鈕的 View
        view = HelpView(self.bot, self.cog_mapping, ctx.author, embed)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="changelog", aliases=["update", "更新", "更新日誌"], help="查看機器人的最新更新內容")
    async def changelog(self, ctx):
        embed = discord.Embed(
            title=self.changelog_title,
            description=self.changelog_text,
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="未來有新功能都會在這裡發布喔！", icon_url=ctx.author.display_avatar.url)
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
        
        await ctx.send(f"✅ 成功！已將 {ctx.channel.mention} 設為更新推播頻道。這是最新的更新內容：", embed=embed)
        
        self.c.execute('INSERT OR REPLACE INTO update_settings (guild_id, channel_id, last_version) VALUES (?, ?, ?)', 
                       (ctx.guild.id, ctx.channel.id, self.current_version))
        self.conn.commit()

async def setup(bot):
    await bot.add_cog(Help(bot))