from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="Douyin Embed Fixer")

@app.get("/video/{video_id}", response_class=HTMLResponse)
async def get_video_embed(video_id: str, request: Request):
    """
    接收影片 ID，渲染出包含 Open Graph 標籤的 HTML 網頁
    """
    
    # =========================================================================
    # ⚠️ 【預留區塊】未來可以在此串接第三方或自建的「抖音去浮水印解析 API」
    # 範例邏輯：
    #   async with aiohttp.ClientSession() as session:
    #       async with session.get(f"https://api.example.com/douyin?id={video_id}") as r:
    #           data = await r.json()
    #           video_url = data["video_url"]
    #           title = data["title"]
    #           cover_url = data["cover_url"]
    # =========================================================================
    
    # 目前使用假資料 (Dummy Data) 進行 HTML 渲染測試
    title = f"抖音影片 (ID: {video_id})"
    cover_url = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500" # 範例封面圖
    # 使用網路上公開的測試 MP4 影片連結
    video_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

    # 建立讓 Discord 爬蟲能讀取的標準 Open Graph HTML 網頁
    # 為了讓影片能在 Discord 內聯直接播放，必須設定 og:video 與 twitter:player:stream
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
