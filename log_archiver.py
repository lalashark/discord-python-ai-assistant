import os
import json
import threading
import time
from datetime import datetime

# 學生聊天紀錄暫存（全域）
student_logs = {}  # e.g., {'001': [{'timestamp': ..., 'role': ..., 'content': ...}, ...]}

# ✅ 每次訊息傳入時，將記錄寫入 student_logs

def log_message(student_id: str, role: str, content: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if student_id not in student_logs:
        student_logs[student_id] = []
    student_logs[student_id].append({
        "timestamp": timestamp,
        "role": role,
        "content": content
    })

# ✅ 背景執行：每週將 logs 寫入檔案歸檔

def archive_logs():
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        os.makedirs("logs", exist_ok=True)
        for sid, logs in student_logs.items():
            filename = f"logs/{timestamp}_student-{sid}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        student_logs.clear()
        print(f"[LOG] ✅ 已歸檔於 {timestamp}")
        time.sleep(7 * 24 * 60 * 60)  # 每週執行一次（7 天）

# ✅ 啟動背景執行緒
threading.Thread(target=archive_logs, daemon=True).start()
