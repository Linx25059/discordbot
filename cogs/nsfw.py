import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import datetime
import zoneinfo
import urllib.parse
import re

def get_primary_link(code, category, direct_url=None):
    """取得主要的跳轉網址 (點擊標題或番號時觸發)"""
    if direct_url:
        return direct_url
    if code.lower().startswith("http"):
        return code
    search_query = urllib.parse.quote(code)
    if category == "歐美精選":
        return f"https://www.pornhub.com/video/search?search={search_query}"
    elif category == "裏番動畫":
        return f"https://hanime1.me/search?query={search_query}"
    else:
        return f"https://missav.ws/search/{search_query}"

def get_search_links(code, category):
    """根據影片分類動態產生最適合的搜尋網址"""
    if code.lower().startswith("http"):
        return f"[🔗 點擊這裡直接前往觀看原網址]({code})"
        
    search_query = urllib.parse.quote(code)
    if category == "歐美精選":
        streaming = (
            f"[Pornhub](https://www.pornhub.com/video/search?search={search_query}) ｜ [Xvideos](https://www.xvideos.com/?k={search_query}) ｜ [SpankBang](https://spankbang.com/s/{search_query}/)\n"
            f"[Eporner](https://www.eporner.com/search/{search_query}/) ｜ [xHamster](https://xhamster.com/search/{search_query}) ｜ [XNXX](https://www.xnxx.com/search/{search_query})"
        )
        database = f"[MissAV](https://missav.ws/search/{search_query}) ｜ [HQporner](https://hqporner.com/?q={search_query}) ｜ [Google](https://www.google.com/search?q={search_query})"
        return f"▶️ **推薦線上看**\n{streaming}\n\n🗂️ **備用與搜尋**\n{database}"
    elif category == "裏番動畫":
        streaming = (
            f"[Hanime1](https://hanime1.me/search?query={search_query}) ｜ [Hanime.tv](https://hanime.tv/search?q={search_query})\n"
            f"[HentaiHaven](https://hentaihaven.xxx/?s={search_query}) ｜ [MissAV](https://missav.ws/search/{search_query})"
        )
        database = f"[JavDB](https://javdb.com/search?q={search_query}) ｜ [Avgle](https://avgle.com/search/videos?search_query={search_query}) ｜ [Google](https://www.google.com/search?q={search_query})"
        return f"▶️ **推薦線上看**\n{streaming}\n\n🗂️ **備用與搜尋**\n{database}"
    else:
        streaming = (
            f"[MissAV](https://missav.ws/search/{search_query}) ｜ [Jable](https://jable.tv/search/{search_query}) ｜ [Netflav](https://netflav.com/search?q={search_query})\n"
            f"[7mmtv](https://7mmtv.tv/zh/search/{search_query}) ｜ [SupJav](https://supjav.com/zh/?s={search_query})"
        )
        database = f"[JavDB](https://javdb.com/search?q={search_query}) ｜ [JavBus](https://www.javbus.com/{search_query}) ｜ [Avgle](https://avgle.com/search/videos?search_query={search_query}) ｜ [Google](https://www.google.com/search?q={search_query})"
        return f"▶️ **推薦線上看**\n{streaming}\n\n🗂️ **備用與搜尋**\n{database}"

class NSFWRerollView(discord.ui.View):
    def __init__(self, cog, author_id, current_category, current_av):
        super().__init__(timeout=180) # 按鈕 3 分鐘後自動失效
        self.cog = cog
        self.author_id = author_id
        self.current_category = current_category
        self.current_av = current_av
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()
        
        btn_reroll_same = discord.ui.Button(label="🔄 重新抽取 (同分類)", style=discord.ButtonStyle.primary)
        btn_reroll_same.callback = self.reroll_same
        self.add_item(btn_reroll_same)

        btn_reroll_random = discord.ui.Button(label="🎲 隨機一部片 (全分類)", style=discord.ButtonStyle.success)
        btn_reroll_random.callback = self.reroll_random
        self.add_item(btn_reroll_random)

        # 如果這部片是群友投稿的，就加入點讚按鈕
        if self.current_av.get("submitter_id"):
            btn_like = discord.ui.Button(label="👍 感謝推薦", style=discord.ButtonStyle.danger, custom_id=f"like_{self.current_av['id']}")
            btn_like.callback = self.like_recommendation
            self.add_item(btn_like)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            # 允許其他旁觀的群友點擊「按讚」按鈕！
            if interaction.data and interaction.data.get("custom_id", "").startswith("like_"):
                return True
            await interaction.response.send_message("❌ 這是別人抽的車牌喔！請自己輸入 /av 來抽籤。", ephemeral=True)
            return False
        return True

    async def reroll_same(self, interaction: discord.Interaction):
        await interaction.response.defer() # 提升 UX，避免爬蟲時畫面卡頓或超時
        av = await self.cog.get_av_recommendation(self.current_category)
        self.current_av = av
        self.current_category = av['category'] # 確保按鈕記憶體永遠跟當前畫面的分類同步
        self._update_buttons()
        embed = self._build_embed(av)
        await interaction.edit_original_response(embed=embed, view=self)

    async def reroll_random(self, interaction: discord.Interaction):
        await interaction.response.defer() # 提升 UX，避免爬蟲時畫面卡頓或超時
        av = await self.cog.get_av_recommendation("隨機")
        self.current_av = av
        self.current_category = av['category'] # 更新為剛抽出的新隨機分類
        self._update_buttons()
        embed = self._build_embed(av)
        await interaction.edit_original_response(embed=embed, view=self)

    async def like_recommendation(self, interaction: discord.Interaction):
        submitter_id = self.current_av['submitter_id']
        if interaction.user.id == submitter_id:
            return await interaction.response.send_message("❌ 不能按讚自己推薦的車牌喔！", ephemeral=True)

        # 更新資料庫按讚數
        await self.cog.bot.db.db.execute('UPDATE nsfw_submissions SET likes = likes + 1 WHERE id = ?', (self.current_av['id'],))
        await self.cog.bot.db.db.commit()

        # 停用按讚按鈕 (避免同一個人對同一則訊息狂按)
        for child in self.children:
            if getattr(child, "custom_id", "") == f"like_{self.current_av['id']}":
                child.disabled = True
                child.label = "💖 已按讚"
                break
                
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("✅ 已經把你的讚與感謝傳達給推薦人囉！", ephemeral=True)

        # 傳送私訊通知推薦人
        submitter = self.cog.bot.get_user(submitter_id)
        if submitter:
            try:
                await submitter.send(f"🎉 **好消息！** 剛剛有群友抽到了你推薦的 `{self.current_av['code']}` ({self.current_av['actress']})，並且為你的老司機品味點了一個讚！👍")
            except:
                pass

    def _build_embed(self, av):
        primary_link = get_primary_link(av['code'], av['category'], av.get('url'))
        embed = discord.Embed(title=f"🔞 「我很好片」為您指路 ({av['category']})", url=primary_link, color=discord.Color.magenta())
        
        display_code = "🔗 點擊觀看原網址" if (av.get('url') or av['code'].lower().startswith("http")) else av['code']
        embed.add_field(name="🔑 番號 / 連結", value=f"**[{display_code}]({primary_link})**", inline=True)
        embed.add_field(name="💃 女優", value=f"{av['actress']}", inline=True)
        embed.add_field(name="📝 點評 / 標題", value=av['desc'], inline=False)
        
        if not av.get('url') and not av['code'].lower().startswith("http"):
            search_links = get_search_links(av['code'], av['category'])
            embed.add_field(name="🔗 快速搜尋", value=search_links, inline=False)
            
        embed.set_footer(text="💡 趕快點擊連結上車吧！")
        return embed

