import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import random
import asyncio

class Gamble(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('bot_database.db', timeout=10.0)
        self.c = self.conn.cursor()

        # 確保 economy 資料表存在
        self.c.execute('''CREATE TABLE IF NOT EXISTS economy (user_id INTEGER PRIMARY KEY, balance INTEGER)''')
        self.conn.commit()

    # --- 輔助功能區 (用來與資料庫連動) ---
    def get_balance(self, user_id):
        self.c.execute('SELECT balance FROM economy WHERE user_id = ?', (user_id,))
        result = self.c.fetchone()
        if result is None:
            self.c.execute('INSERT INTO economy (user_id, balance) VALUES (?, ?)', (user_id, 0))
            self.conn.commit()
            return 0
        return result[0]

    def update_balance(self, user_id, amount):
        balance = self.get_balance(user_id)
        new_balance = balance + amount
        self.c.execute('UPDATE economy SET balance = ? WHERE user_id = ?', (new_balance, user_id))
        self.conn.commit()
        return new_balance

    # --- 賭博遊戲區 ---
    @commands.hybrid_command(name="coinflip", aliases=["cf", "猜硬幣"], help="猜硬幣正反面")
    @app_commands.describe(choice="選擇你要猜哪一面", amount="下注金額")
    @app_commands.choices(choice=[
        app_commands.Choice(name="🪙 正面", value="正"),
        app_commands.Choice(name="🪙 反面", value="反")
    ])
    async def coinflip(self, ctx, choice: str, amount: int):
        if amount <= 0:
            return await ctx.send("❌ 賭注必須大於 0！")
        if self.get_balance(ctx.author.id) < amount:
            return await ctx.send("❌ 你的餘額不足，無法下注！")
        if choice not in ["正", "反"]:
            return await ctx.send("❌ 選擇錯誤！請輸入 `正` 或 `反` (例如: !cf 正 100)")

        outcome = random.choice(["正", "反"])
        
        if choice == outcome:
            self.update_balance(ctx.author.id, amount)
            await ctx.send(f"🪙 硬幣擲出：**{outcome}面**！\n🎉 恭喜 {ctx.author.mention} 猜中了，贏得 **{amount}** 金幣！")
        else:
            self.update_balance(ctx.author.id, -amount)
            await ctx.send(f"🪙 硬幣擲出：**{outcome}面**！\n💥 哎呀，{ctx.author.mention} 猜錯了，損失 **{amount}** 金幣。")

    @commands.hybrid_command(name="betdice", aliases=["bdice", "比大小", "賭骰子"], help="和機器人比骰子大小")
    async def betdice(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("❌ 賭注必須大於 0！")
        if self.get_balance(ctx.author.id) < amount:
            return await ctx.send("❌ 你的餘額不足，無法下注！")

        bot_roll = random.randint(1, 6)
        user_roll = random.randint(1, 6)

        embed = discord.Embed(title="🎲 骰子對決", color=discord.Color.blurple())
        embed.add_field(name=f"{ctx.author.display_name} 的點數", value=f"**{user_roll}**", inline=True)
        embed.add_field(name="機器人 的點數", value=f"**{bot_roll}**", inline=True)

        if user_roll > bot_roll:
            self.update_balance(ctx.author.id, amount)
            embed.description = f"🎉 恭喜 {ctx.author.mention} 贏了 **{amount}** 金幣！"
            embed.color = discord.Color.green()
        elif user_roll < bot_roll:
            self.update_balance(ctx.author.id, -amount)
            embed.description = f"💥 很遺憾，{ctx.author.mention} 輸了 **{amount}** 金幣。"
            embed.color = discord.Color.red()
        else:
            embed.description = f"🤝 平手！你的賭金已退回。"
            embed.color = discord.Color.gold()

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="slots", aliases=["老虎機", "拉霸"], help="玩拉霸機")
    async def slots(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("❌ 賭注必須大於 0！")
        if self.get_balance(ctx.author.id) < amount:
            return await ctx.send("❌ 你的餘額不足，無法下注！")

        emojis = ["🍎", "🍊", "🍇", "💎", "7️⃣"]
        result = [random.choice(emojis) for _ in range(3)]
        
        # 製作動態效果
        slot_msg = await ctx.send("🎰 **拉霸機轉動中...**\n[ ⬛ | ⬛ | ⬛ ]")
        await asyncio.sleep(1)
        
        # 結算
        if result[0] == result[1] == result[2]:
            multiplier = 10 if result[0] == "7️⃣" else 5
            winnings = amount * multiplier
            self.update_balance(ctx.author.id, winnings - amount)
            await slot_msg.edit(content=f"🎰 **拉霸機結果**\n[ {result[0]} | {result[1]} | {result[2]} ]\n🎉 **大獎！** 恭喜 {ctx.author.mention} 贏得 **{winnings}** 金幣！ (x{multiplier})")
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            winnings = amount * 2
            self.update_balance(ctx.author.id, winnings - amount)
            await slot_msg.edit(content=f"🎰 **拉霸機結果**\n[ {result[0]} | {result[1]} | {result[2]} ]\n✨ **小獎！** {ctx.author.mention} 贏得 **{winnings}** 金幣！ (x2)")
        else:
            self.update_balance(ctx.author.id, -amount)
            await slot_msg.edit(content=f"🎰 **拉霸機結果**\n[ {result[0]} | {result[1]} | {result[2]} ]\n💀 沒中，{ctx.author.mention} 失去了 **{amount}** 金幣。")

async def setup(bot):
    await bot.add_cog(Gamble(bot))