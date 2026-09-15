import os
import re
import aiohttp
import asyncio
import yt_dlp
import logging
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager

async def verify_api_key(x_api_key: str | None = Header(None)):
    """如果環境變數設定了 DOUYIN_API_KEY，則進行 X-API-Key 驗證」"""
    required_key = os.getenv("DOUYIN_API_KEY")
    if required_key and x_api_key != required_key:
        raise HTTPException(status_code=403, detail="Invalid or missing X-API-Key header")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 全域託管 ClientSession 連線池
    app.state.session = aiohttp.ClientSession()
    yield
    if not app.state.session.closed:
        await app.state.session.close()

app = FastAPI(title="Douyin Embed Fixer", lifespan=lifespan, dependencies=[Depends(verify_api_key)])

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Douyin Embed Fixer API",
        "message": "API 正常運行中！請透過 /video/{video_id} 存取抖音嵌入服務。"
    }

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
        logger.error(f"[DouyinAPI] 獲取 ttwid 失敗: {e}")
    return None

async def fetch_aweme_detail(video_id: str, session: aiohttp.ClientSession | None = None) -> dict | None:
    """
    備用解析：當 yt-dlp 或 ttwid 失敗時，直接調用抖音官方 Web API (Aweme Detail)
    """
    url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    }
    
    async def _request(sess: aiohttp.ClientSession):
        try:
            async with sess.get(url, headers=headers, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("item_list", [])
                    if items:
                        item = items[0]
                        title = item.get("desc") or f"抖音影片 (ID: {video_id})"
                        
                        # 封面圖
                        video_info = item.get("video", {})
                        cover_list = video_info.get("cover", {}).get("url_list", [])
                        cover_url = cover_list[0] if cover_list else "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"
                        
                        # 播放連結
                        play_addr = video_info.get("play_addr", {}).get("url_list", [])
                        raw_video_url = play_addr[0].replace("playwm", "play") if play_addr else None
                        
                        video_id_key = None
                        if raw_video_url:
                            match = re.search(r'video_id=([a-zA-Z0-9_]+)', raw_video_url)
                            if match:
                                video_id_key = match.group(1)
                                
                        video_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={video_id_key}&.mp4" if video_id_key else raw_video_url
                        
                        return {
                            "title": title,
                            "video_url": video_url,
                            "cover_url": cover_url,
                            "video_id_key": video_id_key
                        }
        except Exception as e:
            logger.error(f"[DouyinAPI] Aweme Detail 備用解析失敗: {e}")
        return None

    if session and not session.closed:
        return await _request(session)
    else:
        async with aiohttp.ClientSession() as temp_sess:
            return await _request(temp_sess)

async def extract_douyin_video(video_id: str, session: aiohttp.ClientSession | None = None) -> dict:
    """
    使用 yt-dlp 擷取影片真實資訊與可外連的無浮水印 API 播放連結，失敗時降級使用 Aweme Detail API
    """
    url = f"https://www.douyin.com/video/{video_id}"
    
    # 優先從環境變數讀取靜態 ttwid Cookie，若沒有則嘗試動態註冊
    ttwid = os.getenv("DOUYIN_COOKIE_TTWID")
    if not ttwid:
        if session:
            ttwid = await get_ttwid(session)
        else:
            async with aiohttp.ClientSession() as temp_session:
                ttwid = await get_ttwid(temp_session)
            
    if not ttwid:
        logger.warning("[DouyinAPI] 無法取得 ttwid，嘗試切換至 Aweme Detail 備用 API 解析。")
        fallback_res = await fetch_aweme_detail(video_id, session=session)
        if fallback_res:
            return fallback_res
        return {"error": "Failed to acquire ttwid cookie and fallback API failed"}

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
            logger.warning("[DouyinAPI] yt-dlp 回傳空數據，切換至 Aweme Detail 備用 API 解析。")
            fallback_res = await fetch_aweme_detail(video_id, session=session)
            if fallback_res:
                return fallback_res
            return {"error": "yt-dlp returned empty info"}
            
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
            "cover_url": thumbnail,
            "video_id_key": video_id_key
        }
    except Exception as e:
        err_msg = str(e)
        logger.error(f"[DouyinAPI] yt-dlp 解析失敗: {err_msg}，嘗試切換至 Aweme Detail 備用 API 解析。")
        fallback_res = await fetch_aweme_detail(video_id, session=session)
        if fallback_res:
            return fallback_res
        return {"error": err_msg}

