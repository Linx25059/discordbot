import discord
from discord.ext import commands
import re
from urllib.parse import urlparse, urlunparse

class LinkFixer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 建立正則表達式，用來抓取訊息中的任何可能網址
        self.url_pattern = re.compile(r'(https?://[^\s>\|]+)')

    def fix_single_url(self, url: str) -> str | None:
        try:
            parsed = urlparse(url)
        except Exception:
            return None
            
        netloc = parsed.netloc.lower()
        path = parsed.path
        
        # 移除前導的 'www.' 以便統一判斷
        def clean_netloc(nl):
            if nl.startswith('www.'):
                return nl[4:]
            return nl

        domain = clean_netloc(netloc)
        
        # 1. Twitter / X
        if domain in ('twitter.com', 'x.com'):
            if '/status/' in path:
                return urlunparse(parsed._replace(netloc='fxtwitter.com'))
                
        # 2. Instagram
        elif domain == 'instagram.com':
            if path.startswith(('/p/', '/reel/', '/reels/')):
                return urlunparse(parsed._replace(netloc='ddinstagram.com'))
                
        # 3. TikTok
        elif domain == 'tiktok.com' or netloc.endswith('.tiktok.com'):
            if domain == 'vm.tiktok.com':
                return urlunparse(parsed._replace(netloc='vm.vxtiktok.com'))
            else:
                return urlunparse(parsed._replace(netloc='tnktok.com'))
                
        # 4. Threads
        elif domain in ('threads.net', 'threads.com'):
            return urlunparse(parsed._replace(netloc='fixthreads.seria.moe'))
            
        # 5. Reddit
        elif domain in ('reddit.com', 'redditmedia.com'):
            return urlunparse(parsed._replace(netloc='rxddit.com'))
            
        # 6. Pixiv
        elif domain == 'pixiv.net':
            return urlunparse(parsed._replace(netloc='phixiv.net'))
            
        # 7. Bluesky
        elif domain == 'bsky.app':
            return urlunparse(parsed._replace(netloc='fxbsky.app'))
            
        # 8. Bilibili (B站影片或短網址)
        elif domain == 'bilibili.com' or domain == 'b23.tv':
            return urlunparse(parsed._replace(netloc='vxbilibili.com'))
            
        # 9. Twitch Clip (影片剪輯)
        elif domain == 'twitch.tv' or netloc == 'clips.twitch.tv':
            if netloc == 'clips.twitch.tv' or '/clip/' in path:
                new_netloc = 'fxtwitch.seria.moe'
                if netloc == 'clips.twitch.tv':
                    new_path = f"/clip{path}" if not path.startswith('/clip/') else path
                    return urlunparse(parsed._replace(netloc=new_netloc, path=new_path))
                return urlunparse(parsed._replace(netloc=new_netloc))
                
        # 10. Spotify (單曲、專輯、播放清單等)
        elif domain == 'spotify.com' or netloc == 'open.spotify.com':
            if path.startswith(('/track/', '/album/', '/artist/', '/playlist/')):
                return urlunparse(parsed._replace(netloc='fxspotify.com'))
                
        # 11. YouTube Shorts (YouTube 短片)
        elif domain in ('youtube.com', 'youtu.be'):
            if path.startswith('/shorts/'):
                return urlunparse(parsed._replace(netloc='koutube.com'))
                
        return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # 快速檢查訊息是否含有網址，減少後續正則比對負荷
        if not self.url_pattern.search(message.content):
            return

        fixed_urls = []

        def replacer(match):
            url = match.group(1)
            fixed = self.fix_single_url(url)
            if fixed:
                fixed_urls.append(fixed)
                return fixed
            return url

        # 替換訊息中的所有符合條件的網址
        new_content = self.url_pattern.sub(replacer, message.content)

        # 若沒有任何網址被修改，則不進行後續動作
        if not fixed_urls:
            return

        try:
            # 嘗試取得頻道中的 Webhook
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
            
            # 刪除原訊息
            await message.delete()

        except discord.Forbidden:
            # 如果機器人權限不足 (無法管理 Webhook 或刪除訊息)，退回舊版簡單的回覆模式
            try:
                await message.edit(suppress=True)
            except discord.Forbidden:
                pass
            
            reply_content = "🔗 **為您提供可預覽的連結：**\n" + "\n".join(fixed_urls)
            await message.reply(reply_content, mention_author=False)

async def setup(bot):
    await bot.add_cog(LinkFixer(bot))