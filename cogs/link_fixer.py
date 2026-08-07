import discord
from discord.ext import commands
from discord import app_commands
import re
import os
import logging
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

class LinkFixer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 建立正則表達式，用來抓取訊息中的任何可能網址
        self.url_pattern = re.compile(r'(https?://[^\s>\|]+)')
        
        # 註冊右鍵選單指令，支援個人安裝 (User-Installable) 應用程式在所有伺服器使用
        self.ctx_menu = app_commands.ContextMenu(
            name='修復訊息中的連結',
            callback=self.fix_links_ctx
        )
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        # 卸載 Cog 時移除右鍵選單指令
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

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
            if not path.startswith('/share/'):
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

    async def resolve_threads_share_url(self, url: str) -> str | None:
        """
        將 Threads 的 /share/ 短網址解析並還原為標準的 post 網址，並替換為 fixthreads.seria.moe
        """
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            path = parsed.path
            
            domain = netloc
            if domain.startswith('www.'):
                domain = domain[4:]
                
            if domain in ('threads.net', 'threads.com') and path.startswith('/share/'):
                # aiohttp 會自動處理 Threads share 連結的所有重新導向，並還原至真實 post 網址
                async with self.bot.session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        final_url = str(response.url)
                        final_parsed = urlparse(final_url)
                        final_netloc = final_parsed.netloc.lower()
                        final_domain = final_netloc
                        if final_domain.startswith('www.'):
                            final_domain = final_domain[4:]
                            
                        # 確保重新導向後是 Threads 的貼文網址 (例如 /@user/post/post_id)
                        if final_domain in ('threads.net', 'threads.com') and '/post/' in final_parsed.path:
                            fixed_url = urlunparse(final_parsed._replace(
                                netloc='fixthreads.seria.moe',
                                query=''
                            ))
                            return fixed_url
        except Exception:
            pass
        return None

    async def resolve_douyin_url(self, url: str) -> str | None:
        """
        將抖音的短網址或標準網址轉換為中繼端網址，支援非同步跳轉追蹤
        """
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            path = parsed.path
            
            domain = netloc
            if domain.startswith('www.'):
                domain = domain[4:]
                
            proxy_base = os.getenv("DOUYIN_PROXY_BASE_URL", "https://your-douyin-proxy.vercel.app")

            # A. 處理手機端分享短網址 v.douyin.com
            if domain == 'v.douyin.com':
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                # aiohttp 連線池非同步跟隨跳轉以獲取真實的長網址
                async with self.bot.session.get(url, headers=headers, allow_redirects=True, timeout=5) as response:
                    if response.status == 200:
                        final_url = str(response.url)
                        final_parsed = urlparse(final_url)
                        id_match = re.search(r'/video/(\d+)', final_parsed.path)
                        if id_match:
                            video_id = id_match.group(1)
                            return f"{proxy_base.rstrip('/')}/video/{video_id}"
                            
            # B. 處理標準網頁版網址 douyin.com/video/...
            elif domain == 'douyin.com' and path.startswith('/video/'):
                id_match = re.search(r'/video/(\d+)', path)
                if id_match:
                    video_id = id_match.group(1)
                    return f"{proxy_base.rstrip('/')}/video/{video_id}"
        except Exception as e:
            logger.warning(f"解析抖音網址時發生錯誤: {e}")
        return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # 快速檢查訊息是否含有網址，減少後續正則比對負荷
        if not self.url_pattern.search(message.content):
            return

        urls = self.url_pattern.findall(message.content)
        fixed_urls = []
        replaced_mapping = {}

        for url in urls:
            # 1. 優先嘗試非同步解析 Threads 的 /share/ 網址
            fixed = await self.resolve_threads_share_url(url)
            if fixed:
                fixed_urls.append(fixed)
                replaced_mapping[url] = fixed
                continue

            # 2. 嘗試非同步解析 Douyin 網址 (短網址 & 標準網址)
            fixed = await self.resolve_douyin_url(url)
            if fixed:
                fixed_urls.append(fixed)
                replaced_mapping[url] = fixed
                continue

            # 3. 處理其他一般網址的同步轉換
            fixed = self.fix_single_url(url)
            if fixed:
                fixed_urls.append(fixed)
                replaced_mapping[url] = fixed

        # 若沒有任何網址被修改，則不進行後續動作
        if not replaced_mapping:
            return

        # 依照網址長度降序替換，防止子字串取代錯誤
        new_content = message.content
        for orig in sorted(replaced_mapping.keys(), key=len, reverse=True):
            fixed = replaced_mapping[orig]
            new_content = new_content.replace(orig, fixed)

        # 4. 如果是包含抖音分享文字的格式，清理掉所有的額外分享文案，僅保留修復後的連結
        is_douyin_share = False
        for url in urls:
            if 'v.douyin.com' in url or 'douyin.com' in url:
                if any(kw in message.content for kw in ['复制此链接', '打开Dou音', '打开抖音', 'Jvs:/', '復制此鏈接']):
                    is_douyin_share = True
                    break

        if is_douyin_share:
            new_content = "\n".join(fixed_urls)

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

    async def fix_links_ctx(self, interaction: discord.Interaction, message: discord.Message):
        """
        右鍵選單指令：自動修復訊息中含有的 Threads、抖音或 Twitter 等可預覽連結
        """
        # 快速檢查訊息是否含有網址
        if not self.url_pattern.search(message.content):
            await interaction.response.send_message("❌ 這則訊息中沒有偵測到任何網址喔！", ephemeral=True)
            return

        # 延遲回應以避免非同步解析超時
        await interaction.response.defer(ephemeral=False)

        urls = self.url_pattern.findall(message.content)
        fixed_urls = []
        replaced_mapping = {}

        for url in urls:
            # 1. 優先嘗試非同步解析 Threads 的 /share/ 網址
            fixed = await self.resolve_threads_share_url(url)
            if fixed:
                fixed_urls.append(fixed)
                replaced_mapping[url] = fixed
                continue

            # 2. 嘗試非同步解析 Douyin 網址 (短網址 & 標準網址)
            fixed = await self.resolve_douyin_url(url)
            if fixed:
                fixed_urls.append(fixed)
                replaced_mapping[url] = fixed
                continue

            # 3. 處理其他一般網址的同步轉換
            fixed = self.fix_single_url(url)
            if fixed:
                fixed_urls.append(fixed)
                replaced_mapping[url] = fixed

        if not fixed_urls:
            await interaction.followup.send("❌ 這則訊息中的網址不需要修復，或是不支援修復喔！", ephemeral=True)
            return

        # 整理修復後的連結輸出
        # 如果是包含抖音分享文字的格式，僅保留連結
        is_douyin_share = False
        for url in urls:
            if 'v.douyin.com' in url or 'douyin.com' in url:
                if any(kw in message.content for kw in ['复制此链接', '打开Dou音', '打开抖音', 'Jvs:/', '復制此鏈接']):
                    is_douyin_share = True
                    break

        if is_douyin_share:
            reply_text = "\n".join(fixed_urls)
        else:
            # 將原訊息複製一份並替換裡面的網址
            new_content = message.content
            for orig in sorted(replaced_mapping.keys(), key=len, reverse=True):
                fixed = replaced_mapping[orig]
                new_content = new_content.replace(orig, fixed)
            reply_text = new_content

        # 以公開訊息發送修復後的連結
        await interaction.followup.send(
            content=f"🔗 **由 {interaction.user.mention} 幫忙修復的連結：**\n{reply_text}"
        )

async def setup(bot):
    await bot.add_cog(LinkFixer(bot))