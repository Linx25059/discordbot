import discord
from discord.ext import commands
import sys
import traceback
import logging
from cogs.bug_report import BugReportPanelView

class ErrorHandler(commands.Cog):
    """一個用來處理指令錯誤的全域處理器。"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # 忽略有自訂錯誤處理器的指令
        if hasattr(ctx.command, 'on_error'):
            return

        # 取得最原始的錯誤
        error = getattr(error, 'original', error)

        # 忽略特定錯誤 (例如：找不到指令)
        if isinstance(error, (commands.CommandNotFound,)):
            return

        view = BugReportPanelView()
        embed = discord.Embed(title="🚨 發生了一點錯誤", color=discord.Color.red())

        if isinstance(error, commands.DisabledCommand):
            embed.description = f"目前 `{ctx.command}` 指令暫時被停用了喔。"
        
        elif isinstance(error, commands.CommandOnCooldown):
            embed.title = "⏳ 技能冷卻中"
            embed.description = f"稍微休息一下吧！請稍等 {error.retry_after:.2f} 秒後再試一次。"
            embed.color = discord.Color.orange()

        elif isinstance(error, commands.MissingPermissions):
            embed.description = f"你好像沒有權限使用 `{ctx.command}` 喔！\n需要的權限：`{'`, `'.join(error.missing_permissions)}`"
            
        elif isinstance(error, commands.BotMissingPermissions):
            embed.description = f"我沒有足夠的權限執行這個指令！\n需要的權限：`{'`, `'.join(error.missing_permissions)}`"

        elif isinstance(error, commands.UserInputError):
            embed.description = f"指令的格式好像不太對喔！\n可以使用 `{ctx.prefix}help {ctx.command}` 查看正確的用法。"

        else:
            # 其他所有未處理的錯誤
            embed.description = "發生了未知的錯誤，我會盡快回報給管理員處理。"
            # 企業級優化：將例外拋入日誌系統，而非單純 print，以便後續集中監控
            logging.error(f'Ignoring exception in command {ctx.command}:', exc_info=error)

        embed.set_footer(text="💡 若需要管理員的協助或回報問題，可隨時點擊下方按鈕！")

        # --- 核心修復邏輯 ---
        kwargs = {"embed": embed, "ephemeral": True}
        if view:
            kwargs["view"] = view
            
        # 嘗試發送錯誤訊息。如果因為互動已被確認而失敗，則改用 followup.send()
        try:
            # 對於混合指令，ctx.send() 會自動判斷。但為了處理競態條件，我們需要手動捕捉錯誤。
            await ctx.send(**kwargs)
        except discord.errors.HTTPException as e:
            # 錯誤碼 40060 代表 "Interaction has already been acknowledged"
            if e.code == 40060:
                try:
                    # 如果初始回應失敗，就改用後續訊息發送
                    await ctx.followup.send(**kwargs)
                except discord.errors.HTTPException as followup_e:
                    print(f"連後續錯誤訊息都發送失敗: {followup_e}", file=sys.stderr)
            else:
                # 如果是其他 HTTP 錯誤，則印出
                print(f"發送錯誤訊息時發生 HTTP 錯誤: {e}", file=sys.stderr)
        except Exception as final_e:
            # 處理其他所有在發送錯誤訊息時可能發生的意外
            print(f"在錯誤處理期間發生了無法預期的錯誤: {final_e}", file=sys.stderr)


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))