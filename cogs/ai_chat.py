import discord
from discord.ext import commands
import google.generativeai as genai
import os

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("警告: 找不到 GEMINI_API_KEY，請確認 .env 檔案設定。")
            
        genai.configure(api_key=api_key)
        
        # 💡 第一招：改造 AI 的靈魂 (System Instruction)
        # 這裡設定得越像真人，它的回答就會越口語！
        friend_persona = (
            "你現在是我在 Discord 上的好朋友。請一律使用「繁體中文（台灣）」。"
            "說話要非常口語、自然，就像真人朋友一樣，可以帶點幽默感或吐槽，並善用台灣常用的語氣詞（像是：哈哈、笑死、對啊、喔、欸、啦）。"
            "絕對不要像 AI 一樣列點說明或長篇大論，每次回答盡量精簡（控制在三四句話以內），就像我們在用 LINE 聊天一樣。"
            "如果我問你今天過得怎樣，你要能自己瞎掰一些日常小事。"
        )
        
        self.model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=friend_persona
        )
        
        # 💡 第二招：建立大腦記憶體 (儲存每個人的對話紀錄)
        # 用字典來存，這樣 A 講的話才不會跟 B 混在一起
        self.chat_sessions = {}

    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.hybrid_command(name="chat", aliases=["ai", "問"], help="跟 AI 朋友瞎聊")
    async def chat(self, ctx, *, prompt: str):
        async with ctx.typing():
            try:
                user_id = ctx.author.id
                
                # 如果這個人是第一次跟你聊天，就幫他開一個全新的「聊天室 (Session)」
                if user_id not in self.chat_sessions:
                    # start_chat 會自動幫我們記住上下文！
                    self.chat_sessions[user_id] = self.model.start_chat(history=[])
                
                # 取出這個使用者的專屬對話紀錄
                user_chat = self.chat_sessions[user_id]
                
                # 傳送訊息 (API 會自動把這次的 prompt 跟之前的紀錄綁在一起送給 Gemini)
                response = await user_chat.send_message_async(prompt)
                
                reply_text = response.text
                if len(reply_text) > 2000:
                    reply_text = reply_text[:1995] + "..."
                    
                await ctx.send(reply_text)
                
            except Exception as e:
                if "429" in str(e):
                    await ctx.send("⏳ 欸我回太快了，等我幾秒喘口氣啦！")
                else:
                    await ctx.send(f"❌ 完蛋，我腦袋當機了：\n```\n{e}\n```")

# 清除記憶的指令 (可選)
    @commands.hybrid_command(name="忘記", help="清除 AI 對你的記憶")
    async def clear_memory(self, ctx):
        user_id = ctx.author.id
        if user_id in self.chat_sessions:
            del self.chat_sessions[user_id]
            await ctx.send("🤯 登愣！我剛才是不是失憶了？我們聊到哪？")
        else:
            await ctx.send("🤔 我們才剛認識吧？我本來就沒有你的記憶啊。")

async def setup(bot):
    await bot.add_cog(AIChat(bot))