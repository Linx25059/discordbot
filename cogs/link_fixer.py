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
        self.debug_mode = False
        # 建立正則表達式，用來抓取訊息中的任何可能網址
        self.url_pattern = re.compile(r'(https?://[^\s>\|]+)')
        
        # 註冊右鍵選單指令，支援個人安裝 (User-Installable) 應用程式在所有伺服器使用
        self.ctx_menu = app_commands.ContextMenu(
            name='修復訊息中的連結',
            callback=self.fix_links_ctx
        )

    async def cog_load(self):
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        # 卸載 Cog 時移除右鍵選單指令
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @commands.command(name="linkfix_debug")
    @commands.has_permissions(administrator=True)
    async def toggle_debug(self, ctx):
        self.debug_mode = not self.debug_mode
        status = "開啟" if self.debug_mode else "關閉"
        await ctx.send(f"🔧 連結修復除錯模式已 {status}。")

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

    async def resolve_douyin_url(self, url: str, debug_channel=None) -> str | None:
        """
        將抖音的短網址或標準網址轉換為中繼端網址，支援非同步跳轉追蹤與全網域識別
        """
        async def send_debug(msg):
            if debug_channel:
                await debug_channel.send(f"🔍 [Douyin Debug] {msg}")

        try:
            await send_debug(f"開始解析網址: `{url}`")
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            path = parsed.path
            
            domain = netloc
            if domain.startswith('www.'):
                domain = domain[4:]
                
            proxy_base = os.getenv("DOUYIN_PROXY_BASE_URL", "https://discordbot-six-gamma.vercel.app")
            await send_debug(f"解析網址基本資訊: domain=`{domain}`, path=`{path}`, query=`{parsed.query}`")

            # A. 處理短網址 v.douyin.com
            if domain == 'v.douyin.com' or 'v.douyin.com' in url:
                await send_debug("偵測到 v.douyin.com 短網址，開始發送追蹤跳轉請求...")
                headers = {
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
                }
                
                # 安全獲取 aiohttp session
                session = getattr(self.bot, 'session', None)
                async def _do_get(s: aiohttp.ClientSession):
                    # 允許跳轉以獲取最終網址
                    async with s.get(url, headers=headers, allow_redirects=True, timeout=a_timeout) as response:
                        return response.status, str(response.url), response.headers
                
                a_timeout = aiohttp.ClientTimeout(total=6)
                try:
                    if session and not session.closed:
                        status, final_url, resp_headers = await _do_get(session)
                    else:
                        async with aiohttp.ClientSession() as temp_sess:
                            status, final_url, resp_headers = await _do_get(temp_sess)
                except Exception as req_err:
                    await send_debug(f"跳轉請求異常: {req_err}")
                    return None

                await send_debug(f"跳轉成功，最終網址為: `{final_url}`")
                
                # 1. 優先從跳轉後的網址尋找影片 /video/{id} 或 /share/video/{id}
                id_match = re.search(r'/(?:video|share/video)/(\d+)', final_url)
                if id_match:
                    video_id = id_match.group(1)
                    fixed = f"{proxy_base.rstrip('/')}/video/{video_id}"
                    await send_debug(f"成功提取影片 ID: `{video_id}`，生成修復連結: `{fixed}`")
                    return fixed
                    
                # 2. 尋找圖集/筆記 /note/{id} 或 /share/note/{id}
                note_match = re.search(r'/(?:note|share/note)/(\d+)', final_url)
                if note_match:
                    video_id = note_match.group(1)
                    fixed = f"{proxy_base.rstrip('/')}/video/{video_id}"
                    await send_debug(f"成功提取圖集 ID: `{video_id}`，生成修復連結: `{fixed}`")
                    return fixed

                # 3. 尋找彈窗 /?modal_id={id}
                modal_match = re.search(r'modal_id=(\d+)', final_url)
                if modal_match:
                    video_id = modal_match.group(1)
                    fixed = f"{proxy_base.rstrip('/')}/video/{video_id}"
                    await send_debug(f"成功提取 modal_id: `{video_id}`，生成修復連結: `{fixed}`")
                    return fixed
                    
                # 4. 全能降級方案：尋找 URL 中的任何 18-19 位數字金鑰 (抖音 Standard Aweme ID)
                digit_match = re.search(r'(\d{18,19})', final_url)
                if digit_match:
                    video_id = digit_match.group(1)
                    fixed = f"{proxy_base.rstrip('/')}/video/{video_id}"
                    await send_debug(f"透過備用長數值匹配成功提取 ID: `{video_id}`，生成修復連結: `{fixed}`")
                    return fixed

                await send_debug("未能在跳轉後的網址中找到影片 ID。")
                        
            # B. 處理標準網頁版網址 douyin.com, iesdouyin.com 等
            elif 'douyin.com' in domain or 'iesdouyin.com' in domain:
                await send_debug("偵測到 douyin 網域網址。")
                # 1. 匹配影片/圖集/分享路徑
                id_match = re.search(r'/(?:video|note|share/video|share/note)/(\d+)', url)
                if id_match:
                    video_id = id_match.group(1)
                    fixed = f"{proxy_base.rstrip('/')}/video/{video_id}"
                    await send_debug(f"成功匹配標準路徑，提取影片 ID: `{video_id}`，生成修復連結: `{fixed}`")
                    return fixed
                
                # 2. 匹配 modal_id 參數
                modal_match = re.search(r'modal_id=(\d+)', url)
                if modal_match:
                    video_id = modal_match.group(1)
                    fixed = f"{proxy_base.rstrip('/')}/video/{video_id}"
                    await send_debug(f"成功匹配 modal_id: `{video_id}`，生成修復連結: `{fixed}`")
                    return fixed

                # 3. 備用全能 18-19 位數匹配
                digit_match = re.search(r'(\d{18,19})', url)
                if digit_match:
                    video_id = digit_match.group(1)
                    fixed = f"{proxy_base.rstrip('/')}/video/{video_id}"
                    await send_debug(f"透過數值備用匹配提取 ID: `{video_id}`，生成修復連結: `{fixed}`")
                    return fixed

                await send_debug(f"未能在 douyin 網址中提取出影片 ID。")
            else:
                await send_debug(f"該網址不屬於抖音網域: `{domain}`")
        except Exception as e:
            logger.warning(f"解析抖音網址時發生錯誤: {e}")
            await send_debug(f"解析過程發生異常: {e}")
        return None

    async def process_content_links(self, content: str, channel=None) -> tuple[str, list[str]]:
        """
        核心解析介面：對字串內容中的所有網址進行解析與替換，回傳 (new_content, fixed_urls)
        """
        urls = self.url_pattern.findall(content)
        if not urls:
            return content, []

        fixed_urls = []
        replaced_mapping = {}

        for url in urls:
            fixed = await self.resolve_threads_share_url(url)
            if not fixed:
                fixed = await self.resolve_douyin_url(url, debug_channel=channel if self.debug_mode else None)
            if not fixed:
                fixed = self.fix_single_url(url)
                
            if fixed:
                fixed_urls.append(fixed)
                replaced_mapping[url] = fixed

        if not replaced_mapping:
            return content, []

        is_douyin_share = any(
            ('v.douyin.com' in u or 'douyin.com' in u) and
            any(kw in content for kw in ['复制此链接', '打开Dou音', '打开抖音', 'Jvs:/', '復制此鏈接', '打開Dou音', '長按複製'])
            for u in urls
        )

        if is_douyin_share:
            new_content = "\n".join(fixed_urls)
        else:
            new_content = content
            for orig in sorted(replaced_mapping.keys(), key=len, reverse=True):
                new_content = new_content.replace(orig, replaced_mapping[orig])

        return new_content, fixed_urls

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not self.url_pattern.search(message.content):
            return

        new_content, fixed_urls = await self.process_content_links(message.content, message.channel)
        if not fixed_urls:
            return

        try:
            webhook_channel = message.channel.parent if isinstance(message.channel, discord.Thread) else message.channel
            webhooks = await webhook_channel.webhooks()
            webhook = discord.utils.get(webhooks, user=self.bot.user) or await webhook_channel.create_webhook(name="LinkFixer")

            files = [await attachment.to_file() for attachment in message.attachments]
            send_kwargs = {
                "content": new_content,
                "username": message.author.display_name,
                "avatar_url": message.author.display_avatar.url,
                "files": files
            }
            if isinstance(message.channel, discord.Thread):
                send_kwargs["thread"] = message.channel

            await webhook.send(**send_kwargs)
            await message.delete()

        except discord.Forbidden:
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
        if not self.url_pattern.search(message.content):
            await interaction.response.send_message("❌ 這則訊息中沒有偵測到任何網址喔！", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)
        reply_text, fixed_urls = await self.process_content_links(message.content, interaction.channel)

        if not fixed_urls:
            await interaction.followup.send("❌ 這則訊息中的網址不需要修復，或是不支援修復喔！", ephemeral=True)
            return

        await interaction.followup.send(
            content=f"🔗 **由 {interaction.user.mention} 幫忙修復的連結：**\n{reply_text}"
        )

async def setup(bot):
    await bot.add_cog(LinkFixer(bot))