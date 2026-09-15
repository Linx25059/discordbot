import discord
from discord.ext import commands
from discord import app_commands
import traceback
import logging
from cogs.bug_report import BugReportPanelView

logger = logging.getLogger(__name__)

class ErrorHandler(commands.Cog):
    """全域指令與斜線指令 (App Command) 錯誤處理器"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 紀錄預設的 app command 錯誤處理常式
        self.old_tree_error = self.bot.tree.on_error

    async def cog_load(self):
        # 註冊斜線指令 (Slash Command) 全域錯誤監聽器
        self.bot.tree.on_error = self.on_app_command_error

    def cog_unload(self):
        # 卸載時還原原本的處理器
        self.bot.tree.on_error = self.old_tree_error

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # 忽略有自訂錯誤處理器的指令
        if ctx.command and hasattr(ctx.command, 'on_error'):
            return

        # 取得最原始的錯誤
        error = getattr(error, 'original', error)

        view = BugReportPanelView()
        embed = discord.Embed(title="🚨 發生了一點錯誤", color=discord.Color.red())

        if isinstance(error, commands.CommandNotFound):
            embed.description = f"找不到 `{ctx.invoked_with}` 這個指令喔！\n可以使用 `/help` 來查看所有可用的指令清單。"

        elif isinstance(error, commands.DisabledCommand):
            embed.description = f"目前 `{ctx.command}` 指令暫時被停用了喔。"
        
        elif isinstance(error, commands.CommandOnCooldown):
            embed.title = "⏳ 技能冷卻中"
            embed.description = f"稍微休息一下吧！請稍等 {error.retry_after:.2f} 秒後再試一次。"
            embed.color = discord.Color.orange()

        elif isinstance(error, commands.MissingPermissions):
            embed.description = f"你好像沒有權限使用 `{ctx.command}` 喔！\n需要的權限：`{'`, `'.join(error.missing_permissions)}`"
            
        elif isinstance(error, commands.BotMissingPermissions):
            embed.description = f"我沒有足夠的權限執行這個指令！\n需要的權限：`{'`, `'.join(error.missing_permissions)}`"

        elif isinstance(error, commands.NotOwner):
            embed.description = "❌ 這是開發者專用的隱藏指令，一般使用者無法執行喔！"

        elif isinstance(error, commands.CheckFailure):
            embed.description = "❌ 你目前不符合使用這個指令的條件或權限喔！"

        elif isinstance(error, commands.UserInputError):
            cmd_name = ctx.command.qualified_name if ctx.command else "指令"
            embed.description = f"指令的格式好像不太對喔！\n可以使用 `/help {cmd_name}` 查看正確的用法。"

        else:
            embed.description = "發生了未知的錯誤，我會盡快回報給管理員處理。"
            logger.error(f'文字指令 {ctx.command} 發生未預期的例外狀況:', exc_info=error)

        embed.set_footer(text="💡 若需要管理員的協助或回報問題，可隨時點擊下方按鈕！")

        kwargs = {"embed": embed, "ephemeral": True}
        if view:
            kwargs["view"] = view
            
        try:
            await ctx.send(**kwargs)
        except discord.errors.HTTPException as e:
            if e.code == 40060:
                try:
                    if ctx.interaction:
                        await ctx.interaction.followup.send(**kwargs)
                except discord.errors.HTTPException as followup_e:
                    logger.error(f"連後續錯誤訊息發送亦失敗: {followup_e}")
            else:
                logger.error(f"發送文字指令錯誤訊息時發生 HTTP 異常: {e}")
        except Exception as final_e:
            logger.error(f"在文字指令錯誤處理期間發生未預期異常: {final_e}")

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """全域斜線指令 (Slash / Context Menu) 錯誤處理器"""
        error = getattr(error, 'original', error)

        view = BugReportPanelView()
        embed = discord.Embed(title="🚨 發生了一點錯誤", color=discord.Color.red())

        if isinstance(error, app_commands.CommandOnCooldown):
            embed.title = "⏳ 技能冷卻中"
            embed.description = f"稍微休息一下吧！請稍等 {error.retry_after:.2f} 秒後再試一次。"
            embed.color = discord.Color.orange()

        elif isinstance(error, app_commands.MissingPermissions):
            embed.description = f"你好像沒有權限使用此斜線指令喔！\n需要的權限：`{'`, `'.join(error.missing_permissions)}`"

        elif isinstance(error, app_commands.BotMissingPermissions):
            embed.description = f"我沒有足夠的權限執行此斜線指令！\n需要的權限：`{'`, `'.join(error.missing_permissions)}`"

        elif isinstance(error, app_commands.CheckFailure):
            embed.description = "❌ 你目前不符合使用此斜線指令的條件或權限喔！"

        else:
            embed.description = "執行斜線指令時發生未知錯誤，已自動紀錄並回報管理員。"
            logger.error(f'斜線指令 {interaction.command} 發生未預期例外:', exc_info=error)

        embed.set_footer(text="💡 若需要管理員的協助或回報問題，可隨時點擊下方按鈕！")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"發送斜線指令錯誤訊息時發生異常: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))