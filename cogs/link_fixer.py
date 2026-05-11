import discord
from discord.ext import commands
import re

class LinkFixer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 設定要替換的網域對應表 (使用目前主流且穩定的預覽 API)
        self.fix_map = {
            "twitter.com": "vxtwitter.com",
            "x.com": "fixvx.com",
            "instagram.com": "kkinstagram.com",
            "tiktok.com": "d.tiktokez.com",
            "vm.tiktok.com": "vm.vxtiktok.com",
            "threads.com": "fixthreads.seria.moe",
            "threads.net": "vxthreads.net",
            "pixiv.net": "phixiv.net",
            "reddit.com": "rxddit.com",
            "bsky.app": "vxbsky.app"
        }
        
        # 建立正則表達式，用來精準抓取訊息中的目標網址
        domain_pattern = "|".join(re.escape(domain) for domain in self.fix_map.keys())
        # [^\s>\|]+ 可以避免抓取到空格、Discord 的防雷標籤 || 或是隱藏預覽的 <>
        self.url_pattern = re.compile(rf'(https?://)(?:www\.)?({domain_pattern})(/[^\s>\|]*)')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # 檢查是否包含需要修復的連結
        if not self.url_pattern.search(message.content):
            return

        # 定義正則表達式的替換邏輯
        def replacer(match):
            protocol = match.group(1)
            domain = match.group(2)
            path = match.group(3)
            fixed_domain = self.fix_map[domain]
            return f"{protocol}{fixed_domain}{path}"

        # 替換訊息中的所有網址 (保留使用者輸入的其他文字)
        new_content = self.url_pattern.sub(replacer, message.content)

        try:
            # 嘗試取得頻道中的 Webhook
            webhooks = await message.channel.webhooks()
            # 判斷是否在討論串 (Thread) 中，Thread 本身沒有 webhook，需從母頻道取得
            if isinstance(message.channel, discord.Thread):
                webhook_channel = message.channel.parent
            else:
                webhook_channel = message.channel
                
            webhooks = await webhook_channel.webhooks()
            webhook = discord.utils.get(webhooks, user=self.bot.user)
            # 如果沒有，就建立一個
            if not webhook:
                webhook = await webhook_channel.create_webhook(name="LinkFixer")

            # 準備附件 (如果有圖片或其他檔案，也一併帶過去)
            files = [await attachment.to_file() for attachment in message.attachments]

            # 透過 Webhook 發送偽裝訊息
            if isinstance(message.channel, discord.Thread):
                await webhook.send(
                    content=new_content,
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url,
                    files=files,
                    thread=message.channel
                )
            else:
                await webhook.send(
                    content=new_content,
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url,
                    files=files
                )
            
            # 刪除原訊息 (讓版面看起來像是玩家自己發出的完美連結)
            await message.delete()

        except discord.Forbidden:
            # 如果機器人權限不足 (無法管理 Webhook 或刪除訊息)，退回舊版簡單的回覆模式
            fixed_urls = []
            matches = self.url_pattern.findall(message.content)
            for match in matches:
                protocol, domain, path = match
                fixed_domain = self.fix_map[domain]
                fixed_urls.append(f"{protocol}{fixed_domain}{path}")
                
            try:
                await message.edit(suppress=True)
            except discord.Forbidden:
                pass
            
            reply_content = "🔗 **為您提供可預覽的連結：**\n" + "\n".join(fixed_urls)
            await message.reply(reply_content, mention_author=False)

async def setup(bot):
    await bot.add_cog(LinkFixer(bot))