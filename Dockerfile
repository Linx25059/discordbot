# 1. 指定基礎鏡像：使用輕量級的 Python 環境
FROM python:3.11-slim

# 2. 設定容器內的資料夾路徑
WORKDIR /app

# 3. 複製依賴清單到容器中
COPY requirements.txt .

# 4. 安裝套件
RUN pip install --no-cache-dir -r requirements.txt

# 5. 複製目前資料夾的所有程式碼到容器裡
COPY . .

# 6. 執行機器人
CMD ["python", "main.py"]