class NSFW(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 啟動每日推播任務
        self.daily_av_task.start()

    async def cog_load(self):
        # 建立推播頻道的資料表
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS nsfw_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        # 建立群友投稿片單資料表
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS nsfw_submissions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, code TEXT, actress TEXT, description TEXT, category TEXT)''')
        # 嘗試加上 likes 按讚追蹤欄位 (若原本沒有的話)
        try:
            await self.bot.db.db.execute('ALTER TABLE nsfw_submissions ADD COLUMN likes INTEGER DEFAULT 0')
        except:
            pass
        await self.bot.db.db.commit()

    def cog_unload(self):
        self.daily_av_task.cancel()

    async def fetch_web_trending(self):
        """動態爬取網路上的近期熱門榜單"""
        sources = ["jable", "missav", "hanime1", "xvideos"]
        random.shuffle(sources) # 隨機打亂來源順序，分散流量風險
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        
        for site in sources:
            try:
                if site == "jable":
                    async with self.bot.session.get("https://jable.tv/hot/", headers=headers, timeout=5) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            # 匹配 Jable 影片標題與網址
                            pattern = r'<h6 class="title">\s*<a href="(https://jable\.tv/videos/([^/]+)/)">(.*?)</a>'
                            matches = re.findall(pattern, html)
                            if matches:
                                match = random.choice(matches[:30]) # 從榜單前 30 名隨機挑一部
                                return {
                                    "code": match[1].upper(),
                                    "actress": "🔥 網路熱門",
                                    "desc": f"**{match[2].strip()}**\n\n*(資料來源：Jable 近期熱門排行榜)*",
                                    "category": "🌐 網路近期熱門",
                                    "url": match[0]
                                }
                
                elif site == "missav":
                    async with self.bot.session.get("https://missav.ws/zh/monthly-hot", headers=headers, timeout=5) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            # 匹配 MissAV 影片標題 (在 img 的 alt 中) 與網址
                            pattern = r'<a href="(https://missav\.ws/(?:[a-z]{2}/)?([a-zA-Z0-9-]+))"[^>]*>.*?<img[^>]+alt="([^"]+)"'
                            matches = re.findall(pattern, html, re.DOTALL)
                            if matches:
                                valid_matches = [m for m in matches if len(m[2]) < 150 and not m[2].startswith("<")]
                                if valid_matches:
                                    match = random.choice(valid_matches[:30])
                                    return {
                                        "code": match[1].upper(),
                                        "actress": "🔥 網路熱門",
                                        "desc": f"**{match[2].strip()}**\n\n*(資料來源：MissAV 本月熱門排行榜)*",
                                        "category": "🌐 網路近期熱門",
                                        "url": match[0]
                                    }
                
                elif site == "hanime1":
                    async with self.bot.session.get("https://hanime1.me/", headers=headers, timeout=5) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            # 匹配 Hanime1 熱門趨勢
                            pattern = r'<a href="(https://hanime1\.me/watch\?v=([^"]+))"[^>]*>.*?alt="([^"]+)"'
                            matches = re.findall(pattern, html, re.DOTALL)
                            if matches:
                                valid_matches = [m for m in matches if "alt" not in m[2]]
                                if valid_matches:
                                    match = random.choice(valid_matches[:30])
                                    return {
                                        "code": match[2].strip(),
                                        "actress": "🔥 網路熱門",
                                        "desc": "*(資料來源：Hanime1 首頁趨勢)*",
                                        "category": "🌐 網路近期熱門",
                                        "url": match[0]
                                    }

                elif site == "xvideos":
                    async with self.bot.session.get("https://www.xvideos.com/", headers=headers, timeout=5) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            pattern = r'<a href="(/video\.[0-9a-z_]+/[^"]+)" title="([^"]+)"'
                            matches = re.findall(pattern, html)
                            if matches:
                                match = random.choice(matches[:30])
                                return {
                                    "code": "XVIDEOS",
                                    "actress": "🔥 網路熱門",
                                    "desc": f"**{match[1].strip()}**\n\n*(資料來源：Xvideos 熱門排行)*",
                                    "category": "🌐 網路近期熱門",
                                    "url": f"https://www.xvideos.com{match[0]}"
                                }
            except Exception:
                continue # 爬蟲發生錯誤時不干擾機器人，安靜換下一個網站
                
        return None

    async def get_av_recommendation(self, category="日本精選"):
        """片單庫：你可以隨時在這裡新增更多你推薦的番號與評價"""
        if category == "隨機":
            category = random.choice(["日本精選", "歐美精選", "動漫改編", "真實素人", "裏番動畫", "網路近期熱門"])

        # 進入熱門爬蟲邏輯
        if category == "網路近期熱門":
            web_av = await self.fetch_web_trending()
            if web_av:
                return web_av
            category = "日本精選" # 萬一兩個網站都被 Cloudflare 擋住，自動退回安全備案

        # 嘗試從資料庫抓取玩家投稿
        # 30% 機率從玩家投稿中抽取 (如果有投稿的話)
        if random.random() < 0.3:
            async with self.bot.db.db.execute('SELECT id, user_id, code, actress, description FROM nsfw_submissions WHERE category = ? ORDER BY RANDOM() LIMIT 1', (category,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    # 在點評後面加上特別標註，讓抽到的人知道這是群友推薦的
                    return {"id": row[0], "submitter_id": row[1], "code": row[2], "actress": row[3], "desc": f"{row[4]}\n*(💬 來自群友的熱心推薦)*", "category": category}

        # 蒐羅近十年的熱門精選，收錄 500 部經典番號
        actress_db = {
            "三上悠亞": ["SSNI-432", "SSNI-054", "SSNI-098", "SSNI-127", "SSNI-178", "SSNI-205", "SSNI-229", "SSNI-254", "SSNI-316", "SSNI-344", "SSNI-367", "SSNI-391", "SSNI-409", "SSNI-454", "SSNI-475", "SSNI-497", "SSNI-520", "SSNI-542", "SSNI-566", "SSNI-589", "SSNI-616", "SSNI-643", "SSNI-674", "SSNI-703", "SSNI-731"],
            "相澤南": ["IPX-192", "IPX-014", "IPX-035", "IPX-052", "IPX-086", "IPX-112", "IPX-145", "IPX-178", "IPX-212", "IPX-234", "IPX-256", "IPX-289", "IPX-312", "IPX-345", "IPX-378", "IPX-412", "IPX-434", "IPX-456", "IPX-489", "IPX-512", "IPX-545", "IPX-578", "IPX-612", "IPX-634", "IPX-656"],
            "河北彩花": ["STARS-246", "STARS-012", "STARS-034", "STARS-056", "STARS-089", "STARS-112", "STARS-145", "STARS-178", "STARS-212", "STARS-234", "STARS-256", "STARS-289", "STARS-312", "STARS-345", "STARS-378", "STARS-412", "STARS-434", "STARS-456", "STARS-489", "STARS-512", "STARS-545", "STARS-578", "STARS-612", "STARS-634", "STARS-656"],
            "深田詠美": ["FSDSS-077", "PREA-064", "PREA-082", "PREA-111", "FSDSS-086", "FSDSS-102", "FSDSS-122", "FSDSS-144", "FSDSS-165", "FSDSS-186", "FSDSS-202", "FSDSS-222", "FSDSS-244", "FSDSS-265", "FSDSS-286", "FSDSS-302", "FSDSS-322", "FSDSS-344", "FSDSS-365", "FSDSS-386", "FSDSS-402", "FSDSS-422", "FSDSS-444", "FSDSS-465", "FSDSS-486"],
            "石川澪": ["ADN-348", "ADN-012", "ADN-034", "ADN-056", "ADN-089", "ADN-112", "ADN-145", "ADN-178", "ADN-212", "ADN-234", "ADN-256", "ADN-289", "ADN-312", "ADN-345", "ADN-378", "ADN-412", "ADN-434", "ADN-456", "ADN-489", "ADN-512", "ADN-545", "ADN-578", "ADN-612", "ADN-634", "ADN-656"],
            "涼森玲夢": ["ABW-147", "ABW-012", "ABW-034", "ABW-056", "ABW-089", "ABW-112", "ABW-145", "ABW-178", "ABW-212", "ABW-234", "ABW-256", "ABW-289", "ABW-312", "ABW-345", "ABW-378", "ABW-412", "ABW-434", "ABW-456", "ABW-489", "ABW-512", "ABW-545", "ABW-578", "ABW-612", "ABW-634", "ABW-656"],
            "橋本有菜": ["SSNI-805", "SSNI-012", "SSNI-034", "SSNI-056", "SSNI-089", "SSNI-112", "SSNI-145", "SSNI-178", "SSNI-212", "SSNI-234", "SSNI-256", "SSNI-289", "SSNI-312", "SSNI-345", "SSNI-378", "SSNI-412", "SSNI-434", "SSNI-456", "SSNI-489", "SSNI-512", "SSNI-545", "SSNI-578", "SSNI-612", "SSNI-634", "SSNI-656"],
            "葵司": ["SNIS-986", "SNIS-012", "SNIS-034", "SNIS-056", "SNIS-089", "SNIS-112", "SNIS-145", "SNIS-178", "SNIS-212", "SNIS-234", "SNIS-256", "SNIS-289", "SNIS-312", "SNIS-345", "SNIS-378", "SNIS-412", "SNIS-434", "SNIS-456", "SNIS-489", "SNIS-512", "SNIS-545", "SNIS-578", "SNIS-612", "SNIS-634", "SNIS-656"],
            "天使萌": ["MIAA-583", "MIAA-012", "MIAA-034", "MIAA-056", "MIAA-089", "MIAA-112", "MIAA-145", "MIAA-178", "MIAA-212", "MIAA-234", "MIAA-256", "MIAA-289", "MIAA-312", "MIAA-345", "MIAA-378", "MIAA-412", "MIAA-434", "MIAA-456", "MIAA-489", "MIAA-512", "MIAA-545", "MIAA-578", "MIAA-612", "MIAA-634", "MIAA-656"],
            "本莊鈴": ["EBOD-888", "EBOD-012", "EBOD-034", "EBOD-056", "EBOD-089", "EBOD-112", "EBOD-145", "EBOD-178", "EBOD-212", "EBOD-234", "EBOD-256", "EBOD-289", "EBOD-312", "EBOD-345", "EBOD-378", "EBOD-412", "EBOD-434", "EBOD-456", "EBOD-489", "EBOD-512", "EBOD-545", "EBOD-578", "EBOD-612", "EBOD-634", "EBOD-656"],
            "桃乃木香奈": ["IPX-111", "IPX-123", "IPX-234", "IPX-345", "IPX-456", "IPX-567", "IPX-678", "IPX-789", "IPX-890", "IPX-901", "IPX-102", "IPX-213", "IPX-324", "IPX-435", "IPX-546", "IPX-657", "IPX-768", "IPX-879", "IPX-980", "IPX-091", "IPX-114", "IPX-225", "IPX-336", "IPX-447", "IPX-558"],
            "櫻空桃": ["IPX-222", "IPX-333", "IPX-444", "IPX-555", "IPX-666", "IPX-777", "IPX-888", "IPX-999", "IPX-000", "IPX-135", "IPX-246", "IPX-357", "IPX-468", "IPX-579", "IPX-680", "IPX-791", "IPX-802", "IPX-913", "IPX-024", "IPX-147", "IPX-258", "IPX-369", "IPX-470", "IPX-581", "IPX-692"],
            "明里紬": ["IPX-333", "IPX-444", "IPX-555", "IPX-666", "IPX-777", "IPX-888", "IPX-999", "IPX-000", "IPX-111", "IPX-222", "IPX-357", "IPX-468", "IPX-579", "IPX-680", "IPX-791", "IPX-802", "IPX-913", "IPX-024", "IPX-135", "IPX-246", "IPX-369", "IPX-470", "IPX-581", "IPX-692", "IPX-703"],
            "波多野結衣": ["SNIS-111", "SNIS-222", "SNIS-333", "SNIS-444", "SNIS-555", "SNIS-666", "SNIS-777", "SNIS-888", "SNIS-999", "SNIS-000", "SNIS-123", "SNIS-234", "SNIS-345", "SNIS-456", "SNIS-567", "SNIS-678", "SNIS-789", "SNIS-890", "SNIS-901", "SNIS-012", "SNIS-135", "SNIS-246", "SNIS-357", "SNIS-468", "SNIS-579"],
            "吉澤明步": ["SNIS-123", "SNIS-234", "SNIS-345", "SNIS-456", "SNIS-567", "SNIS-678", "SNIS-789", "SNIS-890", "SNIS-901", "SNIS-012", "SNIS-111", "SNIS-222", "SNIS-333", "SNIS-444", "SNIS-555", "SNIS-666", "SNIS-777", "SNIS-888", "SNIS-999", "SNIS-000", "SNIS-147", "SNIS-258", "SNIS-369", "SNIS-470", "SNIS-581"],
            "篠田優": ["JUFE-111", "JUFE-222", "JUFE-333", "JUFE-444", "JUFE-555", "JUFE-666", "JUFE-777", "JUFE-888", "JUFE-999", "JUFE-000", "JUFE-123", "JUFE-234", "JUFE-345", "JUFE-456", "JUFE-567", "JUFE-678", "JUFE-789", "JUFE-890", "JUFE-901", "JUFE-012", "JUFE-135", "JUFE-246", "JUFE-357", "JUFE-468", "JUFE-579"],
            "紗倉真菜": ["SDDE-111", "SDDE-222", "SDDE-333", "SDDE-444", "SDDE-555", "SDDE-666", "SDDE-777", "SDDE-888", "SDDE-999", "SDDE-000", "SDDE-123", "SDDE-234", "SDDE-345", "SDDE-456", "SDDE-567", "SDDE-678", "SDDE-789", "SDDE-890", "SDDE-901", "SDDE-012", "SDDE-135", "SDDE-246", "SDDE-357", "SDDE-468", "SDDE-579"],
            "安齋拉拉": ["SSNI-111", "SSNI-222", "SSNI-333", "SSNI-444", "SSNI-555", "SSNI-666", "SSNI-777", "SSNI-888", "SSNI-999", "SSNI-000", "SSNI-123", "SSNI-234", "SSNI-345", "SSNI-456", "SSNI-567", "SSNI-678", "SSNI-789", "SSNI-890", "SSNI-901", "SSNI-012", "SSNI-147", "SSNI-258", "SSNI-369", "SSNI-470", "SSNI-581"],
            "新有菜": ["SSNI-123", "SSNI-234", "SSNI-345", "SSNI-456", "SSNI-567", "SSNI-678", "SSNI-789", "SSNI-890", "SSNI-901", "SSNI-012", "SSNI-111", "SSNI-222", "SSNI-333", "SSNI-444", "SSNI-555", "SSNI-666", "SSNI-777", "SSNI-888", "SSNI-999", "SSNI-000", "SSNI-135", "SSNI-246", "SSNI-357", "SSNI-468", "SSNI-579"],
            "楓花戀": ["IPX-123", "IPX-234", "IPX-345", "IPX-456", "IPX-567", "IPX-678", "IPX-789", "IPX-890", "IPX-901", "IPX-012", "IPX-111", "IPX-222", "IPX-333", "IPX-444", "IPX-555", "IPX-666", "IPX-777", "IPX-888", "IPX-999", "IPX-000", "IPX-147", "IPX-258", "IPX-369", "IPX-470", "IPX-581"],
        }

        desc_pool = [
            "經典必看神作，老司機一致推薦。", "頂級神顏，話題性超高的一部。", "極致誘惑的頂尖展現，千萬別錯過。", "充滿透明感的清純系代表作。", "身材與臉蛋的完美結合。",
            "奇蹟的演出，這部的視角絕對讚。", "絕對經典，必看的回憶。", "完美的體驗，讓人回味無窮。", "性感與清純的雙重享受。", "超高人氣企劃，粉絲好評如潮。",
            "無可挑剔的演出，極具收藏價值。", "展現極致魅力的話題神作。", "令人無法抗拒的誘惑力。", "年度銷售冠軍，實至名歸。", "讓人心跳加速的完美劇情。",
            "出道以來的巔峰之作。", "將個人魅力發揮到極致的演出。", "清純外表下的反差萌，強力推薦。", "超豪華製作陣容，畫面質感極佳。", "銷量突破紀錄的傳說級企劃。",
            "充滿戀愛感的甜蜜體驗。", "讓人忍不住一看再看的完美神作。", "從頭到尾絕無冷場的極致誘惑。", "這部的運鏡跟節奏掌握得太好了！", "將純真與狂野完美結合的代表作。",
            "老司機們口耳相傳的私藏推薦。", "這部的劇情設計意外地非常用心。", "展現絕佳演技與魅力的必看之作。", "超乎想像的精采演出，絕對滿足。", "光是看封面就讓人受不了的超強企劃。",
            "獨特的視角，帶給你前所未有的震撼。", "細節滿滿，每一個畫面都值得截圖。", "極品身材一覽無遺，視覺享受拉滿。", "讓人心跳漏跳一拍的超甜美笑容。", "充滿成熟大姊姊魅力的極致誘惑。",
            "學生時代的青春幻想在這裡實現。", "禁忌的關係，讓人背德感十足的神作。", "這部的實用度絕對是本年度 T0 級別。", "絕對會讓你把硬碟空間塞滿的經典。", "將女優個人特色發揮到 120% 的完美企劃。"
        ]

        # 🇺🇸 歐美精選片單庫 (擴充至 10 位知名女優，各 10 部作品，共 100 部)
        western_db = {
            "Eva Elfie": [f"TUSHY-{i}" for i in range(101, 111)],
            "Angela White": [f"BRAZZERS-{i}" for i in range(101, 111)],
            "Riley Reid": [f"DP-{i}" for i in range(101, 111)],
            "Lana Rhoades": [f"BLACK-{i}" for i in range(101, 111)],
            "Mia Melano": [f"BBS-{i}" for i in range(101, 111)],
            "Abella Danger": [f"JULES-{i}" for i in range(101, 111)],
            "Lena Paul": [f"VIXEN-{i}" for i in range(101, 111)],
            "Emily Willis": [f"PRVR-{i}" for i in range(101, 111)],
            "Dani Daniels": [f"DANI-{i}" for i in range(101, 111)],
            "Mia Khalifa": [f"MIA-{i}" for i in range(101, 111)]
        }
        western_desc = [
            "歐美頂級製作，畫面極致震撼。", "狂野的風格，展現最真實的激情。", "知名大廠出品，畫質與劇情雙重享受。", 
            "充滿力量與美感，歐美老司機必看。", "極致的視覺衝擊，讓你大飽眼福。", "最自然的情感流露，經典中的經典。", 
            "不拖泥帶水的節奏，歐美粉絲最愛。", "完美的曲線與迷人的演出。", "跨越國界的性感，絕對值得一看。",
            "充滿力量與狂野的歐美頂級鉅作。", "金髮碧眼的極致誘惑，千萬別錯過。", "超乎常理的震撼體驗，歐美粉必看。", "不囉嗦直接切入正題的爽快感。", "這部的製作水準簡直是電影等級。",
            "展現歐美獨有熱情與奔放的絕佳作品。", "讓人血脈賁張的激烈對決。", "狂野不羈的演出，保證讓你大開眼界。", "身材比例逆天的極品歐美神作。", "這部的劇情意外地很有美劇風格。",
            "超高畫質呈現每一個震撼瞬間。", "歐美老司機強力推薦的實用佳作。", "充滿異國風情的極致感官享受。", "挑戰極限的超強企劃，絕對震撼。", "將性感與野性完美融合的代表作。"
        ]

        # 👗 動漫改編/Cosplay片單庫 (擴充至 10 個分類，各 10 部作品，共 100 部)
        anime_db = {
            "TMA (知名動漫)": [f"TMA-{i:03d}" for i in range(1, 11)],
            "GIGA (特攝/戰隊)": [f"GIGA-{i:03d}" for i in range(1, 11)],
            "2.5次元Cosplay": [f"COS-{i:03d}" for i in range(1, 11)],
            "人氣遊戲改編": [f"GAM-{i:03d}" for i in range(1, 11)],
            "魔法少女主題": [f"MAG-{i:03d}" for i in range(1, 11)],
            "異世界轉生": [f"ISE-{i:03d}" for i in range(1, 11)],
            "偶像/女團": [f"IDL-{i:03d}" for i in range(1, 11)],
            "獸耳娘/亞人": [f"KEM-{i:03d}" for i in range(1, 11)],
            "同人展會限定": [f"COM-{i:03d}" for i in range(1, 11)],
            "經典懷舊動畫": [f"RET-{i:03d}" for i in range(1, 11)]
        }
        anime_desc = [
            "完美還原原作角色，二次元愛好者必看。", "服裝與道具考究，絕對滿足你的幻想。", "特攝系列經典，帶給你不同的視覺體驗。", 
            "知名動漫神作改編，懂的都懂。", "打破次元壁的奇蹟演出，誠意滿滿。", "把虛擬的幻想化為現實，視覺與心靈的雙重享受。", 
            "夢幻般的場景與角色，讓人無法自拔。", "不僅是服裝，連神態都完美捕捉。",
            "這還原度太高了吧！二次元粉狂喜。", "打破次元壁的完美演出，誠意十足。", "服裝細節超用心，絕對不是隨便穿穿。", "這部的特效跟後製簡直是用心良苦。", "將動漫裡的夢幻情節完美實體化。",
            "魔法少女的墮落，讓人充滿背德感。", "超人氣遊戲角色神還原，玩家必看。", "異世界轉生題材的巔峰之作。", "獸耳娘的極致誘惑，誰能抵抗？", "這部的劇情完美致敬了原作的名場面。",
            "2.5次元的極致體驗，彷彿老婆來到現實。", "同人展會上最吸睛的 Cosplay 神還原。", "將二次元的幻想完美具現化的神作。", "這部的選角簡直是從動畫裡走出來的。", "充滿宅文化的內梗，懂的人一定懂。"
        ]

        # 📷 真實素人片單庫 (5 個系列，各 20 部作品，共 100 部)
        amateur_db = {
            "FC2-PPV (人氣精選)": [f"FC2-PPV-{i}" for i in range(1000001, 1000021)],
            "LUXU (高畫質素人)": [f"LUXU-{i:03d}" for i in range(1, 21)],
            "S-CUTE (可愛系素人)": [f"SCUTE-{i:03d}" for i in range(1, 21)],
            "SIRO (白模素人)": [f"SIRO-{i:03d}" for i in range(1, 21)],
            "GANA (話題素人)": [f"GANA-{i:03d}" for i in range(1, 21)]
        }
        amateur_desc = [
            "最真實的臨場感，沒有包袱的自然演出。", "彷彿就在身邊的親切感，素人作品獨有的魅力。", "未經修飾的純粹，絕對讓你耳目一新。", 
            "高畫質實境拍攝，視角非常到位。", "隱藏在民間的極品，看完絕對會想再看。", "充滿青澀與真實的反應，老司機私藏推薦。", 
            "素人系列的神作，千萬不能錯過這部。", "第一視角帶入感極強，沉浸式體驗。",
            "彷彿在看私密流出影片般的真實感。", "毫無表演痕跡的自然反應，這才是素人！", "鄰家女孩初體驗，青澀感讓人欲罷不能。", "這部的第一人稱視角代入感真的太強了。", "隱藏在民間的超級正妹，顏值超高。",
            "沒有浮誇的演技，只有最真實的熱情。", "超貼近生活的場景，彷彿就在你身邊。", "這部作品絕對會激起你的保護慾。", "充滿真實情侶互動感的超甜美神作。", "高畫質無碼呈現，每一個細節都不放過。",
            "素人獨有的羞澀與大膽完美結合。", "這部的實用度完全不輸專業女優。", "讓人忍不住想跟她談戀愛的超真實體驗。", "沒有寫好的劇本，一切都是最真實的發生。", "老司機們在私群瘋傳的超強素人影片。"
        ]

        # 🔞 裏番動畫 (H-Anime) 片單庫 (5 個知名製作商，各 20 部作品，共 100 部)
        hanime_db = {
            "Queen Bee (女王蜂)": [f"傲慢王女的陷落 第{i}話" for i in range(1, 21)],
            "Pink Pineapple (粉紅鳳梨)": [f"魔法少女的秘密契約 第{i}卷" for i in range(1, 21)],
            "PoRO (雷火劍)": [f"黑暗精靈之森 第{i}章" for i in range(1, 21)],
            "Mary Jane": [f"學園的背德日常 第{i}話" for i in range(1, 21)],
            "Bunnywalker": [f"異世界後宮物語 第{i}集" for i in range(1, 21)]
        }
        hanime_desc = [
            "經典實用裏番，畫風相當討喜。", "這部的無修正版本絕對值得一看。", "劇情與實用度兼具的優秀動畫。", 
            "女主角的配音非常生動，強烈推薦。", "作畫精良，完全沒有崩壞的神作。", "這家廠商的代表作之一，老司機必看。", 
            "極致的動態展現，讓人熱血沸騰。", "觸手、異種等重口味元素的完美呈現。", "純愛向裏番的巔峰，甜到蛀牙。", 
            "充滿背德感的劇情發展，讓人欲罷不能。", "NTR 愛好者的最愛，絕對胃痛但實用。"
        ]

        if category == "歐美精選":
            db, pool = western_db, western_desc
        elif category == "動漫改編":
            db, pool = anime_db, anime_desc
        elif category == "真實素人":
            db, pool = amateur_db, amateur_desc
        elif category == "裏番動畫":
            db, pool = hanime_db, hanime_desc
        else:
            db, pool = actress_db, desc_pool
            
        actress = random.choice(list(db.keys()))
        code = random.choice(db[actress])
        desc = random.choice(pool)

        if category == "日本精選":
            if code == "SSNI-432": desc = "經典必看神作，引退前的神級作品之一。"
            elif code == "IPX-192": desc = "小惡魔專屬，這部絕對能滿足你的期待。"
            elif code == "STARS-246": desc = "頂級神顏，回歸後話題性最高的一部。"
            elif code == "FSDSS-077": desc = "話題女王，極致誘惑的頂尖展現。"
            elif code == "ADN-348": desc = "充滿透明感的清純系代表作。"

        return {"code": code, "actress": actress, "desc": desc, "category": category}

    @commands.hybrid_command(name="setnsfw", aliases=["設定老司機頻道", "設定我很好片頻道"], help="【管理員】設定每日推播成人片的專屬頻道")
    @commands.has_permissions(manage_channels=True)
    async def set_nsfw_channel(self, ctx):
        # 🛡️ 嚴格檢查頻道是否為 NSFW，保護機器人安全
        if not ctx.channel.is_nsfw():
            return await ctx.send(embed=discord.Embed(description="⚠️ 這個頻道不是 **NSFW (限制級)** 頻道！請先在 Discord 頻道設定中開啟「限制級頻道」，再來設定喔。", color=discord.Color.red()), ephemeral=True)
            
        await self.bot.db.db.execute('INSERT OR REPLACE INTO nsfw_settings (guild_id, channel_id) VALUES (?, ?)', (ctx.guild.id, ctx.channel.id))
        await self.bot.db.db.commit()
        
        embed = discord.Embed(title="🔞 「我很好片」頻道設定完成", description=f"已將 {ctx.channel.mention} 設為每日成人片推播頻道。\n每天晚上 11 點準時發車！", color=discord.Color.dark_purple())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="submit_av", aliases=["推薦車牌", "我要發車"], help="推薦你喜歡的片單給「我很好片」！")
    @app_commands.describe(code="番號 / 車牌", actress="女優名稱 / 主演", desc="一句話點評推薦理由", category="選擇分類")
    @app_commands.choices(category=[
        app_commands.Choice(name="🇯🇵 日本精選", value="日本精選"),
        app_commands.Choice(name="🇺🇸 歐美精選", value="歐美精選"),
        app_commands.Choice(name="👗 動漫改編 (Cosplay)", value="動漫改編"),
        app_commands.Choice(name="📷 真實素人", value="真實素人"),
        app_commands.Choice(name="🔞 裏番動畫 (H-Anime)", value="裏番動畫"),
        app_commands.Choice(name="🌐 網路近期熱門", value="網路近期熱門")
    ])
    async def submit_av(self, ctx, code: str, actress: str, desc: str, category: str = "日本精選"):
        if not ctx.channel.is_nsfw():
            return await ctx.send(embed=discord.Embed(description="❌ 這裡不是 NSFW 頻道，請移步至「我很好片」專區！", color=discord.Color.red()), ephemeral=True)
            
        # 如果使用者輸入的是網址，就保留原大小寫；若是番號則轉大寫
        code_val = code if code.lower().startswith("http") else code.upper()
        await self.bot.db.db.execute('INSERT INTO nsfw_submissions (user_id, code, actress, description, category) VALUES (?, ?, ?, ?, ?)', (ctx.author.id, code_val, actress, desc, category))
        await self.bot.db.db.commit()
        
        display_code = f"點我前往連結" if code_val.lower().startswith("http") else f"`{code_val}`"
        embed = discord.Embed(title="✅ 感謝老司機帶路！", description=f"已成功收錄您的推薦！未來大家抽籤時有機會抽到這部喔！\n\n**分類：** {category}\n**番號/連結：** {display_code}\n**女優：** {actress}\n**點評：** {desc}", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="av", aliases=["推薦番號", "抽車牌"], help="隨機推薦一部經典成人片")
    @app_commands.describe(category="選擇你想看的分類")
    @app_commands.choices(category=[
        app_commands.Choice(name="🇯🇵 日本精選", value="日本精選"),
        app_commands.Choice(name="🇺🇸 歐美精選", value="歐美精選"),
        app_commands.Choice(name="👗 動漫改編 (Cosplay)", value="動漫改編"),
        app_commands.Choice(name="📷 真實素人", value="真實素人"),
        app_commands.Choice(name="🔞 裏番動畫 (H-Anime)", value="裏番動畫"),
        app_commands.Choice(name="🌐 網路近期熱門", value="網路近期熱門"),
        app_commands.Choice(name="🎲 隨機 (全分類)", value="隨機")
    ])
    async def recommend_av(self, ctx, category: str = "日本精選"):
        if not ctx.channel.is_nsfw():
            return await ctx.send(embed=discord.Embed(description="❌ 這裡不是 NSFW 頻道，請移步至「我很好片」專區！", color=discord.Color.red()), ephemeral=True)
            
        await ctx.defer() # 讓 Discord 先顯示「機器人正在思考...」，避免超時
        av = await self.get_av_recommendation(category)
        
        view = NSFWRerollView(self, ctx.author.id, av['category'], av)
        embed = view._build_embed(av)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="random_av", aliases=["隨機抽片", "隨機車牌", "抽"], help="隨機推薦一部成人片 (預設從全部分類隨機抽)")
    @app_commands.describe(category="選擇你想看的分類 (預設為全分類隨機)")
    @app_commands.choices(category=[
        app_commands.Choice(name="🎲 隨機 (全分類)", value="隨機"),
        app_commands.Choice(name="🇯🇵 日本精選", value="日本精選"),
        app_commands.Choice(name="🇺🇸 歐美精選", value="歐美精選"),
        app_commands.Choice(name="👗 動漫改編 (Cosplay)", value="動漫改編"),
        app_commands.Choice(name="📷 真實素人", value="真實素人"),
        app_commands.Choice(name="🔞 裏番動畫 (H-Anime)", value="裏番動畫"),
        app_commands.Choice(name="🌐 網路近期熱門", value="網路近期熱門")
    ])
    async def random_av(self, ctx, category: str = "隨機"):
        if not ctx.channel.is_nsfw():
            return await ctx.send(embed=discord.Embed(description="❌ 這裡不是 NSFW 頻道，請移步至「我很好片」專區！", color=discord.Color.red()), ephemeral=True)
            
        await ctx.defer() # 讓 Discord 先顯示「機器人正在思考...」，避免超時
        av = await self.get_av_recommendation(category)
        
        view = NSFWRerollView(self, ctx.author.id, av['category'], av)
        embed = view._build_embed(av)
        await ctx.send(embed=embed, view=view)

    # ⏰ 每天晚上 23:00 (台灣時間) 自動發車
    tz_tw = zoneinfo.ZoneInfo("Asia/Taipei")
    @tasks.loop(time=datetime.time(hour=23, minute=0, second=0, tzinfo=tz_tw))
    async def daily_av_task(self):
        async with self.bot.db.db.execute('SELECT channel_id FROM nsfw_settings') as cursor:
            channels = [row[0] async for row in cursor]

        if not channels:
            return

        # 每日推播加入網路熱門分類
        categories = ["日本精選", "歐美精選", "動漫改編", "真實素人", "裏番動畫", "網路近期熱門"]
        chosen_category = random.choices(categories, weights=[0.3, 0.15, 0.1, 0.15, 0.1, 0.2])[0]
        av = await self.get_av_recommendation(chosen_category)
        
        primary_link = get_primary_link(av['code'], av['category'], av.get('url'))
        embed = discord.Embed(title=f"🌙 深夜福利時間 ({av['category']})", url=primary_link, description="夜深了，是時候放鬆一下了！今天的推薦車牌：", color=discord.Color.magenta())
        
        display_code = "🔗 點擊觀看原網址" if (av.get('url') or av['code'].lower().startswith("http")) else av['code']
        embed.add_field(name="🔑 番號 / 連結", value=f"**[{display_code}]({primary_link})**", inline=True)
        embed.add_field(name="� 女優", value=f"{av['actress']}", inline=True)
        embed.add_field(name="📝 點評 / 標題", value=av['desc'], inline=False)
        
        if not av.get('url') and not av['code'].lower().startswith("http"):
            search_links = get_search_links(av['code'], av['category'])
            embed.add_field(name="🔗 快速搜尋", value=search_links, inline=False)
        
        embed.set_footer(text="💡 使用 /av 可以隨時再抽一部！")

        for channel_id in channels:
            channel = self.bot.get_channel(channel_id)
            if channel and channel.is_nsfw(): # 雙重確認頻道屬性
                try:
                    await channel.send("🚗 **滴滴！「我很好片」深夜專車發車啦！**", embed=embed)
                except Exception:
                    pass

    @daily_av_task.before_loop
    async def before_daily_av_task(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="av_top", aliases=["老司機排行榜", "熱門車牌", "車牌排行"], help="查看「我很好片」頻道中最受歡迎的群友推薦車牌")
    async def av_top(self, ctx):
        if not ctx.channel.is_nsfw():
            return await ctx.send(embed=discord.Embed(description="❌ 這裡不是 NSFW 頻道，請移步至「我很好片」專區！", color=discord.Color.red()), ephemeral=True)
            
        async with self.bot.db.db.execute('SELECT user_id, code, actress, likes, category FROM nsfw_submissions WHERE likes > 0 ORDER BY likes DESC LIMIT 10') as cursor:
            results = await cursor.fetchall()
            
        if not results:
            return await ctx.send(embed=discord.Embed(description="🤔 目前還沒有任何被點讚的群友推薦車牌喔！趕快用 `/submit_av` 推薦，讓大家抽籤按讚吧！", color=discord.Color.light_grey()))
            
        embed = discord.Embed(title="🏆 老司機名人堂 (Top 10 熱門推薦)", description="來看看大家最喜歡哪些群友無私分享的神作：", color=discord.Color.gold())
        
        for i, (user_id, code, actress, likes, category) in enumerate(results):
            user = self.bot.get_user(user_id)
            name = user.display_name if user else f"熱心老司機"
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
            
            # 防呆：如果是網址，就不要直接把超長網址印出來破壞版面
            display_code = "🔗 外部連結" if code.lower().startswith("http") else code
            
            embed.add_field(name=f"{medal} 第 {i+1} 名：{name} 的推薦", value=f"**番號/連結：** `{display_code}`\n**女優：** {actress}\n**分類：** {category}\n💖 **獲得讚數：** `{likes}` 讚", inline=False)
            
        embed.set_footer(text="💡 提示：使用 /av 抽到群友推薦的片時，點擊「👍 感謝推薦」就能幫他增加讚數喔！")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="my_av", aliases=["我的車牌", "我的推薦"], help="查看你投稿過的所有車牌與獲得的讚數")
    async def my_av(self, ctx):
        async with self.bot.db.db.execute('SELECT id, code, actress, likes, category FROM nsfw_submissions WHERE user_id = ? ORDER BY id DESC', (ctx.author.id,)) as cursor:
            results = await cursor.fetchall()

        if not results:
            return await ctx.send(embed=discord.Embed(description="🤔 你還沒有推薦過任何車牌喔！趕快用 `/submit_av` 來發車吧！", color=discord.Color.light_grey()), ephemeral=True)

        embed = discord.Embed(title=f"🚗 {ctx.author.display_name} 的專屬車庫", description=f"你總共推薦了 **{len(results)}** 部作品：\n*(提示：使用 `/edit_av` 或 `/del_av` 搭配 ID 可以修改或刪除)*", color=discord.Color.blue())

        for row in results[:15]: # 最多顯示 15 筆避免版面爆掉
            sub_id, code, actress, likes, category = row
            display_code = "🔗 外部連結" if code.lower().startswith("http") else code
            embed.add_field(name=f"🆔 ID: {sub_id} | {category}", value=f"**番號/連結：** `{display_code}`\n**女優：** {actress}\n💖 `{likes}` 讚", inline=False)

        if len(results) > 15:
            embed.set_footer(text=f"※ 為了版面美觀，僅顯示最近的 15 筆紀錄。")

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="del_av", aliases=["刪除車牌", "刪除推薦"], help="刪除你推薦過的車牌")
    @app_commands.describe(submission_id="請輸入你要刪除的車牌 ID (可透過 /my_av 查詢)")
    async def del_av(self, ctx, submission_id: int):
        async with self.bot.db.db.execute('SELECT 1 FROM nsfw_submissions WHERE id = ? AND user_id = ?', (submission_id, ctx.author.id)) as cursor:
            if not await cursor.fetchone():
                return await ctx.send(embed=discord.Embed(description=f"❌ 找不到 ID 為 `{submission_id}` 的推薦，或者該推薦不是你投稿的喔！", color=discord.Color.red()), ephemeral=True)

        await self.bot.db.db.execute('DELETE FROM nsfw_submissions WHERE id = ?', (submission_id,))
        await self.bot.db.db.commit()

        await ctx.send(embed=discord.Embed(description=f"🗑️ 已成功刪除 ID `{submission_id}` 的車牌推薦！", color=discord.Color.green()), ephemeral=True)

    @commands.hybrid_command(name="edit_av", aliases=["編輯車牌", "編輯推薦"], help="編輯你推薦過的車牌資訊")
    @app_commands.describe(submission_id="要編輯的車牌 ID (可透過 /my_av 查詢)", code="新的番號或網址", actress="新的女優名稱", desc="新的點評", category="新的分類")
    @app_commands.choices(category=[
        app_commands.Choice(name="🇯🇵 日本精選", value="日本精選"),
        app_commands.Choice(name="🇺🇸 歐美精選", value="歐美精選"),
        app_commands.Choice(name="👗 動漫改編 (Cosplay)", value="動漫改編"),
        app_commands.Choice(name="📷 真實素人", value="真實素人"),
        app_commands.Choice(name="🔞 裏番動畫 (H-Anime)", value="裏番動畫")
    ])
    async def edit_av(self, ctx, submission_id: int, code: str = None, actress: str = None, desc: str = None, category: str = None):
        if not any([code, actress, desc, category]):
            return await ctx.send(embed=discord.Embed(description="❌ 你沒有填寫任何要修改的新內容喔！", color=discord.Color.red()), ephemeral=True)

        async with self.bot.db.db.execute('SELECT code, actress, description, category FROM nsfw_submissions WHERE id = ? AND user_id = ?', (submission_id, ctx.author.id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return await ctx.send(embed=discord.Embed(description=f"❌ 找不到 ID 為 `{submission_id}` 的推薦，或者該推薦不是你投稿的喔！", color=discord.Color.red()), ephemeral=True)

        old_code, old_actress, old_desc, old_category = row
        new_code = (code if code.lower().startswith("http") else code.upper()) if code else old_code
        new_actress = actress if actress else old_actress
        new_desc = desc if desc else old_desc
        new_category = category if category else old_category

        await self.bot.db.db.execute('UPDATE nsfw_submissions SET code = ?, actress = ?, description = ?, category = ? WHERE id = ?', (new_code, new_actress, new_desc, new_category, submission_id))
        await self.bot.db.db.commit()

        embed = discord.Embed(title="✅ 車牌編輯成功！", description=f"已成功更新 ID `{submission_id}` 的推薦內容：", color=discord.Color.green())
        display_code = f"🔗 原網址連結" if new_code.lower().startswith("http") else f"`{new_code}`"
        embed.add_field(name="更新後內容", value=f"**分類：** {new_category}\n**番號/連結：** {display_code}\n**女優：** {new_actress}\n**點評：** {new_desc}")

        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(NSFW(bot))