import discord
from discord import app_commands
from discord.ext import commands
import random
from typing import Optional

class FoodRerollView(discord.ui.View):
    def __init__(self, cog, command_type: str, author_id: int, category: Optional[str] = None):
        super().__init__(timeout=180) # 3分鐘後按鈕自動失效
        self.cog = cog
        self.command_type = command_type
        self.author_id = author_id
        self.category = category

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # 防呆：防止別人亂點重抽按鈕
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 這是為別人推薦的喔！請自己輸入指令來抽籤。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🔄 重抽", style=discord.ButtonStyle.primary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.command_type == "eat":
            food, time_str = self.cog.get_random_food(self.category)
            embed = discord.Embed(title="🍽️ 食物推薦", description=f"不知道吃什麼的話，{time_str}為您推薦：\n\n# 🍱 **{food}**", color=discord.Color.orange())
            embed.set_footer(text="不滿意可以再點擊下方按鈕重抽喔！")
            await interaction.response.edit_message(embed=embed, view=self)
        elif self.command_type == "drink":
            drink = self.cog.get_random_drink()
            embed = discord.Embed(title="🥤 手搖飲品項推薦", description=f"口渴了嗎？今天為您推薦：\n\n# 🧋 **{drink}**", color=discord.Color.blue())
            embed.set_footer(text="不滿意可以再點擊下方按鈕重抽喔！")
            await interaction.response.edit_message(embed=embed, view=self)

import json
import os

class Food(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.food_data = self._load_food_data()

    def _load_food_data(self) -> dict:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'food_data.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "breakfast": [], "lunch": [], "dinner": [], "midnight_snack": [], "drinks": []
        }

    def get_random_food(self, category: Optional[str] = None):
        breakfast = self.food_data.get("breakfast", [])
        lunch = self.food_data.get("lunch", [])
        dinner = self.food_data.get("dinner", [])
        midnight_snack = self.food_data.get("midnight_snack", [])

        if category == "早餐":
            foods = breakfast
        elif category == "午餐":
            foods = lunch
        elif category == "晚餐":
            foods = dinner
        elif category == "宵夜":
            foods = midnight_snack
        else:
            foods = breakfast + lunch + dinner + midnight_snack

        food = random.choice(foods) if foods else "滷肉飯"
        time_str = category if category else "今天"
        
        return food, time_str

    def get_random_drink(self):
        drinks = self.food_data.get("drinks", [])
        return random.choice(drinks) if drinks else "珍珠奶茶"

    @commands.hybrid_command(name="drink", aliases=["喝什麼", "喝啥", "飲料", "手搖飲"], help="不知道要喝什麼手搖飲嗎？讓我來推薦！")
    async def drink(self, ctx: commands.Context):
        drink = self.get_random_drink()
        embed = discord.Embed(title="🥤 手搖飲品項推薦", description=f"口渴了嗎？今天為您推薦：\n\n# 🧋 **{drink}**", color=discord.Color.blue())
        embed.set_footer(text="不滿意可以再點擊下方按鈕重抽喔！")
        view = FoodRerollView(self, "drink", ctx.author.id)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Food(bot))
