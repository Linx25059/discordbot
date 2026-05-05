import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import sqlite3
import urllib.parse

class Finance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('bot_database.db', timeout=10.0)
        self.c = self.conn.cursor()

        # 確保 economy (錢包) 與 investments (投資組合) 資料表存在
        self.c.execute('''CREATE TABLE IF NOT EXISTS economy (user_id INTEGER PRIMARY KEY, balance INTEGER)''')
        self.c.execute('''CREATE TABLE IF NOT EXISTS investments (user_id INTEGER, symbol TEXT, amount REAL, avg_price REAL, PRIMARY KEY (user_id, symbol))''')
        self.conn.commit()

    # --- 輔助功能：讀取/更新金幣餘額 ---
    def get_balance(self, user_id):
        self.c.execute('SELECT balance FROM economy WHERE user_id = ?', (user_id,))
        result = self.c.fetchone()
        return result[0] if result else 0

    def update_balance(self, user_id, amount):
        balance = self.get_balance(user_id)
        new_balance = balance + amount
        self.c.execute('INSERT OR REPLACE INTO economy (user_id, balance) VALUES (?, ?)', (user_id, new_balance))
        self.conn.commit()
        return new_balance

    # --- 輔助功能：從 Yahoo Finance 抓取即時報價 ---
    async def fetch_price(self, query: str):
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        try:
            async with aiohttp.ClientSession() as session:
                # 1. 透過 Yahoo Search API 將「中文名稱」或「模糊代號」轉為標準的 symbol
                search_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}&quotesCount=1"
                async with session.get(search_url, headers=headers) as search_resp:
                    if search_resp.status == 200:
                        search_data = await search_resp.json()
                        quotes = search_data.get("quotes", [])
                        if not quotes:
                            return None, None, None, None, None
                        symbol = quotes[0]["symbol"]
                        short_name = quotes[0].get("shortname", symbol) # 取得公司名稱
                    else:
                        return None, None, None, None, None

                # 2. 透過 Chart API 取得精準報價
                chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                async with session.get(chart_url, headers=headers) as chart_resp:
                    if chart_resp.status == 200:
                        data = await chart_resp.json()
                        res = data.get("chart", {}).get("result")
                        if res:
                            meta = res[0]["meta"]
                            price = meta["regularMarketPrice"]
                            prev_close = meta["previousClose"]
                            currency = meta.get("currency", "USD")
                            return price, prev_close, currency, symbol, short_name
        except Exception as e:
            print(f"抓取股價失敗: {e}")
        return None, None, None, None, None

    # --- 💰 金融指令區 ---
    @commands.hybrid_command(name="price", aliases=["報價"], help="查詢即時報價 (支援代號與名稱)")
    @app_commands.describe(symbol="輸入代號或名稱 (例如: 2330, AAPL, 0050, VOO, 比特幣)")
    async def price(self, ctx, symbol: str):
        async with ctx.typing():
            price, prev_close, currency, real_symbol, short_name = await self.fetch_price(symbol)
            
            if price is None:
                return await ctx.send(f"❌ 找不到關於 `{symbol}` 的報價，請確認名稱是否正確。")

            change = price - prev_close
            change_percent = (change / prev_close) * 100
            
            # 判斷漲跌顏色與符號
            if change > 0:
                color = discord.Color.red() # 台灣習慣紅漲綠跌
                trend = "🔺"
            elif change < 0:
                color = discord.Color.green()
                trend = "🔻"
            else:
                color = discord.Color.light_grey()
                trend = "➖"

            embed = discord.Embed(title=f"📈 即時報價：{short_name} ({real_symbol})", color=color)
            embed.add_field(name="現價", value=f"**{price:,.2f}** {currency}", inline=True)
            embed.add_field(name="漲跌幅", value=f"{trend} {change:,.2f} ({change_percent:,.2f}%)", inline=True)
            embed.set_footer(text="資料來源: Yahoo Finance (延遲可能達 15 分鐘)")
            
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="buy_stock", aliases=["買股"], help="使用金幣買入虛擬資產 (支援代號與名稱)")
    @app_commands.describe(symbol="輸入代號或名稱 (例如: 2330, 0050, VOO, BTC)", amount="購買數量")
    async def buy_stock(self, ctx, symbol: str, amount: float):
        if amount <= 0:
            return await ctx.send("❌ 購買數量必須大於 0！")
            
        async with ctx.typing():
            price, _, currency, real_symbol, short_name = await self.fetch_price(symbol)
            if price is None:
                return await ctx.send(f"❌ 找不到關於 `{symbol}` 的報價，無法購買。")

            total_cost = int(price * amount) # 四捨五入取整數金幣
            if self.get_balance(ctx.author.id) < total_cost:
                return await ctx.send(f"❌ 餘額不足！購買 {amount} 單位 `{short_name}` 總共需要 **{total_cost}** 金幣。")

            # 扣款
            self.update_balance(ctx.author.id, -total_cost)

            # 存入投資組合
            self.c.execute('SELECT amount, avg_price FROM investments WHERE user_id = ? AND symbol = ?', (ctx.author.id, real_symbol))
            holding = self.c.fetchone()
            
            if holding:
                old_amount, old_avg = holding
                new_amount = old_amount + amount
                new_avg = ((old_amount * old_avg) + (amount * price)) / new_amount
                self.c.execute('UPDATE investments SET amount = ?, avg_price = ? WHERE user_id = ? AND symbol = ?', (new_amount, new_avg, ctx.author.id, real_symbol))
            else:
                self.c.execute('INSERT INTO investments (user_id, symbol, amount, avg_price) VALUES (?, ?, ?, ?)', (ctx.author.id, real_symbol, amount, price))
                
            self.conn.commit()
            await ctx.send(f"✅ 交易成功！{ctx.author.mention} 花費了 **{total_cost}** 金幣，買入了 **{amount}** 單位 `{short_name} ({real_symbol})`。\n目前的成交均價為：**{price:,.2f}** {currency}。")

    @commands.hybrid_command(name="sell_stock", aliases=["賣股"], help="賣出持有的部位換回金幣 (支援代號與名稱)")
    @app_commands.describe(symbol="輸入代號或名稱 (例如: 台積電, 0050, VOO, BTC)", amount="賣出數量")
    async def sell_stock(self, ctx, symbol: str, amount: float):
        if amount <= 0:
            return await ctx.send("❌ 賣出數量必須大於 0！")

        async with ctx.typing():
            # 先透過搜尋系統把名稱解析成正確的 symbol 才能去資料庫比對
            price, _, _, real_symbol, short_name = await self.fetch_price(symbol)
            if price is None:
                return await ctx.send(f"❌ 目前無法獲取 `{symbol}` 的即時報價，請稍後再試。")

            self.c.execute('SELECT amount, avg_price FROM investments WHERE user_id = ? AND symbol = ?', (ctx.author.id, real_symbol))
            holding = self.c.fetchone()

            if not holding or holding[0] < amount:
                return await ctx.send(f"❌ 你持有的 `{short_name} ({real_symbol})` 數量不足！(目前持有: {holding[0] if holding else 0} 單位)")

            total_earn = int(price * amount)
            
            # 更新持倉
            new_amount = holding[0] - amount
            if new_amount <= 0.00001: # 避免浮點數誤差
                self.c.execute('DELETE FROM investments WHERE user_id = ? AND symbol = ?', (ctx.author.id, real_symbol))
            else:
                self.c.execute('UPDATE investments SET amount = ? WHERE user_id = ? AND symbol = ?', (new_amount, ctx.author.id, real_symbol))
            
            # 給錢
            self.update_balance(ctx.author.id, total_earn)
            self.conn.commit()

            # 計算這筆賣出的損益
            profit = total_earn - int(holding[1] * amount)
            profit_text = f"🔺 獲利 **{profit}** 金幣" if profit > 0 else (f"🔻 虧損 **{abs(profit)}** 金幣" if profit < 0 else "➖ 不賺不賠")

            await ctx.send(f"✅ 賣出成功！{ctx.author.mention} 以 **{price:,.2f}** 的市價賣出了 **{amount}** 單位 `{short_name} ({real_symbol})`。\n獲得了 **{total_earn}** 金幣！({profit_text})")

    @commands.hybrid_command(name="portfolio", aliases=["持倉", "資產"], help="查看目前的投資組合與未實現損益")
    async def portfolio(self, ctx):
        self.c.execute('SELECT symbol, amount, avg_price FROM investments WHERE user_id = ?', (ctx.author.id,))
        holdings = self.c.fetchall()

        if not holdings:
            return await ctx.send(f"📊 {ctx.author.mention} 目前沒有持有任何投資部位喔！趕快用 `/buy_stock` 買進吧！")

        embed = discord.Embed(title=f"📊 {ctx.author.display_name} 的虛擬投資組合", color=discord.Color.blue())
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        async with ctx.typing():
            for symbol, amount, avg_price in holdings:
                current_price, _, _, _, short_name = await self.fetch_price(symbol)
                if current_price:
                    pnl = (current_price - avg_price) / avg_price * 100
                    trend = "🔺" if pnl > 0 else ("🔻" if pnl < 0 else "➖")
                    embed.add_field(name=f"🏷️ {short_name} ({symbol})", value=f"持有數量: **{amount:,.4g}**\n均價: `{avg_price:,.2f}`\n現價: `{current_price:,.2f}`\n損益: {trend} **{pnl:,.2f}%**", inline=True)
                else:
                    embed.add_field(name=f"🏷️ {short_name or symbol}", value=f"持有數量: **{amount:,.4g}**\n均價: `{avg_price:,.2f}`\n*(目前無法取得現價)*", inline=True)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Finance(bot))