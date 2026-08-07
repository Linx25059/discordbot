import discord
from discord.ext import commands
from discord import app_commands
import os
import aiohttp
import logging
import traceback
import re
import urllib.parse
from typing import Optional

logger = logging.getLogger(__name__)

FLAG_TO_LANG = {
    "🇹🇼": "Traditional Chinese",
    "🇭🇰": "Traditional Chinese",
    "🇨🇳": "Simplified Chinese",
    "🇺🇸": "English",
    "🇬🇧": "English",
    "🇯🇵": "Japanese",
    "🇰🇷": "Korean",
    "🇫🇷": "French",
    "🇩🇪": "German",
    "🇪🇸": "Spanish",
    "🇷🇺": "Russian",
    "🇻🇳": "Vietnamese",
    "🇹🇭": "Thai"
}

class Translation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 註冊 Discord 右鍵訊息上下文選單指令
        self.ctx_menu = app_commands.ContextMenu(
            name='翻譯此訊息',
            callback=self.translate_message_context_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        # 卸載 Cog 時移除上下文選單
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def cog_load(self):
        # 初始化自動翻譯頻道資料表
        await self.bot.db.db.execute('''
            CREATE TABLE IF NOT EXISTS translation_channels (
                guild_id INTEGER,
                channel_id INTEGER PRIMARY KEY,
                target_language TEXT
            )
        ''')
        await self.bot.db.db.commit()

    def get_lang_code(self, lang_name: str) -> str:
        """
        將可讀的語言名稱轉換為 Google 翻譯使用的 ISO 語言代碼
        """
        lang_name_lower = lang_name.lower().strip()
        # 支援繁體中文的各種寫法
        if "traditional" in lang_name_lower or "繁體" in lang_name_lower or "繁中" in lang_name_lower or "zh-tw" in lang_name_lower:
            return "zh-TW"
        # 簡體中文
        if "simplified" in lang_name_lower or "簡體" in lang_name_lower or "簡中" in lang_name_lower or "zh-cn" in lang_name_lower:
            return "zh-CN"
            
        # 其他常見語言映射
        name_map = {
            "english": "en", "英文": "en", "英語": "en",
            "japanese": "ja", "日文": "ja", "日語": "ja",
            "korean": "ko", "韓文": "ko", "韓語": "ko",
            "french": "fr", "法文": "fr", "法語": "fr",
            "german": "de", "德文": "de", "德語": "de",
            "spanish": "es", "西班牙文": "es", "西班牙語": "es",
            "russian": "ru", "俄文": "ru", "俄語": "ru",
            "vietnamese": "vi", "越南文": "vi", "越南語": "vi",
            "thai": "th", "泰文": "th", "泰語": "th"
        }
        return name_map.get(lang_name_lower, "en")

    async def translate_text(self, text: str, target_lang: str, prompt_type: str = "direct") -> Optional[str]:
        """
        核心翻譯函式：優先使用 Gemini AI，若遇到錯誤則自動啟用 Google 翻譯備用方案
        """
        # 1. 優先嘗試 Gemini AI
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"

            if prompt_type == "auto":
                prompt = (
                    f"You are an expert translator bot.\n"
                    f"Translate the following text into {target_lang}.\n"
                    f"If the text is already in {target_lang} or is just emojis/mentions/numbers/links/command prefixes (like !, /) and doesn't need translation, output ONLY the string \"NO_TRANSLATION_NEEDED\".\n"
                    f"Otherwise, output ONLY the translated text. Do not add any conversational filler, explanations, or notes.\n\n"
                    f"Text to translate:\n"
                    f"{text}"
                )
            else:
                prompt = (
                    f"You are an expert translator bot.\n"
                    f"Translate the following text into {target_lang}.\n"
                    f"Output ONLY the translated text. Do not add any conversational filler, explanations, or notes.\n\n"
                    f"Text to translate:\n"
                    f"{text}"
                )

            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }]
            }

            try:
                # 設定 5 秒超時，防止 API 掛起延誤回應
                async with self.bot.session.post(url, json=payload, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "").strip()
                        logger.warning("Gemini API 回傳資料格式異常，啟用備用 Google 翻譯")
                    else:
                        logger.warning(f"Gemini API 狀態碼異常 ({response.status})，啟用備用 Google 翻譯")
            except Exception as e:
                logger.warning(f"呼叫 Gemini 翻譯失敗 ({e})，啟用備用 Google 翻譯")

        # 2. 備用方案：使用免費 Google 翻譯 Web API
        logger.info("正在使用備用 Google 翻譯端點...")
        try:
            target_code = self.get_lang_code(target_lang)
            encoded_text = urllib.parse.quote(text)
            free_url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_code}&dt=t&q={encoded_text}"

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com/resources)"
            }

            async with self.bot.session.get(free_url, headers=headers, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    translated_parts = []
                    for part in data[0]:
                        if part[0]:
                            translated_parts.append(part[0])

                    translated_text = "".join(translated_parts).strip()
                    detected_source = data[2]

                    # 在自動翻譯頻道模式下，套用過濾條件
                    if prompt_type == "auto":
                        # 偵測到的語言與目標語言代碼一致，說明不需翻譯
                        if detected_source.lower() == target_code.lower():
                            return "NO_TRANSLATION_NEEDED"

                        # 翻譯前後內容一致，說明是純連結、純表情或純數字
                        orig_clean = "".join(text.split()).lower()
                        trans_clean = "".join(translated_text.split()).lower()
                        if orig_clean == trans_clean:
                            return "NO_TRANSLATION_NEEDED"

                    return translated_text
                else:
                    logger.error(f"備用 Google 翻譯 API 狀態碼異常 ({response.status})")
        except Exception as e:
            logger.error(f"備用 Google 翻譯執行失敗: {e}")
            traceback.print_exc()

        return None

    @commands.hybrid_command(
        name="translate",
        aliases=["翻譯"],
        help="【一般/斜線指令】將指定文字翻譯成目標語言"
    )
    @app_commands.describe(
        text="要翻譯的文字內容",
        target_language="目標語言，預設為 Traditional Chinese (繁體中文)"
    )
    async def translate(self, ctx, text: str, target_language: str = "Traditional Chinese"):
        await ctx.defer()

        translated = await self.translate_text(text, target_language, prompt_type="direct")
        if not translated:
            await ctx.send("❌ 翻譯失敗，請檢查 API 金鑰設定與網路連線。")
            return

        embed = discord.Embed(
            title="🌐 翻譯結果 (Translation Result)",
            color=0x5865F2
        )
        orig_text = text if len(text) <= 1000 else text[:997] + "..."
        trans_text = translated if len(translated) <= 1000 else translated[:997] + "..."

        embed.add_field(name="📝 原文 (Original)", value=orig_text, inline=False)
        embed.add_field(name="🎯 譯文 (Translated)", value=trans_text, inline=False)
        embed.set_footer(text=f"目標語言: {target_language} | Powered by Gemini API")

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="translation_setup",
        help="【管理員】設定頻道的自動翻譯功能。用法：!translation_setup action [channel] [target_language]"
    )
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        action="操作類型：enable (啟用), disable (停用), list (列表)",
        channel="目標頻道 (enable/disable 時需要，預設為當前頻道)",
        target_language="目標語言，預設為 Traditional Chinese (繁體中文)"
    )
    async def translation_setup(
        self,
        ctx,
        action: str,
        channel: discord.TextChannel = None,
        target_language: str = "Traditional Chinese"
    ):
        action = action.lower().strip()
        if action not in ["enable", "disable", "list"]:
            await ctx.send("❌ 無效的操作類型！請使用 `enable`、`disable` 或 `list`。")
            return

        if action == "enable":
            target_channel = channel or ctx.channel
            await self.bot.db.db.execute(
                "INSERT OR REPLACE INTO translation_channels (guild_id, channel_id, target_language) VALUES (?, ?, ?)",
                (ctx.guild.id, target_channel.id, target_language)
            )
            await self.bot.db.db.commit()

            embed = discord.Embed(
                title="✅ 啟用自動翻譯",
                description=f"已成功對頻道 {target_channel.mention} 啟用自動翻譯功能！",
                color=discord.Color.green()
            )
            embed.add_field(name="🎯 目標語言", value=f"`{target_language}`", inline=True)
            await ctx.send(embed=embed)

        elif action == "disable":
            target_channel = channel or ctx.channel
            async with self.bot.db.db.execute(
                "SELECT 1 FROM translation_channels WHERE channel_id = ?",
                (target_channel.id,)
            ) as cursor:
                exists = await cursor.fetchone()

            if not exists:
                await ctx.send(f"❌ 頻道 {target_channel.mention} 尚未啟用自動翻譯。")
                return

            await self.bot.db.db.execute(
                "DELETE FROM translation_channels WHERE channel_id = ?",
                (target_channel.id,)
            )
            await self.bot.db.db.commit()

            embed = discord.Embed(
                title="🧹 停用自動翻譯",
                description=f"已成功對頻道 {target_channel.mention} 停用自動翻譯功能。",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)

        elif action == "list":
            async with self.bot.db.db.execute(
                "SELECT channel_id, target_language FROM translation_channels WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                rows = await cursor.fetchall()

            if not rows:
                await ctx.send("ℹ️ 當前伺服器中沒有任何頻道啟用自動翻譯。")
                return

            embed = discord.Embed(
                title="📋 自動翻譯頻道列表",
                color=0x5865F2
            )

            channels_info = []
            for ch_id, lang in rows:
                ch = ctx.guild.get_channel(ch_id)
                ch_mention = ch.mention if ch else f"未知頻道 (ID: {ch_id})"
                channels_info.append(f"- {ch_mention} ➔ 目標語言: `{lang}`")

            embed.description = "\n".join(channels_info)
            await ctx.send(embed=embed)

    async def translate_message_context_menu(self, interaction: discord.Interaction, message: discord.Message):
        """
        右鍵點擊訊息翻譯的 Context Menu 回呼函式
        """
        await interaction.response.defer(ephemeral=True)
        if not message.content:
            await interaction.followup.send("❌ 無法翻譯沒有文字的訊息。", ephemeral=True)
            return

        # 貼心邏輯：如果原文包含中文，則翻譯為英文；否則一律翻譯為繁體中文
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', message.content))
        target_language = "English" if has_chinese else "Traditional Chinese"

        translated = await self.translate_text(message.content, target_language, prompt_type="direct")
        if not translated:
            await interaction.followup.send("❌ 翻譯失敗，請檢查 API 金鑰設定與網路連線。", ephemeral=True)
            return

        embed = discord.Embed(
            title="🌐 訊息翻譯 (Message Translation)",
            color=0x5865F2
        )
        orig_text = message.content if len(message.content) <= 1000 else message.content[:997] + "..."
        trans_text = translated if len(translated) <= 1000 else translated[:997] + "..."

        embed.add_field(name="📝 原文 (Original)", value=orig_text, inline=False)
        embed.add_field(name="🎯 譯文 (Translated)", value=trans_text, inline=False)
        embed.set_footer(text=f"目標語言: {target_language} | 原始作者: {message.author.display_name} | Powered by Gemini API")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        當設定自動翻譯的頻道有新訊息時觸發
        """
        # 排除機器人、系統訊息
        if message.author.bot or message.is_system():
            return

        # 排除一般指令格式
        if message.content.startswith("!"):
            return

        # 檢查該頻道是否設定為自動翻譯
        async with self.bot.db.db.execute(
            "SELECT target_language FROM translation_channels WHERE channel_id = ?",
            (message.channel.id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return

        target_lang = row[0]
        clean_content = message.content.strip()
        if not clean_content:
            return

        # 執行偵測與翻譯
        translated = await self.translate_text(clean_content, target_lang, prompt_type="auto")

        # 若需要翻譯，且翻譯結果不為預設字串
        if translated and translated.strip() != "NO_TRANSLATION_NEEDED":
            await message.reply(f"🌐 **[{target_lang}]** {translated.strip()}", mention_author=False)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        當有人對訊息點選國旗反應時觸發
        """
        # 排除機器人自身的反應
        if payload.user_id == self.bot.user.id:
            return

        emoji_str = str(payload.emoji)
        if emoji_str not in FLAG_TO_LANG:
            return

        target_lang = FLAG_TO_LANG[emoji_str]

        # 取得頻道
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except Exception:
                return

        # 取得訊息
        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        # 排除空訊息或機器人發送的訊息
        if not message.content or message.author.bot:
            return

        # 翻譯訊息
        translated = await self.translate_text(message.content, target_lang, prompt_type="direct")

        if translated:
            await message.reply(f"🌐 **[{target_lang} 翻譯]** {translated.strip()}", mention_author=False)

async def setup(bot):
    await bot.add_cog(Translation(bot))
