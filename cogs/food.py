import discord
from discord import app_commands
from discord.ext import commands
import random
import json
import os
from typing import Optional

class FoodRerollView(discord.ui.View):
    def __init__(self, cog, command_type: str, author_id: int, category: Optional[str] = None):
        super().__init__(timeout=180)
        self.cog = cog
        self.command_type = command_type
        self.author_id = author_id
        self.category = category

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 這是為別人推薦的喔！請自己輸入指令來抽籤。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🔄 重抽", style=discord.ButtonStyle.primary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = self.cog.create_recommendation(self.command_type, self.author_id, self.category)
        await interaction.response.edit_message(embed=embed, view=view)


class Food(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.food_data = self._load_food_data()

    def _load_food_data(self) -> dict:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'food_data.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"breakfast": [], "lunch": [], "dinner": [], "midnight_snack": [], "drinks": []}

    def get_random_food(self, category: Optional[str] = None):
        cat_map = {
            "早餐": self.food_data.get("breakfast", []),
            "午餐": self.food_data.get("lunch", []),
            "晚餐": self.food_data.get("dinner", []),
            "宵夜": self.food_data.get("midnight_snack", [])
        }
        foods = cat_map.get(category) or sum(cat_map.values(), [])
        return random.choice(foods) if foods else "滷肉飯", category or "今天"

    def get_random_drink(self) -> str:
        drinks = self.food_data.get("drinks", [])
        return random.choice(drinks) if drinks else "珍珠奶茶"

    def create_recommendation(self, command_type: str, author_id: int, category: Optional[str] = None):
        view = FoodRerollView(self, command_type, author_id, category)
        if command_type == "drink":
            drink_item = self.get_random_drink()
            embed = discord.Embed(title="🥤 手搖飲品項推薦", description=f"口渴了嗎？今天為您推薦：\n\n# 🧋 **{drink_item}**", color=discord.Color.blue())
        else:
            food_item, time_str = self.get_random_food(category)
            embed = discord.Embed(title="🍽️ 食物推薦", description=f"不知道吃什麼的話，{time_str}為您推薦：\n\n# 🍱 **{food_item}**", color=discord.Color.orange())
        
        embed.set_footer(text="不滿意可以再點擊下方按鈕重抽喔！")
        return embed, view

    @commands.hybrid_command(name="drink", aliases=["喝什麼", "喝啥", "飲料", "手搖飲"], help="不知道要喝什麼手搖飲嗎？讓我來推薦！")
    async def drink(self, ctx: commands.Context):
        embed, view = self.create_recommendation("drink", ctx.author.id)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Food(bot))
