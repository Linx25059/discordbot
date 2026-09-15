# 1. 指定基礎鏡像：使用輕量級 Python 3.11
FROM python:3.11-slim

# 2. 安裝系統級音訊依賴 (ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 3. 設定容器內的資料夾路徑
WORKDIR /app

# 4. 建立非 root 安全使用者
RUN useradd -m -u 1000 appuser

# 5. 複製依賴清單並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. 複製專案程式碼並轉交權限
COPY --chown=appuser:appuser . .

# 7. 切換至非 root 使用者執行
USER appuser

# 8. 啟動機器人
CMD ["python", "main.py"]