import discord
from discord.ext import commands
import random
import asyncio

# 📝 彈出式輸入視窗 (用來新增遊戲)
class GameAddModal(discord.ui.Modal, title='➕ 新增遊戲'):
    game_name = discord.ui.TextInput(
        label='想新增什麼遊戲呢？',
        placeholder='例如：Apex Legends, 英雄聯盟...',
        required=True,
        max_length=50
    )

    def __init__(self, cog, guild_id, panel_view):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.panel_view = panel_view  # 紀錄原本的面板，方便新增後重新整理

    async def on_submit(self, interaction: discord.Interaction):
        name = self.game_name.value.strip()
        
        # 檢查是否已經存在
        async with self.cog.bot.db.db.execute('SELECT 1 FROM server_games WHERE guild_id = ? AND game_name = ?', (self.guild_id, name)) as cursor:
            if await cursor.fetchone():
                return await interaction.response.send_message(embed=discord.Embed(description=f"❌ 「{name}」已經在清單裡面囉！", color=discord.Color.red()), ephemeral=True)
        
        # 防呆機制：Discord 下拉選單最多只能顯示 25 個選項
        async with self.cog.bot.db.db.execute('SELECT COUNT(*) FROM server_games WHERE guild_id = ?', (self.guild_id,)) as cursor:
            count = await cursor.fetchone()
            
        if count[0] >= 25:
            return await interaction.response.send_message(embed=discord.Embed(description="❌ 清單已滿！最多只能儲存 25 個遊戲。", color=discord.Color.red()), ephemeral=True)

        # 存入資料庫
        await self.cog.bot.db.db.execute('INSERT INTO server_games (guild_id, game_name) VALUES (?, ?)', (self.guild_id, name))
        await self.cog.bot.db.db.commit()
        
        await interaction.response.send_message(embed=discord.Embed(description=f"✅ 成功將 **{name}** 加入遊戲清單！", color=discord.Color.green()), ephemeral=True)
        
        # 自動更新面板上的遊戲清單
        await self.panel_view.refresh_panel()

# 🗑️ 下拉式刪除選單
class GameRemoveView(discord.ui.View):
    def __init__(self, cog, guild_id, panel_view, games):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id
        self.panel_view = panel_view
        
        # 將遊戲轉換為選單選項
        options = [discord.SelectOption(label=game, value=game, emoji="🎮") for game in games]
        
        self.select = discord.ui.Select(placeholder="👇 點我展開清單，選擇要刪除的遊戲...", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        game_to_remove = self.select.values[0]
        
        await self.cog.bot.db.db.execute('DELETE FROM server_games WHERE guild_id = ? AND game_name = ?', (self.guild_id, game_to_remove))
        await self.cog.bot.db.db.commit()
        
        # 刪除成功後把選單隱藏，並顯示提示
        await interaction.response.edit_message(embed=discord.Embed(description=f"🗑️ 已成功刪除遊戲：**{game_to_remove}**。", color=discord.Color.green()), view=None)
        await self.panel_view.refresh_panel()

# 🕹️ 主控制面板
class GamePanelView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.panel_message = None # 用來記住面板的訊息物件，方便我們隨時更新它

    async def get_panel_embed(self):
        async with self.cog.bot.db.db.execute('SELECT game_name FROM server_games WHERE guild_id = ?', (self.guild_id,)) as cursor:
            games = [row[0] async for row in cursor]
        
        embed = discord.Embed(
            title="🎰 遊戲抽籤面板",
            description="不知道今天要玩什麼嗎？點擊下方按鈕讓我來幫你抽一個！",
            color=discord.Color.blurple()
        )
        
        if games:
            games_list = "\n".join([f"• {g}" for g in games])
            embed.add_field(name=f"📦 目前庫存遊戲 ({len(games)}/25)", value=games_list, inline=False)
        else:
            embed.add_field(name="📦 目前庫存遊戲 (0/25)", value="目前清單空空如也，趕快點擊「➕ 新增」來加入遊戲吧！", inline=False)
            
        return embed

    async def refresh_panel(self):
        if self.panel_message:
            embed = await self.get_panel_embed()
            await self.panel_message.edit(embed=embed)

    @discord.ui.button(label="🎲 決定今天要玩什麼！", style=discord.ButtonStyle.success)
    async def draw_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with self.cog.bot.db.db.execute('SELECT game_name FROM server_games WHERE guild_id = ?', (self.guild_id,)) as cursor:
            games = [row[0] async for row in cursor]
        
        if not games:
            return await interaction.response.send_message(embed=discord.Embed(description="❌ 遊戲清單是空的，請先新增一些遊戲吧！", color=discord.Color.red()), ephemeral=True)
            
        await interaction.response.defer() # 延遲回應，讓我們有時間放個小特效
        
        msg = await interaction.followup.send(embed=discord.Embed(description="🎲 **正在隨機抽選...**", color=discord.Color.blurple()), wait=True)
        await asyncio.sleep(1.5) # 營造抽籤的期待感
        
        winner = random.choice(games)
        await msg.edit(embed=discord.Embed(title="🎉 抽籤結果出爐！", description=f"今天就決定玩：\n\n### **🎮 {winner}**", color=discord.Color.gold()))

    @discord.ui.button(label="➕ 新增", style=discord.ButtonStyle.primary)
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 呼叫彈出式視窗
        await interaction.response.send_modal(GameAddModal(self.cog, self.guild_id, self))

    @discord.ui.button(label="🗑️ 刪除", style=discord.ButtonStyle.danger)
    async def remove_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with self.cog.bot.db.db.execute('SELECT game_name FROM server_games WHERE guild_id = ?', (self.guild_id,)) as cursor:
            games = [row[0] async for row in cursor]
            
        if not games:
            return await interaction.response.send_message(embed=discord.Embed(description="❌ 清單內目前沒有任何遊戲可以刪除。", color=discord.Color.red()), ephemeral=True)
            
        # 呼叫下拉式選單 (且設為 ephemeral，只有點擊的人看得到，不會洗頻)
        view = GameRemoveView(self.cog, self.guild_id, self, games)
        await interaction.response.send_message(embed=discord.Embed(description="請在下方選擇你要刪除的遊戲：", color=discord.Color.orange()), view=view, ephemeral=True)

class GameRouletteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS server_games (guild_id INTEGER, game_name TEXT)''')
        await self.bot.db.db.commit()

    @commands.hybrid_command(name="game_panel", aliases=["抽遊戲", "遊戲面板"], help="開啟專屬遊戲抽籤控制面板")
    async def game_panel(self, ctx):
        view = GamePanelView(self, ctx.guild.id)
        embed = await view.get_panel_embed()
        
        # 發送面板，並將該訊息紀錄下來，以便後續更新 (Refresh) 使用
        msg = await ctx.send(embed=embed, view=view)
        view.panel_message = msg

async def setup(bot):
    await bot.add_cog(GameRouletteCog(bot))