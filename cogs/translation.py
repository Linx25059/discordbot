import discord
from discord.ext import commands
from discord import app_commands
import os
import aiohttp
import logging
import traceback
import re
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

    async def translate_text(self, text: str, target_lang: str, prompt_type: str = "direct") -> Optional[str]:
        """
        核心翻譯函式：呼叫 Gemini API 進行翻譯與語言偵測
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("未在 .env 中設定 GEMINI_API_KEY")
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"

        if prompt_type == "auto":
            # 用於自動翻譯頻道的 Prompts (包含 NO_TRANSLATION_NEEDED 過濾機制)
            prompt = (
                f"You are an expert translator bot.\n"
                f"Translate the following text into {target_lang}.\n"
                f"If the text is already in {target_lang} or is just emojis/mentions/numbers/links/command prefixes (like !, /) and doesn't need translation, output ONLY the string \"NO_TRANSLATION_NEEDED\".\n"
                f"Otherwise, output ONLY the translated text. Do not add any conversational filler, explanations, or notes.\n\n"
                f"Text to translate:\n"
                f"{text}"
            )
        else:
            # 用於主動請求（如指令、右鍵、國旗反應）
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
            async with self.bot.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                    logger.error("Gemini API 回傳資料格式異常或無生成內容")
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"Gemini API 回傳錯誤狀態碼 {response.status}: {error_text}")
                    return None
        except Exception as e:
            logger.error(f"呼叫 Gemini 翻譯 API 時發生錯誤: {e}")
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
