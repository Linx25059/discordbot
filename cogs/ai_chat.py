import discord
from discord.ext import commands
from google import genai
from google.genai import types
import os
from datetime import datetime

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("警告: 找不到 GEMINI_API_KEY，請確認 .env 檔案設定。")
            
        self.client = genai.Client(api_key=api_key)
        
        # 💡 第一招：改造 AI 的靈魂 (System Instruction)
        friend_persona = (
            "你現在是一個友善、熱心、且像個正常朋友一樣聊天的 Discord 機器人小幫手。請一律使用「繁體中文（台灣）」。\n"
            "說話請保持自然、親切的語氣，不用刻意裝作機器人，也不要使用過度負面、攻擊性或過於小眾的網路流行語。\n"
            "當別人找你聊天時，就像一般朋友聊天那樣回覆即可，不要太過長篇大論。\n"
            "當別人詢問知識或需要協助時，請給出清楚、正確、容易理解的答案。\n"
            "你可以使用表情符號讓對話看起來更生動，但不要過量。\n"
        )
        
        self.friend_persona = friend_persona
        
        # 💡 第二招：建立大腦記憶體 (儲存每個人的對話紀錄)
        # 用字典來存，這樣 A 講的話才不會跟 B 混在一起
        self.chat_sessions = {}
        
    async def cog_load(self):
        # 建立 Token 統計資料庫 (使用非同步全域連線)
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS token_usage (user_id INTEGER, date TEXT, total_tokens INTEGER, PRIMARY KEY (user_id, date))''')
        await self.bot.db.db.commit()

    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.hybrid_command(name="chat", aliases=["ai", "問"], help="跟 AI 朋友瞎聊")
    async def chat(self, ctx, *, prompt: str):
        async with ctx.typing():
            try:
                user_id = ctx.author.id
                
                # 如果這個人是第一次跟你聊天，就幫他開一個全新的「聊天室 (Session)」
                if user_id not in self.chat_sessions:
                    # start_chat 會自動幫我們記住上下文！
                    self.chat_sessions[user_id] = self.client.aio.chats.create(
                        model='gemini-2.5-flash',
                        config=types.GenerateContentConfig(
                            system_instruction=self.friend_persona,
                            tools=[{"google_search": {}}]  # 🔍 開啟 Google 搜尋功能，讓 AI 能聯網查閱最新資訊
                        )
                    )
                
                # 取出這個使用者的專屬對話紀錄
                user_chat = self.chat_sessions[user_id]
                
                # 傳送訊息 (API 會自動把這次的 prompt 跟之前的紀錄綁在一起送給 Gemini)
                response = await user_chat.send_message(prompt)
                
                reply_text = response.text
                if len(reply_text) > 2000:
                    reply_text = reply_text[:1995] + "..."
                    
                await ctx.send(reply_text)
                
                # --- 紀錄 Token 使用量到日誌頻道 ---
                if response.usage_metadata:
                    total_tokens = response.usage_metadata.total_token_count
                    # Gemini 2.5 Flash 的最大上下文長度為 1,048,576
                    max_tokens = 1048576
                    remaining_tokens = max_tokens - total_tokens
                    
                    # --- 紀錄每日 Token 消耗到 SQLite ---
                    today_str = datetime.now().strftime('%Y-%m-%d')
                    async with self.bot.db.db.execute('SELECT total_tokens FROM token_usage WHERE user_id = ? AND date = ?', (ctx.author.id, today_str)) as cursor:
                        row = await cursor.fetchone()
                        
                    if row:
                        await self.bot.db.db.execute('UPDATE token_usage SET total_tokens = total_tokens + ? WHERE user_id = ? AND date = ?', (total_tokens, ctx.author.id, today_str))
                    else:
                        await self.bot.db.db.execute('INSERT INTO token_usage (user_id, date, total_tokens) VALUES (?, ?, ?)', (ctx.author.id, today_str, total_tokens))
                    await self.bot.db.db.commit()

                    # --- 判斷「AI 詠唱者」成就 ---
                    async with self.bot.db.db.execute('SELECT SUM(total_tokens) FROM token_usage WHERE user_id = ?', (ctx.author.id,)) as cursor:
                        total_used = (await cursor.fetchone())[0] or 0
                        
                    if total_used >= 50000:
                        if await self.bot.db.check_and_add_achievement(ctx.author.id, '【AI 詠唱者】'):
                            await ctx.send(embed=discord.Embed(title="🤖 成就解鎖！", description=f"{ctx.author.mention} 與 AI 聊天累計消耗超過 50,000 Tokens，獲得稱號 **【AI 詠唱者】**！", color=discord.Color.gold()))

                    # 如果剩餘 Token 小於 10,000，自動傳送提醒
                    if remaining_tokens < 10000:
                        await ctx.send(embed=discord.Embed(title="⚠️ 記憶體即將額滿", description=f"{ctx.author.mention}，我們的對話記憶快滿了 (剩餘 `{remaining_tokens:,}` Token)！\n建議使用 `/忘記` 指令清除記憶喔！", color=discord.Color.orange()))
                    
                    logger_cog = self.bot.get_cog('Logger')
                    if logger_cog and ctx.guild:
                        log_channel = await logger_cog.get_log_channel(ctx.guild)
                        if log_channel:
                            log_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🤖 AI 聊天 ({ctx.author.name} 在 #{ctx.channel.name}) | 總消耗: {total_tokens:,} | 剩餘可用 Token: {remaining_tokens:,}"
                            await log_channel.send(log_msg)
                
            except Exception as e:
                if "429" in str(e):
                    await ctx.send(embed=discord.Embed(description="⏳ 稍微等我一下喔，我處理得有點慢！", color=discord.Color.orange()))
                else:
                    await ctx.send(embed=discord.Embed(title="❌ AI 發生錯誤：", description=f"```\n{e}\n```", color=discord.Color.red()))

# 清除記憶的指令 (可選)
    @commands.hybrid_command(name="忘記", help="清除 AI 對你的記憶")
    async def clear_memory(self, ctx):
        user_id = ctx.author.id
        if user_id in self.chat_sessions:
            del self.chat_sessions[user_id]
            await ctx.send(embed=discord.Embed(description="🤯 好的，我已經忘記我們先前的對話了！", color=discord.Color.green()))
        else:
            await ctx.send(embed=discord.Embed(description="🤔 我們好像還沒有聊過天喔！", color=discord.Color.light_grey()))

    @commands.hybrid_command(name="token_stats", aliases=["消耗統計", "token統計"], help="【管理員】查看今日所有使用者的 Token 消耗量與估算成本")
    @commands.has_permissions(administrator=True)
    async def token_stats(self, ctx):
        today_str = datetime.now().strftime('%Y-%m-%d')
        async with self.bot.db.db.execute('SELECT user_id, total_tokens FROM token_usage WHERE date = ? ORDER BY total_tokens DESC', (today_str,)) as cursor:
            results = await cursor.fetchall()
        
        if not results:
            return await ctx.send(embed=discord.Embed(description="📊 今天還沒有任何人使用 AI 聊天功能喔！", color=discord.Color.light_grey()), ephemeral=True)
            
        embed = discord.Embed(title=f"📊 今日 ({today_str}) Token 消耗與成本統計", color=discord.Color.blue())
        
        total_today = 0
        # 假設 Gemini Flash 平均每 100 萬 Token 混合成本約為 $0.15 USD (約 5 TWD)
        twd_per_million = 5.0
        
        for user_id, tokens in results:
            user = self.bot.get_user(user_id)
            name = user.name if user else f"未知用戶 ({user_id})"
            user_cost = (tokens / 1000000) * twd_per_million
            embed.add_field(name=name, value=f"`{tokens:,}` Tokens (約 NT$ `{user_cost:.4f}`)", inline=False)
            total_today += tokens
            
        total_cost = (total_today / 1000000) * twd_per_million
        embed.description = f"🔥 **今日總消耗 Token**：`{total_today:,}` Tokens\n💸 **估算成本**：約 NT$ `{total_cost:.4f}`"
        embed.set_footer(text="※ 成本以 100萬 Token = 5 TWD 估算，實際費用請依 Google Cloud 帳單為準。")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AIChat(bot))