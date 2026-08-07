import os
import re
import aiohttp
import asyncio
import yt_dlp
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="Douyin Embed Fixer")

async def get_ttwid(session: aiohttp.ClientSession) -> str | None:
    """
    動態註冊並獲取抖音的 ttwid cookie，以繞過安全驗證頁面
    """
    url = "https://ttwid.bytedance.com/ttwid/union/register/"
    payload = {
        "region": "cn",
        "aid": 1768,
        "needFid": False,
        "service": "www.ixigua.com",
        "migrate_info": {"ticket": "", "source": "node"},
        "cbUrlProtocol": "https",
        "union": True
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with session.post(url, json=payload, headers=headers) as response:
            set_cookie = response.headers.get("Set-Cookie", "")
            if "ttwid=" in set_cookie:
                return set_cookie.split("ttwid=")[1].split(";")[0]
    except Exception as e:
        print(f"[DouyinAPI] 獲取 ttwid 失敗: {e}")
    return None

async def extract_douyin_video(video_id: str) -> dict:
    """
    使用 yt-dlp 擷取影片真實資訊與可外連的無浮水印 API 播放連結
    """
    url = f"https://www.douyin.com/video/{video_id}"
    
    # 優先從環境變數讀取靜態 ttwid Cookie，若沒有則嘗試動態註冊
    ttwid = os.getenv("DOUYIN_COOKIE_TTWID")
    if not ttwid:
        async with aiohttp.ClientSession() as session:
            ttwid = await get_ttwid(session)
            
    if not ttwid:
        print("[DouyinAPI] 無法取得 ttwid，跳過解析。")
        return {}

    # 設定 yt-dlp 參數
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'nocachedir': True,  # 停用快取寫入以避免 Vercel 唯讀檔案系統報錯
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.douyin.com/',
            'Cookie': f'ttwid={ttwid}'
        }
    }
    
    loop = asyncio.get_event_loop()
    try:
        def extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
                
        info = await loop.run_in_executor(None, extract)
        if not info:
            return {}
            
        title = info.get('title') or f"抖音影片 (ID: {video_id})"
        thumbnail = info.get('thumbnail') or "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"
        
        # 4. 從影片格式列表中提取出 Bytedance 影片的 video_id 金鑰
        video_id_key = None
        formats = info.get('formats', [])
        for fmt in formats:
            fmt_url = fmt.get('url')
            if fmt_url:
                match = re.search(r'video_id=([a-zA-Z0-9_]+)', fmt_url)
                if match:
                    video_id_key = match.group(1)
                    break
                    
        if video_id_key:
            # ⚠️ 【關鍵修正】在網址後方加上 &.mp4 偽參數，誘導 Discord 爬蟲識別為直鏈影片進行內置播放渲染
            video_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={video_id_key}&.mp4"
        else:
            # 備用：若無法擷取金鑰，使用 yt-dlp 預設格式
            video_url = info.get('url')
            
        return {
            "title": title,
            "video_url": video_url,
            "cover_url": thumbnail
        }
    except Exception as e:
        print(f"[DouyinAPI] yt-dlp 解析失敗: {e}")
    return {}

@app.get("/video/{video_id}", response_class=HTMLResponse)
async def get_video_embed(video_id: str, request: Request):
    """
    接收影片 ID，透過 yt-dlp 本地解析並組裝出免防盜鏈的播放連結，回傳供 Discord 內置播放的 HTML
    """
    info = await extract_douyin_video(video_id)
    
    title = info.get("title") or f"抖音影片 (ID: {video_id})"
    video_url = info.get("video_url") or "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
    cover_url = info.get("cover_url") or "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"

    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    
    <!-- 宣告瀏覽器與爬蟲不發送 Referer 標頭，以完美繞過抖音 CDN 的防盜鏈阻擋 -->
    <meta name="referrer" content="no-referrer">
    
    <!-- 核心 Discord/Facebook Open Graph 標籤 -->
    <meta property="og:site_name" content="Douyin Fixer">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="點擊直接在 Discord 內嵌播放影片！">
    <meta property="og:type" content="video.other">
    <meta property="og:image" content="{cover_url}">
    
    <!-- 影片直接串流位址 (重要：必須指向直鏈 .mp4，且為 HTTPS) -->
    <meta property="og:video" content="{video_url}">
    <meta property="og:video:secure_url" content="{video_url}">
    <meta property="og:video:type" content="video/mp4">
    <meta property="og:video:width" content="720">
    <meta property="og:video:height" content="1280">

    <!-- Twitter Card / Discord 播放器渲染所需標籤 -->
    <meta name="twitter:card" content="player">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="點擊直接播放影片">
    <meta name="twitter:image" content="{cover_url}">
    <meta name="twitter:player" content="{video_url}">
    <meta name="twitter:player:width" content="720">
    <meta name="twitter:player:height" content="1280">
    <meta name="twitter:player:stream" content="{video_url}">
    <meta name="twitter:player:stream:content_type" content="video/mp4">
</head>
<body style="background-color: #121212; color: white; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;">
    <div style="text-align: center; padding: 20px;">
        <h2>{title}</h2>
        <!-- 加入 referrerpolicy="no-referrer" 屬性確保播放器請求不發送 referer -->
        <video src="{video_url}" poster="{cover_url}" referrerpolicy="no-referrer" controls autoplay loop style="max-width: 100%; max-height: 80vh; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);"></video>
        <p style="margin-top: 15px; color: #888;">若無法自動播放，請手動點擊影片</p>
    </div>
</body>
</html>
"""
    return html_content
