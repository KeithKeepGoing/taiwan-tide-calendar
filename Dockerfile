FROM python:3.11-slim

WORKDIR /app

# 安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY tide_calendar.py server.py ./

# 建立快取目錄
RUN mkdir -p /app/cache

# 設定環境變數
ENV PORT=5000
ENV CACHE_DIR=/app/cache
ENV CACHE_TTL_HOURS=6

EXPOSE 5000

CMD ["python", "server.py"]
