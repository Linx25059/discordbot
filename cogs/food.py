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

class Food(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_random_food(self, category: Optional[str] = None):
        # 🌅 早餐清單 (44 項)
        breakfast = [
            "蛋餅", "蘿蔔糕", "鐵板麵", "漢堡", "吐司", "三明治", "飯糰", "燒餅油條",
            "豆漿油條", "蔥抓餅", "水煎包", "饅頭加蛋", "鹹粥", "鍋貼", "生煎包", "麵線",
            "涼麵", "鬆餅", "貝果", "可頌", "燕麥粥", "煎餃", "豬腸粉", "小籠包",
            "培根蛋餅", "起司蛋餅", "薯餅", "熱狗", "蘿蔔糕加蛋", "蔥肉餅", "生菜沙拉",
            "鮪魚三明治", "總匯三明治", "卡啦雞腿堡", "牛肉漢堡", "豬肉滿福堡", "烤果醬吐司",
            "厚片吐司", "法國吐司", "皮蛋瘦肉粥", "肉燥飯", "炒麵麵包", "班尼迪克蛋", "水果燕麥片"
        ]
        
        # 🍱 午餐清單 (44 項)
        lunch = [
            "滷肉飯", "牛肉麵", "雞排便當", "排骨飯", "炒飯", "炒麵", "水餃", "涼麵",
            "鍋燒意麵", "健康餐盒", "乾麵", "肉羹麵", "米粉湯", "自助餐", "肉圓", "大腸包小腸",
            "麥當勞", "肯德基", "漢堡王", "摩斯漢堡", "Subway", "輕食沙拉", "日式定食", "咖哩飯",
            "海南雞飯", "打拋豬飯", "三寶飯", "燒臘便當", "親子丼", "勝丼", "鰻魚飯", "鐵板牛排",
            "石鍋拌飯", "辣炒年糕", "海鮮粥", "皮蛋豆腐", "榨菜肉絲麵", "餛飩麵", "烤雞腿便當",
            "鯖魚便當", "麻婆豆腐飯", "蔥爆牛肉飯", "三杯雞飯", "叉燒飯"
        ]

        # 🍽️ 晚餐清單 (44 項)
        dinner = [
            "火鍋", "燒肉", "牛排", "義大利麵", "披薩", "壽司", "拉麵", "鐵板燒",
            "越式河粉", "泰式打拋豬", "韓式拌飯", "韓式炸雞", "熱炒", "薑母鴨", "羊肉爐", "居酒屋",
            "部隊鍋", "豬排飯", "生魚片", "小籠包", "甕仔雞", "烤魚", "日式漢堡排", "餐酒館",
            "麻辣火鍋", "壽喜燒", "串烤", "石頭火鍋", "個人小火鍋", "烤鴨", "紅酒燉牛肉", "海鮮燉飯",
            "日式咖哩豬排", "生蠔", "生魚片丼飯", "龍蝦", "烤肉拼盤", "泰式檸檬魚", "月亮蝦餅", "台式快炒",
            "酸菜白肉鍋", "壽司拼盤", "焗烤海鮮", "咖哩烤餅"
        ]
        
        # 🌙 宵夜清單 (43 項)
        midnight_snack = [
            "鹹酥雞", "串燒", "烤肉", "滷味", "泡麵", "麥當勞", "永和豆漿", "清粥小菜",
            "涼麵", "麻辣燙", "關東煮", "臭豆腐", "炸物拼盤", "雞排", "串串香", "宵夜火鍋",
            "炭烤土司", "生蠔", "居酒屋料理", "地瓜球", "章魚燒", "烤香腸", "牛肉湯",
            "水煮魚", "烤玉米", "炸魷魚", "炸甜不辣", "鹽水雞", "章魚小丸子", "深夜食堂拉麵",
            "大腸包小腸", "炸雞排", "烤米血", "深夜豆漿", "小籠湯包", "炸銀絲卷", "烤魷魚",
            "深夜牛排", "雞肉串", "炸薯條", "皮蛋瘦肉粥", "滷肉飯(宵夜版)", "熱壓吐司"
        ]

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

        food = random.choice(foods)
        time_str = category if category else "今天"
        
        return food, time_str

    @commands.hybrid_command(name="eat", aliases=["吃什麼", "吃啥", "午餐", "晚餐", "早餐", "宵夜"], help="不知道要吃什麼嗎？讓我來推薦！")
    @app_commands.describe(category="選擇你想吃的時段")
    @app_commands.choices(category=[
        app_commands.Choice(name="🌅 早餐", value="早餐"),
        app_commands.Choice(name="🍱 午餐", value="午餐"),
        app_commands.Choice(name="🍽️ 晚餐", value="晚餐"),
        app_commands.Choice(name="🌙 宵夜", value="宵夜")
    ])
    async def eat(self, ctx: commands.Context, category: Optional[str] = None):
        food, time_str = self.get_random_food(category)
        embed = discord.Embed(title="🍽️ 食物推薦", description=f"不知道吃什麼的話，{time_str}為您推薦：\n\n# 🍱 **{food}**", color=discord.Color.orange())
        embed.set_footer(text="不滿意可以再點擊下方按鈕重抽喔！")
        view = FoodRerollView(self, "eat", ctx.author.id, category)
        await ctx.send(embed=embed, view=view)

    def get_random_drink(self):
        # 🥤 2026 最夯手搖飲料店與熱門/經典菜單品項大全 (130+ 項)
        drinks = [
            "五十嵐 (50嵐) 的「1號 (珍波椰青茶)」", "五十嵐 (50嵐) 的「冰淇淋紅茶」", "五十嵐 (50嵐) 的「波霸奶茶」", "五十嵐 (50嵐) 的「四季春珍波椰」", "五十嵐 (50嵐) 的「8冰綠」", "五十嵐 (50嵐) 的「烏龍瑪奇朵」", "五十嵐 (50嵐) 的「阿華田」", "五十嵐 (50嵐) 的「梅子綠」", "五十嵐 (50嵐) 的「檸檬綠」", "五十嵐 (50嵐) 的「鮮奶茶」",
            "可不可熟成紅茶 的「白玉歐蕾」", "可不可熟成紅茶 的「熟成檸檬」", "可不可熟成紅茶 的「春芽冷露」", "可不可熟成紅茶 的「胭脂紅茶」", "可不可熟成紅茶 的「雪花冷露」", "可不可熟成紅茶 的「麗春紅茶」", "可不可熟成紅茶 的「春梅冰茶」", "可不可熟成紅茶 的「冷露歐蕾」",
            "一沐日 的「逮丸奶茶 (草仔粿)」", "一沐日 的「粉粿黑糖奶茶」", "一沐日 的「無糖蕎麥茶」", "一沐日 的「荔哥紅茶」", "一沐日 的「桂花蕎麥」", "一沐日 的「油切蕎麥茶」", "一沐日 的「洛神冰茶」", "一沐日 的「黃金蕎麥拿鐵」",
            "得正 的「檸檬春烏龍」", "得正 的「焙烏龍鮮奶」", "得正 的「芝士奶蓋春烏龍」", "得正 的「輕烏龍」", "得正 的「春烏龍」", "得正 的「優酪春烏龍」", "得正 的「甘蔗春烏龍」",
            "八曜和茶 的「柚香覺醒307」", "八曜和茶 的「究極308」", "八曜和茶 的「和風307」", "八曜和茶 的「寧夏307」", "八曜和茶 的「87牧場鮮奶茶」", "八曜和茶 的「八曜和茶」", "八曜和茶 的「蜜覺醒307」",
            "麻古茶坊 的「芝芝芒果果粒」", "麻古茶坊 的「楊枝甘露2.0」", "麻古茶坊 的「香橙果粒茶」", "麻古茶坊 的「金萱雙Q」", "麻古茶坊 的「翡翠柳橙」", "麻古茶坊 的「高山金萱茶」", "麻古茶坊 的「百香雙Q果」", "麻古茶坊 的「葡萄柚果粒茶」", "麻古茶坊 的「奇異果果粒茶」",
            "迷客夏 的「珍珠紅茶拿鐵」", "迷客夏 的「大甲芋頭鮮奶」", "迷客夏 的「伯爵紅茶拿鐵」", "迷客夏 的「柳丁綠茶」", "迷客夏 的「焙香決明大麥」", "迷客夏 的「茉香綠茶」", "迷客夏 的「原鄉冬瓜茶」", "迷客夏 的「青檸香茶」", "迷客夏 的「冬瓜麥茶」", "迷客夏 的「出雲抹茶牛奶」",
            "五桐號 的「杏仁凍五桐茶」", "五桐號 的「綠茶凍五桐茶」", "五桐號 的「老實人紅茶拿鐵」", "五桐號 的「招牌五桐奶茶」", "五桐號 的「荔枝冰茶凍飲」", "五桐號 的「清香烏龍」", "五桐號 的「玉堂春茶王」", "五桐號 的「一把青」", "五桐號 的「五桐茶」",
            "龜記 的「紅水烏龍」", "龜記 的「三十三茶王」", "龜記 的「蘋果紅萱」", "龜記 的「紅柚翡翠」", "龜記 的「黑木耳鮮奶茶」", "龜記 的「龜記濃乳茶」", "龜記 的「冬瓜鮮乳」", "龜記 的「阿源楊桃紅茶」",
            "鶴茶樓 的「鶴頂紅茶」", "鶴茶樓 的「綺夢那堤」", "鶴茶樓 的「青泰奶」", "鶴茶樓 的「桂香烏龍茶」", "鶴茶樓 的「藝伎那堤」", "鶴茶樓 的「神農紅茶」", "鶴茶樓 的「鶴頂那堤」",
            "萬波 的「島嶼紅茶」", "萬波 的「紅豆粉粿鮮奶」", "萬波 的「蘭葉那堤」", "萬波 的「金萱珍波粉」", "萬波 的「鳴光蜜檸檬」", "萬波 的「碧螺春」", "萬波 的「琥珀日常」", "萬波 的「冬瓜檸檬」",
            "清心福全 的「優多綠茶」", "清心福全 的「隱藏版 (珍珠蜂蜜普洱鮮奶茶)」", "清心福全 的「烏龍綠茶」", "清心福全 的「冰淇淋紅茶」", "清心福全 的「珍珠奶茶」", "清心福全 的「椰果奶茶」", "清心福全 的「多多綠」", "清心福全 的「布丁奶茶」",
            "珍煮丹 的「黑糖珍珠鮮奶」", "珍煮丹 的「泰泰鮮奶茶」", "珍煮丹 的「姍姍紅茶拿鐵」", "珍煮丹 的「黑糖檸檬冬瓜」", "珍煮丹 的「黑糖冬瓜」", "珍煮丹 的「十份芋芋牛奶」", "珍煮丹 的「百香雙響」",
            "茶湯會 的「觀音拿鐵」", "茶湯會 的「翡翠檸檬」", "茶湯會 的「珍珠紅豆拿鐵」", "茶湯會 的「鐵觀音」", "茶湯會 的「蔗香紅茶」",
            "大苑子 的「台灣鮮搾柳丁綠」", "大苑子 的「愛文芒果冰沙」", "大苑子 的「芭樂梅」", "大苑子 的「芭樂檸檬」", "大苑子 的「番茄梅」", "大苑子 的「奇異果冰沙」", "大苑子 的「蘋果冰茶」",
            "烏弄 的「冬露冬片」", "烏弄 的「杏仁凍冬片」", "烏弄 的「金萱烏龍」", "烏弄 的「原生青茶」", "烏弄 的「冬瓜烏龍」",
            "老賴茶棧 的「老賴紅茶」", "老賴茶棧 的「豆香紅茶」", "老賴茶棧 的「太后牛乳」", "老賴茶棧 的「招牌奶茶」", "老賴茶棧 的「青草茶」",
            "天仁茗茶 的「913茶王」", "天仁茗茶 的「珍珠鮮奶茶」", "天仁茗茶 的「洛神冰茶」", "天仁茗茶 的「香綠茶」", "天仁茗茶 的「普洱茶」",
            "COMEBUY 的「蘋果冰茶」", "COMEBUY 的「海神」", "COMEBUY 的「雙Q奶茶」", "COMEBUY 的「絕代雙Q奶茶」", "COMEBUY 的「百香搖果樂」",
            "COCO都可 的「百香雙響炮」", "COCO都可 的「奶茶三兄弟」", "COCO都可 的「星空葡萄」", "COCO都可 的「芒果冰沙」", "COCO都可 的「檸檬霸」",
            "春水堂 的「珍珠奶茶」", "春水堂 的「鐵觀音凍飲」", "春水堂 的「茉香奶茶」", "春水堂 的「翡翠檸檬」",
            "樺達奶茶 的「美容奶茶」", "樺達奶茶 的「益壽奶茶」", "樺達奶茶 的「樺達奶茶」", "樺達奶茶 的「普洱奶茶」",
            "叮哥茶飲 的「柳橙綠茶」", "叮哥茶飲 的「洛神花茶」", "叮哥茶飲 的「初鹿鮮奶茶」",
            "圓石禪飲 的「復刻紅茶」", "圓石禪飲 的「冷泉玉露」", "圓石禪飲 的「蕎麥綠茶」",
            "雙十八木 的「雙十八木紅」", "雙十八木 的「芝士奶蓋紅」", "雙十八木 的「珍珠鮮奶茶」", "雙十八木 的「黑糖波霸奶茶」",
            "顏太煮奶茶 的「太煮厚奶茶」", "顏太煮奶茶 的「海鹽奶蓋紅茶」",
            "抿茶 的「手炒焦糖鮮奶茶」", "抿茶 的「琥珀紅茶」",
            "鮮茶道 的「阿里山冰茶」", "鮮茶道 的「伯爵奶茶」", "鮮茶道 的「熊貓珍珠奶茶」",
            "星巴克 的「焦糖瑪奇朵」", "星巴克 的「抹茶那堤」", "星巴克 的「巧克力可可碎片星冰樂」", "星巴克 的「香草那堤」", "星巴克 的「冷萃咖啡」",
            "純濃厚木瓜牛奶", "透心涼綠豆沙牛奶", "道地泰式奶茶", "冰拿鐵", "冰美式咖啡", "特調氣泡飲", "手工冬瓜茶", "青草茶"
        ]
        return random.choice(drinks)

    @commands.hybrid_command(name="drink", aliases=["喝什麼", "喝啥", "飲料", "手搖飲"], help="不知道要喝什麼手搖飲嗎？讓我來推薦！")
    async def drink(self, ctx: commands.Context):
        drink = self.get_random_drink()
        embed = discord.Embed(title="🥤 手搖飲品項推薦", description=f"口渴了嗎？今天為您推薦：\n\n# 🧋 **{drink}**", color=discord.Color.blue())
        embed.set_footer(text="不滿意可以再點擊下方按鈕重抽喔！")
        view = FoodRerollView(self, "drink", ctx.author.id)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Food(bot))