@app.get("/video/{video_id}", response_class=HTMLResponse)
async def get_video_embed(video_id: str, request: Request):
    """
    接收影片 ID，透過 yt-dlp 本地解析並組裝出免防盜鏈的播放連結，回傳供 Discord 內置播放的 HTML
    """
    session = getattr(request.app.state, 'session', None)
    info = await extract_douyin_video(video_id, session=session)
    
    if not info or "error" in info:
        err_msg = info.get("error") if info else "Unknown extraction error"
        headers = {
            "X-Debug-Error": err_msg,
            "X-Debug-Ttwid-Preset": "Yes" if os.getenv("DOUYIN_COOKIE_TTWID") else "No"
        }
        # 解析失敗時，直接重導向回官方抖音網址，在 Header 中夾帶錯誤訊息以便除錯
        return RedirectResponse(url=f"https://www.douyin.com/video/{video_id}", headers=headers)
        
    title = info.get("title")
    cover_url = info.get("cover_url")
    
    # 優先使用 Vercel 的串流代理，避免 Discord 存取抖音 CDN 遇到 403 阻擋
    video_id_key = info.get("video_id_key")
    if video_id_key:
        # ⚠️ 【關鍵修正】在串流網址末端加上 .mp4，使 Discord 的 Open Graph 爬蟲能正確識別為直鏈影片並渲染播放器
        clean_key = video_id_key.removesuffix(".mp4")
        video_url = f"{str(request.base_url).rstrip('/')}/video/stream/{clean_key}.mp4"
    else:
        video_url = info.get("video_url")

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
    <meta property="og:video:url" content="{video_url}">
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
        <h2 style="font-size: 1.2rem; margin-bottom: 15px;">{title}</h2>
        <!-- 關鍵修正：加入 playsinline, webkit-playsinline 與 muted 屬性，確保 iOS Safari 及 Android 行動裝置允許播放 -->
        <video src="{video_url}" poster="{cover_url}" referrerpolicy="no-referrer" controls autoplay muted loop playsinline webkit-playsinline style="max-width: 100%; max-height: 75vh; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);"></video>
        <p style="margin-top: 15px; color: #888; font-size: 0.85rem;">若無法自動播放，請手動點擊影片播放</p>
    </div>
</body>
</html>
"""
    headers = {
        "X-Debug-Status": "Success",
        "X-Debug-Ttwid-Preset": "Yes" if os.getenv("DOUYIN_COOKIE_TTWID") else "No"
    }
    return HTMLResponse(content=html_content, headers=headers)


@app.get("/video/stream/{video_id_key}")
async def stream_video(video_id_key: str, request: Request):
    """
    代理影片串流，支援 HTTP Byte-Range (206 Partial Content) 傳輸，確保 iOS Safari 及行動裝置瀏覽器順暢播放
    """
    clean_key = video_id_key.removesuffix(".mp4")
    video_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={clean_key}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    }
    
    # 傳遞行動裝置所需的 Range 標頭 (如 bytes=0-1)
    range_header = request.headers.get("Range")
    if range_header:
        headers["Range"] = range_header
        
    ttwid = os.getenv("DOUYIN_COOKIE_TTWID")
    if ttwid:
        headers["Cookie"] = f"ttwid={ttwid}"
        
    session: aiohttp.ClientSession | None = getattr(request.app.state, 'session', None)
    
    async def fetch_stream(sess: aiohttp.ClientSession):
        resp = await sess.get(video_url, headers=headers, allow_redirects=True)
        resp_status = resp.status
        resp_headers = {}
        for h in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
            val = resp.headers.get(h)
            if val:
                resp_headers[h] = val
        if "Content-Type" not in resp_headers:
            resp_headers["Content-Type"] = "video/mp4"
        if "Accept-Ranges" not in resp_headers:
            resp_headers["Accept-Ranges"] = "bytes"

        async def video_generator():
            try:
                async for chunk, _ in resp.content.iter_chunks():
                    yield chunk
            finally:
                resp.close()

        return StreamingResponse(
            video_generator(),
            status_code=resp_status if resp_status in (200, 206) else 200,
            headers=resp_headers,
            media_type="video/mp4"
        )

    if session and not session.closed:
        return await fetch_stream(session)
    else:
        async with aiohttp.ClientSession() as temp_session:
            return await fetch_stream(temp_session)
