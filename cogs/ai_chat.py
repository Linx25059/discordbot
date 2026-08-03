import discord
from discord.ext import commands
import os
import logging
import traceback

logger = logging.getLogger(__name__)

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 讀取環境變數，若無則使用預設值
        self.api_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
        self.model = os.getenv("OLLAMA_MODEL", "Formosa-1/Llama-3.2-3B-F1:latest")
        logger.info(f"AI 聊天模組已初始化。API 端點: {self.api_url} | 模型: {self.model}")

    def format_response(self, text: str) -> str:
        """
        處理並美化模型的輸出。例如將 DeepSeek-R1 的 <think> 標籤轉換為 Discord 隱藏劇透框 (Spoiler Block)。
        """
        if not text:
            return text
        
        # 將 <think> ... </think> 轉換為 Discord 劇透格式 || [思考過程] ... ||
        # 使用非貪婪匹配處理可能有多個 think 區塊的情況
        import re
        def replace_think(match):
            content = match.group(1).strip()
            if content:
                return f"||**[思考過程]**\n{content}||\n"
            return ""

        formatted = re.sub(r"<think>(.*?)</think>", replace_think, text, flags=re.DOTALL)
        return formatted.strip()

    def split_message(self, text: str, limit: int = 1950) -> list[str]:
        """
        將長訊息分割成多個符合 Discord 限制 (預設 2000 字，保險起見設 1950 字) 的區塊，避免傳送失敗。
        """
        if len(text) <= limit:
            return [text]

        chunks = []
        remaining = text
        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break
            
            # 優先嘗試在換行處分割
            split_idx = remaining.rfind('\n', 0, limit)
            if split_idx == -1 or split_idx < (limit - 300):
                # 如果找不到好換行，或換行太前面，嘗試在空格處分割
                split_idx = remaining.rfind(' ', 0, limit)
                if split_idx == -1 or split_idx < (limit - 100):
                    # 強制在上限處割開
                    split_idx = limit

            chunks.append(remaining[:split_idx])
            remaining = remaining[split_idx:].lstrip()
            
        return chunks

    async def generate_response(self, prompt: str) -> str:
        """
        發送 API 請求到 Ollama 獲取模型生成結果
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False  # 禁用串流，一次取得完整結果以便 Discord 回覆
        }
        
        async with self.bot.session.post(self.api_url, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                raw_response = data.get("response", "")
                return self.format_response(raw_response)
            else:
                error_msg = f"Ollama 伺服器回傳錯誤狀態碼: {response.status}"
                logger.error(error_msg)
                return f"❌ 呼叫 AI 模型時發生錯誤 (錯誤碼 {response.status})"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 排除自己與其他機器人的訊息
        if message.author.bot:
            return

        # 檢查是否被提及 (Mention)
        if self.bot.user in message.mentions:
            # 清理訊息：移除提及機器人的標籤
            prompt = message.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
            if not prompt:
                await message.reply("您好！想和我聊天嗎？請在提及我後輸入您的問題！\n例如：`@機器人 請幫我寫一首詩`")
                return

            logger.info(f"[AI 對話] 使用者: {message.author} | 問題: {prompt}")
            
            async with message.channel.typing():
                try:
                    response_text = await self.generate_response(prompt)
                    if not response_text:
                        response_text = "（AI 似乎保持沉默，未返回任何內容）"
                    
                    # 分割長訊息並發送
                    chunks = self.split_message(response_text)
                    for i, chunk in enumerate(chunks):
                        if i == 0:
                            await message.reply(chunk)
                        else:
                            await message.channel.send(chunk)
                except Exception as e:
                    logger.error(f"AI 回覆處理失敗: {e}")
                    traceback.print_exc()
                    await message.reply("⚠️ AI 對話處理時發生未預期錯誤，請檢查 Ollama 伺服器是否正常運行。")

    @commands.command(name="chat", help="與 AI 聊天：!chat [您的問題]")
    async def chat(self, ctx, *, prompt: str = None):
        if not prompt:
            await ctx.send("請在指令後面輸入您的問題！例如：`!chat 你知道什麼是 Discord 嗎？`")
            return

        logger.info(f"[AI 指令] 使用者: {ctx.author} | 問題: {prompt}")

        async with ctx.typing():
            try:
                response_text = await self.generate_response(prompt)
                if not response_text:
                    response_text = "（AI 似乎保持沉默，未返回任何內容）"
                
                chunks = self.split_message(response_text)
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await ctx.reply(chunk)
                    else:
                        await ctx.send(chunk)
            except Exception as e:
                logger.error(f"AI 指令處理失敗: {e}")
                traceback.print_exc()
                await ctx.reply("⚠️ AI 對話處理時發生異常，請確認伺服器與模型已正常部署。")

async def setup(bot):
    await bot.add_cog(AIChat(bot))
