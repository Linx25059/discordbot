import os
import aiohttp
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="Douyin Embed Fixer")

async def fetch_video_info(video_id: str) -> dict:
    """
    呼叫自建/公開的 Douyin_TikTok_Download_API 獲取抖音影片的真實資料
    """
    # 支援設定自建 API 位址，預設使用公開備份 API 端點
    api_base = os.getenv("DOUYIN_DOWNLOAD_API_URL", "https://api.douyin.wtf")
    video_url = f"https://www.douyin.com/video/{video_id}"
    api_url = f"{api_base.rstrip('/')}/api/hybrid/video_data?url={video_url}&minimal=false"
    
    try:
        # 由於 Vercel Serverless 每一次呼叫都是獨立的，這裡直接開啟並關閉 ClientSession
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=6) as response:
                if response.status == 200:
                    data = await response.json()
                    video_data = data.get("video_data", {})
                    if video_data:
                        # 優先取用無浮水印影片直鏈 (nwm_video_url)，其次為有浮水印影片 (wm_video_url)
                        nwm_url = video_data.get("nwm_video_url")
                        wm_url = video_data.get("wm_video_url")
                        return {
                            "title": video_data.get("video_title") or f"抖音影片 (ID: {video_id})",
                            "video_url": nwm_url or wm_url,
                            "cover_url": video_data.get("cover_image_url") or "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"
                        }
    except Exception as e:
        print(f"[DouyinAPI] 呼叫下載 API 發生錯誤: {e}")
    return {}

@app.get("/video/{video_id}", response_class=HTMLResponse)
async def get_video_embed(video_id: str, request: Request):
    """
    接收影片 ID，自動向 Douyin_TikTok_Download_API 解析影片資料並渲染為 Open Graph HTML
    """
    # 嘗試抓取真實影片資料
    info = await fetch_video_info(video_id)
    
    title = info.get("title") or f"抖音影片 (ID: {video_id})"
    video_url = info.get("video_url") or "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
    cover_url = info.get("cover_url") or "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"

    # 建立讓 Discord 爬蟲能讀取的標準 Open Graph HTML 網頁
    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    
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
        <video src="{video_url}" poster="{cover_url}" controls autoplay loop style="max-width: 100%; max-height: 80vh; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);"></video>
        <p style="margin-top: 15px; color: #888;">若無法自動播放，請手動點擊影片</p>
    </div>
</body>
</html>
"""
    return html_content
