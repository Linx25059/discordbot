import discord
from discord import app_commands
from discord.ext import commands
import random

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('bot_database.db', timeout=10.0)
        self.c = self.conn.cursor()
        
        self.c.execute('''CREATE TABLE IF NOT EXISTS economy
                          (user_id INTEGER PRIMARY KEY, balance INTEGER)''')
        self.c.execute('''CREATE TABLE IF NOT EXISTS inventory
                          (user_id INTEGER, item_name TEXT, amount INTEGER)''')
        self.conn.commit()

        # 🏪 幫每個商品新增 "id" 欄位
        self.shop_items = {
            "神秘寶箱": {"id": "1", "price": 500, "emoji": "🎁", "desc": "【抽獎】開啟後隨機獲得 100 ~ 1500 金幣。"},
            "精力飲料": {"id": "2", "price": 300, "emoji": "🧃", "desc": "【消耗品】喝下去立刻重置 /work 的冷卻時間。"},
            "大聲公": {"id": "3", "price": 600, "emoji": "📢", "desc": "【工具】讓機器人幫你發出一則超醒目的全頻廣播！"},
            "搶劫面罩": {"id": "4", "price": 1000, "emoji": "🥷", "desc": "【攻擊】戴上它去搶劫別人！有風險，被警察抓到會重罰。"},
            "肥皂": {"id": "5", "price": 50, "emoji": "🧼", "desc": "【陷阱】不知道用來幹嘛的，千萬不要自己撿起來。"}
        }

    # --- 輔助功能區 ---
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

    def get_item_amount(self, user_id, item_name):
        self.c.execute('SELECT amount FROM inventory WHERE user_id = ? AND item_name = ?', (user_id, item_name))
        result = self.c.fetchone()
        return result[0] if result else 0

    def add_item(self, user_id, item_name, amount=1):
        current_amount = self.get_item_amount(user_id, item_name)
        if current_amount == 0 and amount > 0:
            self.c.execute('INSERT INTO inventory (user_id, item_name, amount) VALUES (?, ?, ?)', (user_id, item_name, amount))
        else:
            self.c.execute('UPDATE inventory SET amount = ? WHERE user_id = ? AND item_name = ?', (current_amount + amount, user_id, item_name))
        self.conn.commit()

    # --- 基礎經濟指令 ---
    @commands.hybrid_command(name="bal", aliases=["balance", "錢包"], help="查看餘額")
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        balance = self.get_balance(member.id)
        embed = discord.Embed(title="💳 帳戶餘額", color=discord.Color.gold())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="持有者", value=member.mention, inline=True)
        embed.add_field(name="可用餘額", value=f"**{balance}** 枚金幣", inline=True)
        await ctx.send(embed=embed)

    @commands.cooldown(1, 86400, commands.BucketType.user)
    @commands.hybrid_command(name="daily", aliases=["每日", "簽到"])
    async def daily(self, ctx):
        reward = 500
        self.update_balance(ctx.author.id, reward)
        await ctx.send(f"🎉 {ctx.author.mention} 簽到成功！獲得了 **{reward}** 枚金幣！")

    @commands.cooldown(1, 600, commands.BucketType.user)
    @commands.hybrid_command(name="work", aliases=["打工"])
    async def work(self, ctx):
        jobs = ["幫 Discord 伺服器掃地", "去巷口賣香腸", "幫群主搥背", "去麥當勞炸薯條"]
        salary = random.randint(50, 150)
        self.update_balance(ctx.author.id, salary)
        await ctx.send(f"💼 {ctx.author.mention} {random.choice(jobs)}，賺到了 **{salary}** 枚金幣！")

    @commands.hybrid_command(name="pay", aliases=["轉帳"], help="轉帳金幣給其他玩家")
    async def pay(self, ctx, member: discord.Member, amount: int):
        if amount <= 0 or member.id == ctx.author.id:
            await ctx.send("❌ 轉帳金額錯誤或不能轉給自己！")
            return
        if self.get_balance(ctx.author.id) < amount:
            await ctx.send("❌ 餘額不足！")
            return
        self.update_balance(ctx.author.id, -amount)
        self.update_balance(member.id, amount)
        await ctx.send(f"💸 成功轉帳了 **{amount}** 枚金幣給 {member.mention}！")

    # --- 商城與背包 ---
    @commands.hybrid_command(name="shop", aliases=["商城", "商店"], help="查看商城商品")
    async def shop(self, ctx):
        embed = discord.Embed(title="🛒 伺服器商城", description="使用 `/buy <編號或名稱>` 購買！", color=discord.Color.blue())
        for item, info in self.shop_items.items():
            # ✨ 面板更新：在商品前方顯示 [編號]
            embed.add_field(name=f"[{info['id']}] {info['emoji']} {item} - 💰 {info['price']} 金幣", value=info['desc'], inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="buy", aliases=["購買", "買"], help="購買商城物品 (請輸入名稱或編號)")
    @app_commands.describe(item_input="選擇要購買的商品")
    @app_commands.choices(item_input=[
        app_commands.Choice(name="🎁 神秘寶箱 (500金幣)", value="神秘寶箱"),
        app_commands.Choice(name="🧃 精力飲料 (300金幣)", value="精力飲料"),
        app_commands.Choice(name="📢 大聲公 (600金幣)", value="大聲公"),
        app_commands.Choice(name="🥷 搶劫面罩 (1000金幣)", value="搶劫面罩"),
        app_commands.Choice(name="🧼 肥皂 (50金幣)", value="肥皂")
    ])
    async def buy(self, ctx, *, item_input: str):
        target_item = None
        
        # ✨ 邏輯更新：判斷玩家輸入的是「商品名稱」還是「商品編號」
        if item_input in self.shop_items:
            # 如果輸入的是正確的商品名稱
            target_item = item_input
        else:
            # 如果輸入的不是名稱，就去比對編號
            for item_name, info in self.shop_items.items():
                if info["id"] == str(item_input): # 確保轉換成字串比對
                    target_item = item_name
                    break
                    
        # 如果比對完還是找不到，就噴錯
        if not target_item:
            await ctx.send("❌ 商城裡沒有這個東西喔！請確認你輸入的「**編號**」或「**名稱**」是否正確。")
            return

        # 找到商品後，取出對應的價格與符號
        price = self.shop_items[target_item]["price"]
        emoji = self.shop_items[target_item]["emoji"]
        
        if self.get_balance(ctx.author.id) < price:
            await ctx.send(f"❌ 你的錢不夠啦！這個需要 **{price}** 金幣。")
            return
            
        self.update_balance(ctx.author.id, -price)
        self.add_item(ctx.author.id, target_item, 1)
        await ctx.send(f"🛍️ {ctx.author.mention} 花費了 **{price}** 金幣，購買了 {emoji} **{target_item}**！")

    @commands.hybrid_command(name="inv", aliases=["inventory", "背包"], help="查看自己或別人的背包")
    async def inventory(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        self.c.execute('SELECT item_name, amount FROM inventory WHERE user_id = ? AND amount > 0', (member.id,))
        items = self.c.fetchall()
        if not items:
            await ctx.send(f"🎒 {member.mention} 的背包空空如也。")
            return
        embed = discord.Embed(title=f"🎒 {member.display_name} 的背包", color=discord.Color.purple())
        embed.set_thumbnail(url=member.display_avatar.url)
        for item_name, amount in items:
            emoji = self.shop_items.get(item_name, {}).get("emoji", "📦")
            embed.add_field(name=f"{emoji} {item_name}", value=f"數量：**{amount}**", inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="trade", aliases=["giveitem", "給物品"], help="交易道具給其他玩家")
    @app_commands.describe(member="交易對象", amount="交易數量", item_name="選擇要交易的道具")
    @app_commands.choices(item_name=[
        app_commands.Choice(name="🎁 神秘寶箱", value="神秘寶箱"),
        app_commands.Choice(name="🧃 精力飲料", value="精力飲料"),
        app_commands.Choice(name="📢 大聲公", value="大聲公"),
        app_commands.Choice(name="🥷 搶劫面罩", value="搶劫面罩"),
        app_commands.Choice(name="🧼 肥皂", value="肥皂")
    ])
    async def trade(self, ctx, member: discord.Member, amount: int, *, item_name: str):
        if amount <= 0 or member.id == ctx.author.id:
            await ctx.send("❌ 數量錯誤或不能交易給自己！")
            return
        if self.get_item_amount(ctx.author.id, item_name) < amount:
            await ctx.send(f"❌ 你的背包裡沒有那麼多 **{item_name}**！")
            return
        self.add_item(ctx.author.id, item_name, -amount)
        self.add_item(member.id, item_name, amount)
        await ctx.send(f"🤝 交易成功！{ctx.author.mention} 給了 {member.mention} **{amount}** 個 **{item_name}**！")

    # --- 使用物品 ---
    @commands.hybrid_command(name="use", aliases=["使用"], help="使用道具")
    @app_commands.describe(item_name="選擇要使用的道具", args="道具的附加參數 (例如廣播內容或搶劫對象)")
    @app_commands.choices(item_name=[
        app_commands.Choice(name="🎁 神秘寶箱", value="神秘寶箱"),
        app_commands.Choice(name="🧃 精力飲料", value="精力飲料"),
        app_commands.Choice(name="📢 大聲公", value="大聲公"),
        app_commands.Choice(name="🥷 搶劫面罩", value="搶劫面罩"),
        app_commands.Choice(name="🧼 肥皂", value="肥皂")
    ])
    async def use_item(self, ctx, item_name: str, *, args: str = None):
        if self.get_item_amount(ctx.author.id, item_name) <= 0:
            await ctx.send(f"❌ 你的背包裡沒有 **{item_name}** 啦！快去 `/shop` 買！")
            return

        if item_name == "神秘寶箱":
            self.add_item(ctx.author.id, item_name, -1)
            reward = random.randint(100, 1500)
            self.update_balance(ctx.author.id, reward)
            await ctx.send(f"🎁 {ctx.author.mention} 興奮地打開了神秘寶箱...\n✨ 裡面裝了 **{reward}** 金幣！")

        elif item_name == "精力飲料":
            self.add_item(ctx.author.id, item_name, -1)
            self.work.reset_cooldown(ctx)
            await ctx.send(f"🧃 {ctx.author.mention} 一口氣喝完了精力飲料！\n💪 覺得充滿了力量，現在可以立刻再次使用 `/work` 打工了！")

        elif item_name == "大聲公":
            if not args:
                await ctx.send("❌ 浪費了一個大聲公！你沒有告訴我要廣播什麼啦！\n👉 正確用法：`/use 大聲公 大家出來玩！`")
                self.add_item(ctx.author.id, item_name, -1)
                return
            self.add_item(ctx.author.id, item_name, -1)
            embed = discord.Embed(title="📢 全頻廣播", description=f"### {args}", color=discord.Color.red())
            embed.set_author(name=f"{ctx.author.display_name} 拿著大聲公大喊：", icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)

        elif item_name == "搶劫面罩":
            if not args:
                await ctx.send("❌ 你戴上面罩四處張望，卻不知道要搶誰。\n👉 正確用法：`/use 搶劫面罩 @標記某人`")
                return
            
            try:
                target = await commands.MemberConverter().convert(ctx, args)
            except:
                await ctx.send("❌ 找不到你想搶劫的對象！請確實標記 (@) 對方。")
                return
                
            if target.id == ctx.author.id:
                await ctx.send("❌ 你有病嗎？搶劫自己幹嘛啦！")
                return
            
            self.add_item(ctx.author.id, item_name, -1)
                
            target_bal = self.get_balance(target.id)
            if target_bal < 100:
                await ctx.send(f"🥷 {ctx.author.mention} 試圖搶劫 {target.mention}，但發現對方是個連 100 塊都沒有的窮光蛋，只好塞給他一顆糖果後離開了。")
                return
                
            if random.choice([True, False]):
                stolen = int(target_bal * random.uniform(0.1, 0.3))
                self.update_balance(target.id, -stolen)
                self.update_balance(ctx.author.id, stolen)
                await ctx.send(f"🔫 **搶劫成功！** {ctx.author.mention} 趁 {target.mention} 不注意，搶走了 **{stolen}** 金幣！趕快跑！")
            else:
                fine = 500
                self.update_balance(ctx.author.id, -fine)
                await ctx.send(f"🚓 **警報！警報！** {ctx.author.mention} 搶劫失敗，被警察抓個正著！\n💸 面罩被沒收，並繳納了 **{fine}** 金幣的罰款。")

        elif item_name == "肥皂":
            self.add_item(ctx.author.id, item_name, -1)
            lost = random.randint(10, 50)
            self.update_balance(ctx.author.id, -lost)
            await ctx.send(f"🧼 {ctx.author.mention} 在洗澡時不小心弄掉了肥皂... 彎腰去撿的時候發生了不好的事。\n💸 為了看醫生，付了 **{lost}** 金幣的醫藥費。")

async def setup(bot):
    await bot.add_cog(Economy(bot))