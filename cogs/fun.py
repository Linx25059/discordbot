import discord
from discord import app_commands
from discord.ext import commands
import random
from typing import Literal

# 📊 建立一個專屬的「投票面板 UI」類別
class PollView(discord.ui.View):
    def __init__(self, question, options, author_name):
        # timeout=None 代表按鈕不會因為時間過久而失效
        super().__init__(timeout=None)
        self.question = question
        self.options = options
        self.author_name = author_name
        
        # 用來記錄投票狀況：字典的 key 是選項，value 是投給該選項的「使用者 ID 集合 (Set)」
        self.votes = {opt: set() for opt in options}

        # 根據選項數量，動態生成按鈕
        for i, opt in enumerate(options):
            # 建立按鈕 (style=Primary 是藍色按鈕)
            btn = discord.ui.Button(label=opt, style=discord.ButtonStyle.primary, custom_id=f"poll_btn_{i}")
            # 綁定按下按鈕時觸發的事件
            btn.callback = self.make_callback(opt)
            self.add_item(btn)

    # 建立按鈕被按下時的專屬反應
    def make_callback(self, option):
        async def callback(interaction: discord.Interaction):
            user_id = interaction.user.id
            
            # 先把該使用者從「所有選項」的投票紀錄中移除 (允許使用者改票)
            for opt in self.votes:
                self.votes[opt].discard(user_id)
            
            # 再把他加入到他剛剛點擊的「新選項」中
            self.votes[option].add(user_id)

            # 更新面板內容並回傳給 Discord
            await interaction.response.edit_message(embed=self.build_embed())
        return callback

    # 用來產生包含「進度條」的精美投票面板
    def build_embed(self):
        total_votes = sum(len(users) for users in self.votes.values())
        description = ""
        
        for opt, users in self.votes.items():
            count = len(users)
            # 計算百分比
            percentage = (count / total_votes * 100) if total_votes > 0 else 0
            
            # 製作簡易進度條 (█ 與 ░)
            bar_length = 15
            filled = int((percentage / 100) * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            description += f"**{opt}** \n`{bar}` {count} 票 ({percentage:.1f}%)\n\n"

        embed = discord.Embed(title=f"📊 投票：{self.question}", description=description, color=discord.Color.green())
        embed.set_footer(text=f"由 {self.author_name} 發起 • 目前共 {total_votes} 人投票")
        return embed

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="dice", aliases=["骰子"], help="擲一顆 6 面骰")
    async def roll_dice(self, ctx):
        result = random.randint(1, 6)
        await ctx.send(f"🎲 {ctx.author.mention} 擲出了 **{result}** 點！")

    @commands.hybrid_command(name="coin", aliases=["硬幣"], help="丟一枚硬幣")
    async def flip_coin(self, ctx):
        result = random.choice(["正面", "反面"])
        await ctx.send(f"🪙 硬幣掉下來了... 是 **{result}**！")

    # 📊 進階按鈕版投票系統
    @commands.hybrid_command(name="poll", aliases=["投票"], help="發起投票 (選項間請用 | 隔開)")
    async def poll(self, ctx, *, input_string: str):
        if ctx.interaction is None:
            await ctx.message.delete()
        
        parts = [p.strip() for p in input_string.split("|")]
        question = parts[0]
        options = parts[1:]

        # 如果沒有輸入選項，就預設給他「同意」跟「反對」兩個按鈕
        if not options:
            options = ["同意 👍", "反對 👎"]

        # 防呆機制：Discord 按鈕一個 View 最多只能塞 25 個
        if len(options) > 15:
            await ctx.send("❌ 選項太多啦！最多只能設定 15 個喔！", delete_after=5.0)
            return

        view = PollView(question, options, ctx.author.display_name)
        
        await ctx.send(embed=view.build_embed(), view=view)

    @commands.hybrid_command(name="eat", aliases=["吃什麼", "吃啥", "food"], help="不知道吃什麼？我幫你選！")
    @app_commands.describe(category="想找哪一餐的美食？ (可不填，隨機推薦)")
    @app_commands.choices(category=[
        app_commands.Choice(name="🥞 早餐", value="早餐"),
        app_commands.Choice(name="🍱 午餐", value="午餐"),
        app_commands.Choice(name="🥩 晚餐", value="晚餐"),
        app_commands.Choice(name="🍢 宵夜", value="宵夜")
    ])
    async def what_to_eat(self, ctx, category: str = None):
        # 建立詳細的美食字典
        food_menu = {
            "早餐": [
                "古早味蛋餅 🍳", "鐵板麵加蛋 🍝", "燒餅油條 🥖", "傳統大飯糰 🍙", "肉蛋吐司 🥪", 
                "蘿蔔糕加蛋 🥞", "小籠湯包 🥟", "皮蛋瘦肉粥 🥣", "總匯三明治 🥪", "大麵羹 🍜", 
                "炒麵配豬血湯 🥣", "卡拉雞腿堡 🍔", "巧克力吐司 🍫", "鍋貼配豆漿 🥟", "水煎包 🥙", 
                "鹹豆漿 🥛", "果醬貝果 🥯", "法式吐司 🍞", "漢堡排吐司 🥪", "薯餅塔 🥔", 
                "熱狗捲 🌭", "鮪魚蛋餅 🐟", "香雞排饅頭 🥪", "起司牛角 🥐", "清蒸肉圓 🥟", 
                "麵線糊 🍜", "蔬菜捲餅 🥙", "燕麥優格 🥛", "玉米濃湯配吐司 🥣", "台式飯糰加辣 🍙", 
                "花生醬培根堡 🥓", "厚片奶酥 🍞", "雞塊配奶茶 🍗", "碗粿 🍮", "虱目魚粥 🐟", 
                "鼎邊趖 🍜", "煎餃 🥟", "蔥抓餅加蛋 🍳", "里肌豬排蛋餅 🥩", "麥當勞滿福堡 🍔", 
                "超商御飯糰 🍙", "割包 🍔", "香菇肉粥 🥣", "油飯 🍚", "生菜沙拉 🥗", 
                "草莓果醬吐司 🍓", "熱壓吐司 🥪", "培根蛋餅 🥓", "燒肉蛋堡 🍔", "德式香腸堡 🌭"
            ],
            "午餐": [
                "炸雞腿便當 🍗", "滷排骨飯 🍱", "焢肉飯 🥓", "乾麵配貢丸湯 🍜", "鍋貼與水餃 🥟", 
                "麻醬涼麵 🥢", "肉絲炒飯 🍛", "火雞肉飯 🦃", "鴨肉飯 🦆", "自助餐 🥗", 
                "健康水煮餐盒 🥦", "紅燒牛肉麵 🍜", "海南雞飯 🇸🇬", "溫州大餛飩 🥟", "什錦燴飯 🥘", 
                "台式涼麵 🥒", "廣式燒臘飯 🍖", "日式丼飯 🍱", "排骨酥麵 🍜", "土魠魚羹麵 🐟", 
                "滑蛋蝦仁飯 🍤", "客家小炒飯 🐷", "越南河粉 🍜", "泰式綠咖哩 🍛", "韓式炸醬麵 🍜", 
                "紅油抄手 🌶️", "素食餐盒 🥗", "香酥雞肉飯 🍚", "擔仔麵 🍜", "池上便當 🍱", 
                "魚羹麵 🍜", "肉羹麵 🍜", "麻婆豆腐飯 🥘", "咖哩烏龍麵 🍜", "台式控肉便當 🐖", 
                "三寶飯 🍱", "油雞飯 🐥", "炸醬麵 🍜", "素食麵 🍜", "什錦湯麵 🍜", 
                "打拋豬便當 🍛", "清燉牛肉麵 🥣", "上海生煎包 🥟", "雞肉捲 🌯", "叉燒麵 🍜", 
                "皮蛋拌麵 🥢", "羊肉燴飯 🐑", "麻油雞飯 🍚", "豬腳便當 🐷", "吻仔魚炒飯 🐟"
            ],
            "晚餐": [
                "夜市台式牛排 🥩", "日式拉麵 🍜", "迴轉壽司 🍣", "百元熱炒 🍻", "義大利麵 🍝", 
                "韓式烤肉 🥘", "泰式打拋豬 🍛", "小火鍋 🍲", "屋馬燒肉 🥩", "咖哩豬排飯 🍛", 
                "麻辣火鍋 🌶️", "壽喜燒 🍲", "石鍋拌飯 🍚", "手工披薩 🍕", "羊肉爐 🥘", 
                "薑母鴨 🦆", "酸菜魚 🐟", "港式飲茶 🫖", "美式漢堡 🍔", "北平烤鴨 🦆", 
                "肉骨茶 🥣", "四川麻辣燙 🌶️", "砂鍋魚頭 🐟", "歐式排餐 🍷", "蒙古烤肉 🍖", 
                "南印咖哩 🫓", "海鮮燉飯 🥘", "日式居酒屋 🍺", "豬腳飯 🍚", "麻油雞麵線 🍗", 
                "酸辣土豆絲 🍚", "烤全魚 🐟", "汕頭火鍋 🍲", "石頭火鍋 🍲", "廣式粥品 🥣", 
                "鐵板燒 🍳", "泰式檸檬魚 🐟", "麻油腰子 🥣", "東坡肉 🍚", "客家鹹湯圓 🥣", 
                "紅酒燉牛肉 🍛", "酸辣粉 🍜", "北京炸醬麵 🍜", "花雕雞鍋 🍲", "藥燉排骨 🥣", 
                "壽司便當 🍱", "鰻魚飯 🍱", "舒芙蕾歐姆蛋 🍳", "乾煸季豆 🥗", "起司豬排 🧀"
            ],
            "宵夜": [
                "萬惡鹹酥雞 🐔", "加熱滷味 🍢", "碳烤串燒 🍡", "麥當勞 🍟", "泡麵加蛋 🍜", 
                "永和豆漿 🥛", "清粥小菜 🥣", "章魚燒 🐙", "臭豆腐 🥢", "超商微波食品 🏪", 
                "東山鴨頭 🦆", "大腸包小腸 🌭", "藥燉排骨 🥣", "烤肉刈包 🥙", "蚵仔煎 🍳", 
                "鹽水雞 🍗", "雞排配珍奶 🥤", "烤玉米 🌽", "營養三明治 🥪", "深坑臭豆腐 🥘", 
                "大腸麵線 🍜", "甜不辣 🍢", "廣東粥 🥣", "麻辣鴨血 🌶️", "烤魚下巴 🐟", 
                "炭烤大雞排 🍗", "豆花芋圓 🍧", "花生捲冰淇淋 🥜", "紅豆湯圓 🥣", "炭烤土司 🥪", 
                "現切水果 🍍", "涼麵味噌湯 🍜", "胡椒餅 🫓", "肉粽 🍙", "豬血糕 🥢", 
                "關東煮 🍢", "一蘭拉麵 🍜", "燒仙草 🥣", "芒果冰 🍧", "糖葫蘆 🍓", 
                "蔥抓餅 🫓", "地瓜球 🍠", "水煎包 🥟", "雞蛋仔 🥚", "大判燒 🥯", 
                "炸鮮奶 🥛", "起司馬鈴薯 🥔", "涼圓 🍡", "鳥蛋 🥚", "黑輪 🍢"
            ]
        }

        # 將所有分類的食物合併成一個大清單，供沒有輸入參數時使用
        all_foods = []
        for foods in food_menu.values():
            all_foods.extend(foods)

        # 判斷使用者的輸入
        if category in food_menu:
            # 如果有輸入對應的分類 (例如: !eat 早餐)
            choice = random.choice(food_menu[category])
            title = f"🍽️ 一定要吃【{category}】"
        elif category is not None:
            # 如果輸入了奇怪的分類 (例如: /eat 點心)，給予提示
            await ctx.send("❓ 我只有分：`早餐`、`午餐`、`晚餐`、`宵夜` 喔！不然你就直接打 `/eat`。")
            return
        else:
            # 如果什麼都沒輸入 (!eat)，就從所有食物裡隨機抽
            choice = random.choice(all_foods)
            title = "🍽️ 今天吃"

        # 建立回覆面板
        embed = discord.Embed(
            title=title,
            description=f"{ctx.author.mention}，我強烈建議你去吃：\n\n### **{choice}**",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Fun(bot))