import os
import json
import threading
import time
import glob
from datetime import datetime

student_logs = {}  # {'001': [ {...}, {...} ]}

def log_message(student_id: str, role: str, content: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if student_id not in student_logs:
        student_logs[student_id] = []
    student_logs[student_id].append({
        "timestamp": timestamp,
        "role": role,
        "content": content
    })

def save_temp_logs():
    os.makedirs("logs", exist_ok=True)
    temp_file = "logs/student_logs_tmp.json"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(student_logs, f, ensure_ascii=False, indent=2)
    print(f"[LOG] 🛟 已保存聊天暫存")

def periodic_save_temp_logs():
    while True:
        save_temp_logs()
        time.sleep(30)

def load_latest_archive():
    os.makedirs("logs", exist_ok=True)
    archive_files = glob.glob("logs/*_student-*.json")
    latest_files = {}

    for path in archive_files:
        filename = os.path.basename(path)
        if "_student-" in filename:
            ts = filename.split("_student-")[0]
            sid = filename.split("_student-")[-1].replace(".json", "")
            if sid not in latest_files or ts > latest_files[sid][0]:
                latest_files[sid] = (ts, path)

    for sid, (_, path) in latest_files.items():
        with open(path, "r", encoding="utf-8") as f:
            logs = json.load(f)
        student_logs[sid] = logs

    if student_logs:
        print(f"[LOG] ✅ 載入最近歸檔聊天記錄，共 {len(student_logs)} 位學生")
    else:
        print(f"[LOG] ⚡ 沒有找到可載入的歷史聊天記錄")

def archive_now():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    os.makedirs("logs", exist_ok=True)
    for sid, logs in student_logs.items():
        filename = f"logs/{timestamp}_student-{sid}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    if student_logs:
        print(f"[LOG] ✅ 已歸檔聊天記錄")
    else:
        print(f"[LOG] ⚡ 沒有聊天記錄需要歸檔")
    student_logs.clear()

def save_summary(student_id: str, summary: str):
    os.makedirs("logs/summaries", exist_ok=True)
    path = f"logs/summaries/summary_{student_id}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"[LOG] 💾 已儲存摘要：{path}")

def load_summary(student_id: str) -> str:
    path = f"logs/summaries/summary_{student_id}.txt"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None

threading.Thread(target=periodic_save_temp_logs, daemon=True).start()
