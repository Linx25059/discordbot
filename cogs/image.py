import discord
from discord.ext import commands
import aiohttp
import io
from PIL import Image, ImageDraw
import urllib.parse
import random

class ImageGen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.hybrid_command(name="jail", aliases=["大牢", "監獄"], help="把別人的頭貼關進大牢")
    async def jail(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        
        # 🛡️ 防禦與修復：discord.py 2.0+ 已移除 with_format()，必須使用 replace(format="png")
        # 加上 size=512 確保抓取到足夠清晰的圖片以供後續 PIL 處理
        avatar_url = member.display_avatar.replace(format="png", size=512).url
        
        async with ctx.typing():
            try:
                async with self.bot.session.get(avatar_url) as resp:
                    if resp.status != 200:
                        return await ctx.send("❌ 抓不到大頭貼，可能有點問題！")
                    data = await resp.read()
                
                # ⚡ 使用 run_in_executor 避免 PIL 阻塞事件迴圈
                def process_image(img_data):
                    base_img = Image.open(io.BytesIO(img_data)).convert("RGBA")
                    base_img = base_img.resize((400, 400))
                    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
                    draw = ImageDraw.Draw(overlay)
                    for i in range(0, 400, 50):
                        draw.line([(i, 0), (i, 400)], fill=(60, 60, 60, 255), width=15)
                    draw.rectangle([(0, 0), (400, 400)], outline=(60, 60, 60, 255), width=25)
                    final_img = Image.alpha_composite(base_img, overlay)
                    
                    image_binary = io.BytesIO()
                    final_img.save(image_binary, "PNG")
                    image_binary.seek(0)
                    return image_binary

                image_binary = await self.bot.loop.run_in_executor(None, process_image, data)
                
                embed = discord.Embed(title="🚓 逮捕歸案", description=f"{member.mention} 被關進大牢了！", color=discord.Color.dark_gray())
                embed.set_image(url="attachment://jail.png")
                await ctx.send(embed=embed, file=discord.File(fp=image_binary, filename="jail.png"))
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"⚠️ 產生圖片時發生錯誤：{e}", color=discord.Color.red()), ephemeral=True)

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.hybrid_command(name="meme", aliases=["迷因"], help="產生經典迷因圖 (文字間請用 | 隔開)")
    async def meme(self, ctx, *, text: str):
        parts = [p.strip() for p in text.split("|")]
        top_text = parts[0] if len(parts) > 0 and parts[0] else "_"
        bottom_text = parts[1] if len(parts) > 1 and parts[1] else "_"

        # 替換掉 Memegen API 會衝突的特殊字元
        def clean_text(t):
            t = t.replace("-", "--").replace("_", "__").replace(" ", "_")
            t = t.replace("?", "~q").replace("%", "~p").replace("#", "~h").replace("/", "~s")
            return urllib.parse.quote(t)

        safe_top = clean_text(top_text)
        safe_bottom = clean_text(bottom_text)

        # 隨機挑選一個支援上下兩段文字的經典迷因模板
        templates = ["drake", "twobuttons", "spiderman", "disastergirl", "doge"]
        template = random.choice(templates)

        meme_url = f"https://api.memegen.link/images/{template}/{safe_top}/{safe_bottom}.png"
        
        embed = discord.Embed(title="🖼️ 你的迷因圖做好了！", color=discord.Color.random())
        embed.set_image(url=meme_url)
        embed.set_footer(text=f"由 {ctx.author.display_name} 產生 • 模板: {template}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ImageGen(bot))