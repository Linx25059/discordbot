# 🤖 Discord Community Bot (社群多功能機器人)

!Python
!discord.py
!SQLite
!License

本專案為一款基於 `discord.py` 開發的全方位 Discord 機器人，完美整合了 **AI 智慧對話、虛擬經濟與動態股市、音樂播放、多項互動遊戲、自動推播**，以及強大的**伺服器管理與實用工具**。旨在為您的 Discord 社群帶來極致的互動體驗與高效的管理方案。

---

## 🌟 核心功能特色

###  AI 智慧助理 (`ai_chat.py`)
- **強大核心**：串接 Google Gemini 2.5 Flash 模型，支援即時聯網搜尋。
- **多重人格**：支援切換傲嬌、毒舌、貓娘等多種聊天風格 (`/set_persona`)。
- **資源管理**：內建上下文獨立記憶、Token 消耗統計 (`/token_stats`) 與配額監控 (`/quota`)。

### 🏦 經濟與虛擬股市系統 (`economy.py`, `finance.py`)
- **全新銀行系統**：支援現金錢包與銀行存款雙帳戶，存款每日自動產生 1% 利息，並設有全服富豪榜 (`/richest`)。
- **虛擬大盤股市**：內建 15 款特色股票（如：護國神山台積電、滷肉飯指數），價格每小時動態波動。
- **進階金融體驗**：支援買賣持倉分析 (`/portfolio`)、內線消息訂閱、市場即時快訊推播，以及歷史折線圖 (`/stock_history`)。

### 🎮 娛樂與互動遊戲 (`gamble.py`, `fun.py`, `image.py`)
- **皇家 21 點**：支援至多 5 人連線的完整 Blackjack 系統，具備雙倍下注、分牌、投降與黑傑克結算機制。
- **賭場與小遊戲**：內建拉霸機 (`/slots`)、骰子對決 (`/betdice`)、猜硬幣 (`/coinflip`) 與抽獎系統 (`/giveaway`)。
- **惡搞圖片生成**：支援多種大頭貼濾鏡，包含打碼 (`/pixelate`)、黑白遺照 (`/wasted`)、詛咒負片 (`/invert`) 與近視模糊 (`/blur`)，並內建迷因圖產生器 (`/meme`)。

### 🔞 老司機專屬車庫 (`nsfw.py`)
- **熱門網頁爬蟲**：動態爬取 Jable、MissAV、Hanime 等 4 大平台即時熱門榜單。
- **群友互動推播**：專屬的群友投稿推薦 (`/submit_av`)、點讚機制與老司機排行榜 (`/av_top`)。
- **深夜福利專車**：每日深夜指定頻道自動推播精選車牌。

### 🎵 高音質音樂播放 (`music.py`)
- **直覺點播**：支援透過 YouTube 連結或關鍵字直接點播音樂。
- **互動控制面板**：提供播放/暫停、切換下一首、離開頻道及查看待播清單的按鈕 UI。

### 🛠️ 實用工具與伺服器管理 (`admin.py`, `logger.py`, `weather.py`, `link_fixer.py`)
- **社群連結修復**：自動修復 Twitter/X, Instagram, TikTok, Threads 等社群連結，透過 Webhook 保持原發送者外觀。
- **動態語音頻道**：使用者進入特定頻道時自動建立專屬語音空間，閒置時自動銷毀。
- **生活資訊工具**：專屬地點天氣綁定與每日早晨推播 (`/dailyweather`)、餐飲推薦服務 (`/food`)。
- **全方位日誌與回報**：完整記錄訊息刪除、成員進出（追蹤邀請者）、語音頻道動態。內建 Bug 回報工單系統 (Ticket)。
- **一鍵維護**：管理員熱修復 (`!hotfix`) 與環境變數動態更新 (`!update_env`) 功能。

---

##  環境需求

- **Python 3.8+**
- `discord.py` 2.0+
- `google-genai` (Gemini API)
- `yt-dlp` & `PyNaCl` (語音與音樂模組)
- `FFmpeg` (音樂播放必備組件)
- `aiosqlite` / `aiohttp` / `Pillow`

---

## ☁️ Oracle Cloud 虛擬機部署指南 (Ubuntu)

推薦使用 Oracle Cloud (Ubuntu Linux) 作為部署環境。以下為完整的伺服器架設與常駐執行步驟：

### 1. 更新系統並安裝基礎套件
登入虛擬機 (SSH) 後，更新套件清單並安裝 Python 虛擬環境工具、Git 以及 FFmpeg：
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git ffmpeg nodejs npm
```

### 2. 下載專案與建立虛擬環境
將專案複製到虛擬機中，並建立隔離的 Python 虛擬環境以避免套件衝突：
```bash
git clone <你的_GitHub_Repo_網址>
cd <專案資料夾>
python3 -m venv venv
source venv/bin/activate
```

### 3. 安裝 Python 依賴套件
在啟動虛擬環境的狀態下（終端機前方會有 `(venv)` 提示），安裝所需套件：
```bash
pip install -r requirements.txt
```

### 4. 設定環境變數 (.env)
建立並編輯 `.env` 檔案：
```bash
nano .env
```
填入以下資訊（填寫完畢按 `Ctrl+O` 存檔，`Enter` 確認，`Ctrl+X` 離開）：
```env
DISCORD_TOKEN=你的_DISCORD_BOT_TOKEN
GEMINI_API_KEY=你的_GOOGLE_GEMINI_API_KEY
```

### 5. 背景常駐執行 (使用 PM2)
為了確保關閉 SSH 連線後機器人依然穩定運作，我們使用 PM2 來守護進程：
```bash
# 全域安裝 PM2
sudo npm install -g pm2

# 啟動機器人，並綁定虛擬環境中的 Python 解譯器
pm2 start main.py --name discord-bot --interpreter ./venv/bin/python

# 儲存 PM2 狀態並設定開機自動啟動
pm2 save
pm2 startup
```

---

## 💾 資料庫設計
本系統採用輕量級 `SQLite` (`bot_database.db`) 作為資料持久化方案，搭配 `aiosqlite` 實現全域非同步連線操作。系統於首次啟動時，將自動初始化並建立所有核心資料表結構，無須額外架設資料庫伺服器。

## 📄 授權條款 (License)
本專案採用 **MIT License** 開源授權條款。詳細的授權內容與規範請參閱專案根目錄下的 `LICENSE` 檔案。