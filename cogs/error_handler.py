import discord
from discord.ext import commands

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # 建立一個基礎的 Embed，預設為紅色
        embed = discord.Embed(color=discord.Color.red())
        
        # 1. 處理缺少必要參數錯誤
        if isinstance(error, commands.MissingRequiredArgument):
            embed.title = "❌ 缺少必要參數"
            if ctx.command.name == "weather":
                embed.description = "你忘記輸入地區了啦！\n👉 **正確用法**：`/天氣 台北市 信義區` 或 `/w 高雄`"
            elif ctx.command.name in ["meme", "jail"]:
                embed.description = "你忘記輸入迷因的文字或標記了啦！\n👉 **正確用法**：`/meme 今晚打遊戲 | 還是早點睡覺`"
            elif ctx.command.name == "poll":
                embed.description = "你忘記輸入問題了啦！\n👉 **正確用法**：`/poll 今晚吃什麼？ | 火鍋 | 燒肉`"
            elif ctx.command.name == "buy":
                embed.description = "你忘記打要買什麼了！\n👉 **正確用法**：`/buy 1` 或 `/buy 神秘寶箱`"
            elif ctx.command.name == "use":
                embed.description = "你忘記輸入要使用什麼物品了！\n👉 **正確用法**：`/use 神秘寶箱`"
            else:
                embed.description = f"缺少必要的參數：`{error.param.name}`\n👉 請輸入 `/help {ctx.command.name}` 查看正確用法！"
            await ctx.send(embed=embed)

        # 2. 處理冷卻時間錯誤
        elif isinstance(error, commands.CommandOnCooldown):
            embed.title = "⏱️ 指令冷卻中"
            embed.color = discord.Color.orange() # 冷卻錯誤改成橘色
            if ctx.command.name in ["daily", "work"]:
                m, s = divmod(int(error.retry_after), 60)
                h, m = divmod(m, 60)
                if h > 0:
                    embed.description = f"休息一下！請等待 **{h} 小時 {m} 分鐘** 後再來。"
                else:
                    embed.description = f"休息一下！請等待 **{m} 分鐘 {s} 秒** 後再來。\n💡 *你可以去商店買 `精力飲料` 來解除冷卻！*"
            elif ctx.command.name == "chat":
                embed.description = f"欸欸你打字太快了啦！等 **{error.retry_after:.1f} 秒** 再密我。"
            else:
                embed.description = f"查詢太頻繁啦！請等待 **{error.retry_after:.1f} 秒** 後再試。"
            await ctx.send(embed=embed)

        # 3. 處理權限不足錯誤
        elif isinstance(error, commands.MissingPermissions):
            embed.title = "🚫 權限不足"
            embed.description = "嘿！你沒有權限使用這個指令喔！"
            await ctx.send(embed=embed)

        # 4. 處理參數格式錯誤 (例如需要數字卻輸入文字，或是找不到標記的成員)
        elif isinstance(error, (commands.BadArgument, commands.MemberNotFound, commands.UserNotFound)):
            embed.title = "❌ 參數格式錯誤"
            embed.description = f"你輸入的參數格式不對，或者找不到該目標喔！\n👉 請輸入 `/help {ctx.command.name}` 查看正確用法！"
            await ctx.send(embed=embed)

        # 5. 忽略無效的指令錯誤 (例如玩家輸入 !不存在的指令)
        elif isinstance(error, commands.CommandNotFound):
            pass
            
        else:
            # 擷取深層真正的錯誤訊息 (過濾掉 Discord.py 的包裝)
            if isinstance(error, commands.CommandInvokeError):
                error = error.original
            embed.title = "⚠️ 發生未預期的錯誤"
            embed.description = f"```\n{error}\n```"
            await ctx.send(embed=embed)
            print(f"未預期的錯誤發生於 {ctx.command}: {error}")

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))