import discord
from discord.ext import commands
import asyncio
import io

#  報錯面板的按鈕 View
class BugReportPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 設定 None 代表機器人重啟後按鈕依然有效

    @discord.ui.button(label="🚨 建立報錯單", style=discord.ButtonStyle.danger, custom_id="persistent_bug_create_btn")
    async def create_bug_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        # 檢查是否已有相同名稱的頻道 (避免重複開單)
        channel_name = f"bug-{interaction.user.name.lower()}"
        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        if existing_channel:
            return await interaction.response.send_message(f"❌ 你已經有一個正在進行中的回報頻道囉：{existing_channel.mention}", ephemeral=True)

        # 設定頻道權限 (預設身分組不可見，只有點擊者與機器人可見)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # 在與面板相同的類別下建立頻道
        category = interaction.channel.category
        bug_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        embed = discord.Embed(title="🐛 問題回報", description=f"嗨 {interaction.user.mention}！\n遇到了什麼問題嗎？請盡量詳細描述發生的情況，我會將紀錄轉交給62！", color=discord.Color.red())
        # 傳送歡迎訊息，並附上關閉按鈕
        await bug_channel.send(content=f"{interaction.user.mention}", embed=embed, view=BugReportCloseView())
        
        # 給予使用者新開頻道的「跳轉連結」 (這則訊息只有點擊按鈕的人看得到)
        await interaction.response.send_message(f"✅ 專屬回報頻道已建立，請點擊前往：{bug_channel.mention}", ephemeral=True)

# 🔒 關閉報錯單的按鈕 View
class BugReportCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 結案並傳送給62", style=discord.ButtonStyle.secondary, custom_id="persistent_bug_close_btn")
    async def close_bug_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 正在處理結案紀錄，請稍候...")
        
        # 取得頻道歷史訊息 (排除機器人自己的訊息)
        transcript = []
        async for msg in interaction.channel.history(limit=200, oldest_first=True):
            if msg.author.bot:
                continue
            
            content = msg.content
            # 如果使用者有上傳圖片或附件，保留網址
            if msg.attachments:
                content += " " + " ".join([att.url for att in msg.attachments])
            
            if content.strip():
                time_str = msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
                transcript.append(f"[{time_str}] {msg.author.name}: {content}")
                
        transcript_text = "\n".join(transcript)
        if not transcript_text:
            transcript_text = "使用者關閉了回報，但未留下任何訊息。"
            
        # 取得機器人的擁有者並發送私訊
        app_info = await interaction.client.application_info()
        owner = app_info.team.owner if app_info.team else app_info.owner
        
        embed = discord.Embed(title="🚨 有報錯單處理完畢囉", color=discord.Color.red())
        embed.add_field(name="伺服器", value=f"{interaction.guild.name} (`{interaction.guild.id}`)", inline=False)
        embed.add_field(name="頻道名稱", value=interaction.channel.name, inline=False)
        
        # 把所有紀錄轉存成一個 txt 附件傳送 (避免超過 Discord 2000 字限制)
        transcript_file = discord.File(io.BytesIO(transcript_text.encode('utf-8')), filename=f"{interaction.channel.name}_transcript.txt")
        
        try:
            await owner.send(embed=embed, file=transcript_file)
        except discord.Forbidden:
            pass # 若開發者關閉私訊功能則略過
            
        await asyncio.sleep(2)
        await interaction.channel.delete(reason="報錯單已結案並傳送給62")

class BugReport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 註冊持久化視圖，讓機器人重啟後按鈕依然能按
        self.bot.add_view(BugReportPanelView())
        self.bot.add_view(BugReportCloseView())

    @commands.hybrid_command(name="bugreport", aliases=["設定報錯"], help="在當前頻道建立報錯單面板")
    @commands.has_permissions(manage_channels=True)
    async def setup_bug_report(self, ctx):
        # 如果管理員是用傳統指令 (!bugreport) 呼叫的，就自動把那句指令刪除保持版面乾淨
        if not ctx.interaction:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass  # 若機器人權限不足無法刪除則忽略
                
        embed = discord.Embed(
            title="🚨 問題與錯誤回報",
            description="如果在使用上遇到任何問題，請點擊下方按鈕。\n系統會建立一個專屬頻道，讓你與管理員進行溝通與回報！",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, view=BugReportPanelView())

async def setup(bot):
    await bot.add_cog(BugReport(bot))