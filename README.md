# 🤖 Discord Community Bot (多功能社群機器人)

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-v2.x-blueviolet.svg)](https://github.com/Rapptz/discord.py)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

全方位的 Discord 多功能社群機器人，基於 Python 3 及 `discord.py` 2.x 開發。專注於**高效資訊查詢**、**社群互動**與**伺服器自動化管理**。採用模組化 Cog 架構，支援熱重載（Hot-reload）與非同步 SQLite 資料庫儲存。

---

## ✨ 核心特色與功能模組

### 📢 自動化廣播與訂閱
- **每日熱門新聞** (`/setnews`)：定時推播 Google News RSS 焦點新聞。
- **限時免費遊戲通知** (`/setgames`)：自動抓取並推播 Steam、Epic Games 等平台的最新限免遊戲。
- **自訂自動回覆** (`/addreply`)：支援關鍵字匹配自動回覆對話。
- **動態語音頻道** (`/setupvoice`)：設置「點我建立頻道」，成員進入時自動生成專屬臨時包廂，所有人離開後自動清理。

### 🔗 社群連結修復與嵌入 (Link Fixer)
- **自動修復預覽**：支援將 Twitter/X (`vxtwitter.com`), TikTok (`vxtiktok.com`), Instagram (`ddinstagram.com`), Reddit 等社群連結自動轉譯為具備多媒體預覽卡片的格式。

### 🤖 AI 智能對話與擴充
- **Ollama / LLM 本地 AI 整合**：支援對接本地大語言模型（如 Llama 3、DeepSeek 等），具備思考過程劇透遮罩格式化處理。

### 🌤️ 生活與實用娛樂
- **氣象查詢** (`/weather`)：提供即時天氣、預報查詢與使用者個人預設地點綁定。
- **隨機美食選擇** (`/food`)：解決「今天吃什麼」的難題。
- **圖片處理工具** (`/image`)：支援圖片浮水印、頭貼合成等趣味功能。
- **實用工具集**：包含簡易音樂播放 (`/play`)、音樂查詢、語言翻譯 (`/translate`)、抽獎功能 (`/giveaway`)。

### 🛠️ 伺服器管理與維護
- **一鍵清頻** (`!clear`)、伺服器資訊與 Bot 狀態監控 (`/info`, `/status`)。
- **企業級日誌輪替**：採用 `TimedRotatingFileHandler` 定時輪替日誌，防止 Log 檔案撐爆伺服器。
- **開發者熱重載**：無須重啟 Bot 即可透過 `!reload` 或 `!hotfix` 套用新功能。

---

## ⚙️ 環境變數設定 (`.env`)

在啟動機器人前，請於專案根目錄下建立 `.env` 檔案並設定必要的環境變數：

```env
# 【必填】Discord Bot Token (從 Discord Developer Portal 取得)
DISCORD_TOKEN=your_discord_bot_token_here

# 【選填】AI 聊天模組設定 (若有安裝 Ollama 或本地 LLM API)
OLLAMA_API_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=Formosa-1/Llama-3.2-3B-F1:latest
```

> **📌 注意**：在 [Discord Developer Portal](https://discord.com/developers/applications) 設定機器人時，請確保開啟以下 **Privileged Gateway Intents**：
> - `MESSAGE CONTENT INTENT`
> - `SERVER MEMBERS INTENT`
> - `PRESENCE INTENT`

---

## 📦 安裝與部署方式（依個人需求選擇）

依照您的使用環境與設備，選擇最適合的安裝方式：

### 方式 A：本地原生 Python 運行（適合開發測試與 Windows/Linux/macOS）

1. **確認 Python 版本**：需要 Python 3.10 或以上。
2. **（推薦）建立虛擬環境**：
   ```bash
   # Windows (PowerShell / CMD)
   python -m venv venv
   .\venv\Scripts\activate

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **安裝依賴套件**：
   ```bash
   pip install -r requirements.txt
   ```
4. **安裝系統依賴（音樂功能必備）**：
   若需使用音樂功能（`/play`），請在系統中安裝 **FFmpeg** 並將其加入系統環境變數中：
   - **Windows**: 使用 `choco install ffmpeg` 或自 `ffmpeg.org` 下載設定 PATH。
   - **Ubuntu/Debian**: `sudo apt install ffmpeg`
   - **macOS**: `brew install ffmpeg`
5. **啟動機器人**：
   ```bash
   python main.py
   ```

---

### 方式 B：Docker 容器化部署（適合 24H 伺服器 / NAS / VPS）

專案內建 `Dockerfile`，且已自動打包 `ffmpeg` 與所需的 Python 依賴環境，省去環境配置麻煩。

1. **建置 Docker 鏡像**：
   ```bash
   docker build -t discord-bot:latest .
   ```
2. **啟動 Docker 容器**：
   ```bash
   docker run -d \
     --name my-discord-bot \
     --restart unless-stopped \
     -v $(pwd)/.env:/app/.env \
     -v $(pwd)/bot_database.db:/app/bot_database.db \
     discord-bot:latest
   ```

---

### 方式 C：PM2 進程管理（適合 Linux 獨立背景服務）

若在 Linux VPS 上運行且不習慣 Docker，可使用 `pm2` 確保機器人在崩潰或開機時自動重啟：

1. **安裝 PM2**（需 Node.js）：
   ```bash
   npm install -g pm2
   ```
2. **使用 PM2 啟動**：
   ```bash
   pm2 start main.py --name "discord-bot" --interpreter ./venv/bin/python
   pm2 save
   pm2 startup
   ```

---

## ⚡ 斜線指令同步（重要）

Discord API 限制了斜線指令的同步頻率，機器人預設**不會在啟動時自動強制同步全域指令**。

在 Bot 啟動並加入伺服器後，請由**機器人擁有者**在 Discord 頻道中輸入以下文字指令：

- `!sync here`：**【推薦測試使用】** 立即同步目前所在的伺服器指令（按 `Ctrl + R` 或重新整理 Discord 即可馬上使用）。
- `!sync`：同步全域 (Global) 斜線指令（可能需要最長 1 小時生效）。
- `!sync clear`：清除當前伺服器的專屬舊指令（修復指令選單重複或異常時使用）。

---

## 🛡️ 開發者維護與熱重載指令

伺服器管理者與 Bot 擁有者可使用以下指令進行現場維護與無中斷更新：

| 指令 | 權限要求 | 功能說明 |
| --- | --- | --- |
| `!sync [scope]` | 機器人擁有者 | 手動同步斜線指令（`here`, `clear`, `clear_global`） |
| `!update_env <KEY> <VALUE>` | 機器人擁有者 | 動態更新並保存 `.env` 環境變數 |
| `!reload <module>` | 管理員/擁有者 | 熱重載單一 Cog 模組（例如 `!reload cogs.weather`） |
| `!hotfix` | 管理員/擁有者 | 一鍵重新載入所有 Cogs 並自動同步指令 |
| `!shutdown` | 機器人擁有者 | 優雅關閉 Bot 並釋放 SQLite 與 HTTP 連線資源 |

---

## 📂 專案結構說明

```
├── cogs/                # 各功能模組 (Commands / Cog Extensions)
│   ├── admin.py         # 伺服器管理與廣播設置
│   ├── ai_chat.py       # 本地 LLM/Ollama 聊天對接
│   ├── auto_reply.py    # 關鍵字自動回覆
│   ├── auto_voice.py    # 動態語音頻道
│   ├── broadcast.py     # 熱門新聞與限免遊戲定時推播
│   ├── link_fixer.py    # 社群媒體連結修復與預覽
│   ├── weather.py       # 天氣預報與地點綁定
│   └── ...              # 其他功能 (music, food, fun, help, etc.)
├── services/            # 外部 API 與 RSS 邏輯服務
│   ├── news_service.py  # Google News RSS 抓取
│   └── game_service.py  # GamerPower 免費遊戲 API
├── utils/               # 工具類別
│   └── db_manager.py    # SQLite 資料庫 CRUD 管理
├── main.py              # 機器人啟動核心與生命週期託管
├── Dockerfile           # Docker 容器打包設定
├── requirements.txt     # Python 依賴清單
└── README.md            # 專案說明文件
```

---

## 📄 授權條款 (License)

本專案採用 [MIT License](LICENSE) 條款開源授權。