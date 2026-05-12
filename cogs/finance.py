import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import datetime

class Finance(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS market_news_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS virtual_stocks (symbol TEXT PRIMARY KEY, name TEXT, prev_price INTEGER, price INTEGER, next_price INTEGER)''')
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS investments (user_id INTEGER, symbol TEXT, amount INTEGER, avg_price REAL, PRIMARY KEY (user_id, symbol))''')
        await self.bot.db.db.commit()
        await self.init_virtual_stocks()
        self.market_update_loop.start()

    def cog_unload(self):
        self.market_update_loop.cancel()

    async def init_virtual_stocks(self):
        """初始化預設的 15 支惡搞股票"""
        async with self.bot.db.db.execute('SELECT COUNT(*) FROM virtual_stocks') as cursor:
            count = await cursor.fetchone()
            
        if count[0] == 0:
            # 預設 15 支超有梗的虛擬股票
            stocks = [
                ("TMC", "護國神山台積電", 1000),
                ("LRF", "滷肉飯指數", 50),
                ("BBM", "珍奶概念股", 60),
                ("CKP", "雞排控股", 80),
                ("MCB", "魔法小卡銀行", 150),
                ("FMI", "炎上傳媒", 40),
                ("DLY", "拖延症生技", 120),
                ("KBD", "鍵盤網民科技", 90),
                ("SLV", "社畜人壽", 200),
                ("FFS", "財富自由航運", 300),
                ("DOGE", "狗狗幣", 10),
                ("SGL", "單身狗同盟", 30),
                ("H2O", "快樂肥宅水", 25),
                ("VWA", "虛擬老婆AI", 500),
                ("OWL", "熬夜黑眼圈", 15)
            ]
            for sym, name, price in stocks:
                next_price = max(1, int(price * random.uniform(0.8, 1.2)))
                await self.bot.db.db.execute('INSERT INTO virtual_stocks VALUES (?, ?, ?, ?, ?)', (sym, name, price, price, next_price))
            await self.bot.db.db.commit()

    # 每小時整點自動更新股價的背景任務
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    hourly_times = [datetime.time(hour=h, minute=0, second=0, tzinfo=tz_tw) for h in range(24)]
    
    @tasks.loop(time=hourly_times)
    async def market_update_loop(self):
        async with self.bot.db.db.execute('SELECT symbol, name, price, next_price FROM virtual_stocks') as cursor:
            stocks = await cursor.fetchall()
            
        for sym, name, price, next_price in stocks:
            # 產生下下個小時的價格 (加入 5% 機率暴跌或暴漲的黑天鵝事件)
            if random.random() < 0.05:
                volatility = random.uniform(0.5, 2.0)
            else:
                volatility = random.uniform(0.85, 1.15)
            
            # 企業級修復：防止股票跌到 1 之後永遠無法翻身的「殭屍股 Bug」
            new_next = int(next_price * volatility)
            if new_next == next_price:
                if volatility > 1.0:
                    new_next += 1
                elif volatility < 1.0 and new_next > 1:
                    new_next -= 1
            new_next = max(1, new_next)
            
            await self.bot.db.db.execute('UPDATE virtual_stocks SET prev_price = ?, price = ?, next_price = ? WHERE symbol = ?', (price, next_price, new_next, sym))
        await self.bot.db.db.commit()

        # --- 📡 播報虛擬股市新聞 ---
        if stocks:
            # 找出這小時漲幅最大與跌幅最大的股票
            top_gainer = max(stocks, key=lambda x: (x[3] - x[2]) / x[2] if x[2] > 0 else -1)
            top_loser = min(stocks, key=lambda x: (x[3] - x[2]) / x[2] if x[2] > 0 else 1)
            
            gainer_pct = (top_gainer[3] - top_gainer[2]) / top_gainer[2] * 100 if top_gainer[2] > 0 else 0
            loser_pct = (top_loser[3] - top_loser[2]) / top_loser[2] * 100 if top_loser[2] > 0 else 0

            gainer_news = random.choice([
                f"🚀 **【市場快訊】** `{top_gainer[1]}` 突發重大利多，股價上漲 **+{gainer_pct:.1f}%**！",
                f"📈 **【強勢股表現】** `{top_gainer[1]}` 表現亮眼，本期上漲 **+{gainer_pct:.1f}%**。",
                f"🔥 **【熱門焦點】** `{top_gainer[1]}` 買氣旺盛，單期漲幅達 **+{gainer_pct:.1f}%**。"
            ])

            loser_news = random.choice([
                f"📉 **【市場警報】** `{top_loser[1]}` 遭遇賣壓，股價下跌 **{loser_pct:.1f}%**。",
                f"💥 **【弱勢股表現】** `{top_loser[1]}` 表現疲軟，本期下跌 **{loser_pct:.1f}%**。",
                f"⚠️ **【風險提示】** `{top_loser[1]}` 跌幅達 **{loser_pct:.1f}%**，請投資人留意風險。"
            ])

            embed = discord.Embed(title="🗞️ 股市快訊", description="每小時為您播報市場最新動態！", color=discord.Color.gold())
            embed.add_field(name="🔺 本期飆股", value=gainer_news, inline=False)
            embed.add_field(name="🔻 本期冥燈", value=loser_news, inline=False)
            embed.set_footer(text="使用 /market 查看詳細股市行情。")

            # 廣播給所有有設定的頻道
            async with self.bot.db.db.execute('SELECT channel_id FROM market_news_settings') as cursor:
                channels = [row[0] async for row in cursor]

            for channel_id in channels:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(embed=embed)
                    except Exception:
                        pass

    @market_update_loop.before_loop
    async def before_market_update(self):
        await self.bot.wait_until_ready()

    # --- 💰 虛擬股市指令區 ---
    @commands.hybrid_command(name="setmarketnews", aliases=["設定股市新聞"], help="設定當前頻道為股市新聞自動播報頻道")
    @commands.has_permissions(manage_channels=True)
    async def set_market_news(self, ctx):
        await self.bot.db.db.execute('INSERT OR REPLACE INTO market_news_settings (guild_id, channel_id) VALUES (?, ?)', (ctx.guild.id, ctx.channel.id))
        await self.bot.db.db.commit()
        
        embed = discord.Embed(title="📡 財經新聞頻道設定完畢", description=f"已將 {ctx.channel.mention} 設為股市快訊播報頻道。", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="market", aliases=["股市", "股票", "大盤"], help="查看虛擬股市的即時行情 (每小時更新)")
    async def market(self, ctx):
        async with self.bot.db.db.execute('SELECT symbol, name, price, prev_price FROM virtual_stocks') as cursor:
            stocks = await cursor.fetchall()
        
        embed = discord.Embed(title="📊 虛擬股市行情", description="股市價格每小時變動，低買高賣來累積財富吧！", color=discord.Color.dark_theme())
        
        for sym, name, price, prev_price in stocks:
            change = price - prev_price
            change_percent = (change / prev_price * 100) if prev_price > 0 else 0
            if change > 0:
                trend = "🔺"
            elif change < 0:
                trend = "🔻"
            else:
                trend = "➖"
                
            embed.add_field(name=f"🏷️ {name} ({sym})", value=f"現價: **{price}** 金幣\n漲跌: {trend} {abs(change)} ({change_percent:+.1f}%)", inline=True)
            
        embed.set_footer(text="使用 /buy_stock 買入、/sell_stock 賣出，或是用 /insider 購買內線消息！")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="insider", aliases=["內線消息", "內線"], help="花費 5,000 金幣購買下小時的股市內線消息")
    async def insider(self, ctx):
        cost = 5000
        if await self.bot.db.get_balance(ctx.author.id) < cost:
            return await ctx.send(f"❌ 餘額不足，購買內線消息需要 {cost:,} 金幣喔！")

        await self.bot.db.update_balance(ctx.author.id, -cost)
        
        # 企業級優化：同時抓取 symbol 與 name，並防止黑天鵝暴跌時給出「預估暴漲 -10%」的蠢訊息
        async with self.bot.db.db.execute('SELECT symbol, name, price, next_price FROM virtual_stocks') as cursor:
            stocks = await cursor.fetchall()
            
        best_stock = max(stocks, key=lambda x: (x[3] - x[2]) / x[2] if x[2] > 0 else -float('inf'))
        
        increase_pct = ((best_stock[3] - best_stock[2]) / best_stock[2]) * 100
        
        try:
            if increase_pct > 0:
                await ctx.author.send(f"🤫 **【內線消息】**\n根據可靠消息指出，下個小時 **{best_stock[1]} ({best_stock[0]})** 預計將會上漲約 **+{increase_pct:.1f}%**！")
            else:
                await ctx.author.send(f"⚠️ **【內線消息】**\n大盤趨勢不佳，下個小時預計全面下跌，連表現最好的 **{best_stock[1]} ({best_stock[0]})** 也可能下跌 **{increase_pct:.1f}%**。請小心投資！")
                
            await ctx.send(f"🕵️‍♂️ {ctx.author.mention} 購買了最新的股市內線消息。 (已私訊)")
        except discord.Forbidden:
            await self.bot.db.update_balance(ctx.author.id, cost) # 退款
            await ctx.send("❌ 無法傳送私訊給您，請確認是否開啟了伺服器私訊功能。(金幣已退還)")

    @commands.hybrid_command(name="buy_stock", aliases=["買股"], help="買入虛擬股票")
    @app_commands.describe(symbol="輸入股票代號或名稱 (例如: TMC, 滷肉飯指數)", amount="購買數量")
    async def buy_stock(self, ctx, symbol: str, amount: int):
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(description="❌ 購買數量必須大於 0！", color=discord.Color.red()), ephemeral=True)
            
        async with self.bot.db.db.execute('SELECT symbol, name, price FROM virtual_stocks WHERE symbol = ? OR name = ?', (symbol.upper(), symbol)) as cursor:
            stock = await cursor.fetchone()
        
        if not stock:
            return await ctx.send(embed=discord.Embed(description=f"❌ 找不到股票 `{symbol}`，請使用 `/market` 確認正確的名稱或代號。", color=discord.Color.red()), ephemeral=True)
            
        real_symbol, short_name, price = stock
        total_cost = price * amount
        
        if await self.bot.db.get_balance(ctx.author.id) < total_cost:
            return await ctx.send(embed=discord.Embed(description=f"❌ 餘額不足！本次交易需要 **{total_cost:,}** 金幣。", color=discord.Color.red()), ephemeral=True)

        # 扣款
        await self.bot.db.update_balance(ctx.author.id, -total_cost)

        # 存入投資組合
        async with self.bot.db.db.execute('SELECT amount, avg_price FROM investments WHERE user_id = ? AND symbol = ?', (ctx.author.id, real_symbol)) as cursor:
            holding = await cursor.fetchone()
        
        if holding:
            old_amount, old_avg = holding
            new_amount = old_amount + amount
            new_avg = ((old_amount * old_avg) + (amount * price)) / new_amount
            await self.bot.db.db.execute('UPDATE investments SET amount = ?, avg_price = ? WHERE user_id = ? AND symbol = ?', (new_amount, new_avg, ctx.author.id, real_symbol))
        else:
            await self.bot.db.db.execute('INSERT INTO investments (user_id, symbol, amount, avg_price) VALUES (?, ?, ?, ?)', (ctx.author.id, real_symbol, amount, float(price)))
            
        await self.bot.db.db.commit()
        embed = discord.Embed(description=f"✅ 交易成功！{ctx.author.mention} 花費了 **{total_cost:,}** 金幣，買入了 **{amount}** 股 `{short_name}`。\n成交均價：**{price}** 金幣。", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="sell_stock", aliases=["賣股"], help="賣出持有的虛擬股票")
    @app_commands.describe(symbol="輸入股票代號或名稱 (例如: TMC, 滷肉飯指數)", amount="賣出數量")
    async def sell_stock(self, ctx, symbol: str, amount: int):
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(description="❌ 賣出數量必須大於 0！", color=discord.Color.red()), ephemeral=True)

        async with self.bot.db.db.execute('SELECT symbol, name, price FROM virtual_stocks WHERE symbol = ? OR name = ?', (symbol.upper(), symbol)) as cursor:
            stock = await cursor.fetchone()
        
        if not stock:
            return await ctx.send(embed=discord.Embed(description=f"❌ 找不到股票 `{symbol}`，請確認名稱是否正確。", color=discord.Color.red()), ephemeral=True)
            
        real_symbol, short_name, price = stock

        async with self.bot.db.db.execute('SELECT amount, avg_price FROM investments WHERE user_id = ? AND symbol = ?', (ctx.author.id, real_symbol)) as cursor:
            holding = await cursor.fetchone()

        if not holding or holding[0] < amount:
            return await ctx.send(embed=discord.Embed(description=f"❌ 持有數量不足！你目前只持有 {int(holding[0]) if holding else 0} 股。", color=discord.Color.red()), ephemeral=True)

        total_earn = price * amount
        
        # 更新持倉
        new_amount = holding[0] - amount
        if new_amount <= 0:
            await self.bot.db.db.execute('DELETE FROM investments WHERE user_id = ? AND symbol = ?', (ctx.author.id, real_symbol))
        else:
            await self.bot.db.db.execute('UPDATE investments SET amount = ? WHERE user_id = ? AND symbol = ?', (new_amount, ctx.author.id, real_symbol))
        
        # 給錢
        await self.bot.db.update_balance(ctx.author.id, total_earn)
        await self.bot.db.db.commit()

        # 計算這筆賣出的損益與成就
        profit = total_earn - int(holding[1] * amount)
        pnl_percent = ((price - holding[1]) / holding[1]) * 100 if holding[1] > 0 else 0
        profit_text = f"🔺 獲利 **{profit:,}** 金幣" if profit > 0 else (f"🔻 虧損 **{abs(profit):,}** 金幣" if profit < 0 else "➖ 損益打平")

        ach_msg = ""
        if pnl_percent >= 100:
            if await self.bot.db.check_and_add_achievement(ctx.author.id, '【股票大亨】'):
                ach_msg = "\n\n📈 **成就解鎖！** 投資獲利翻倍！獲得稱號 **【股票大亨】**！"
        elif pnl_percent <= -50:
            if await self.bot.db.check_and_add_achievement(ctx.author.id, '【超級大韭菜】'):
                ach_msg = "\n\n📉 **成就解鎖！** 慘賠超過 50%... 獲得稱號 **【超級大韭菜】**！"

        await ctx.send(embed=discord.Embed(description=f"✅ 賣出成功！{ctx.author.mention} 以 **{price}** 金幣賣出了 **{amount}** 股 `{short_name}`。\n獲得了 **{total_earn:,}** 金幣！\n\n{profit_text}{ach_msg}", color=discord.Color.green()))

    @commands.hybrid_command(name="portfolio", aliases=["持倉", "資產"], help="查看目前的投資組合與損益")
    async def portfolio(self, ctx):
        async with self.bot.db.db.execute('''SELECT i.symbol, i.amount, i.avg_price, v.name, v.price 
                          FROM investments i 
                          LEFT JOIN virtual_stocks v ON i.symbol = v.symbol 
                          WHERE i.user_id = ? AND i.amount > 0''', (ctx.author.id,)) as cursor:
            holdings = await cursor.fetchall()

        if not holdings:
            return await ctx.send(f"📊 {ctx.author.mention} 目前沒有持有任何股票喔！")

        embed = discord.Embed(title=f"📊 {ctx.author.display_name} 的投資組合", color=discord.Color.blue())
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        total_investment = 0
        total_value = 0

        for symbol, amount, avg_price, name, current_price in holdings:
            if current_price is None:
                current_price = avg_price # 防呆：若查無現價則用均價取代
                name = symbol
            
            pnl = (current_price - avg_price) / avg_price * 100
            trend = "🔺" if pnl > 0 else ("🔻" if pnl < 0 else "➖")
            
            cost = amount * avg_price
            value = amount * current_price
            total_investment += cost
            total_value += value
            
            embed.add_field(name=f"🏷️ {name} ({symbol})", value=f"持有數量: **{int(amount)}** 股\n均價: `{avg_price:.1f}` | 現價: `{current_price}`\n損益: {trend} **{pnl:+.1f}%**", inline=True)

        total_pnl_pct = ((total_value - total_investment) / total_investment * 100) if total_investment > 0 else 0
        total_trend = "🔺" if total_pnl_pct > 0 else ("🔻" if total_pnl_pct < 0 else "➖")
        embed.description = f"**總投入成本**: `{total_investment:,.0f}` 金幣\n**目前總市值**: `{total_value:,.0f}` 金幣\n**總未實現損益**: {total_trend} **{total_pnl_pct:+.1f}%**"

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Finance(bot))