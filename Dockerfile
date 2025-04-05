FROM python:3.11-slim

# 安裝依賴
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY . .

# 預設執行指令
CMD ["python", "bot.py"]
