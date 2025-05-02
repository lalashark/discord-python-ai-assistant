# ✅ main.py（完整版本，保留新版記憶 + 原本關機歸檔與摘要功能）
import os
import time
import signal
from dotenv import load_dotenv
import discord
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.chat_history import InMemoryChatMessageHistory
from log_archiver import (
    log_message, archive_now, load_latest_archive,
    student_logs, save_summary, load_summary
)
import re
import json

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

load_latest_archive()

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

user_sessions = {}

DEFAULT_PROMPT = (
    "必須使用中文"
    "你有對學生過往的提問紀錄，可以參考這些上下文來判斷本次回覆。\n"
    "你是一位精簡且專業的 Python 助教，請針對學生問題給出直接、有效的提示，"
    "避免贅詞，鼓勵學生自行思考與查詢，必要時提供專業術語與實例。\n\n"
    "請將回覆控制在 5~8 行以內、總長度不超過 6 段，避免冗長描述。整體回覆請壓在 450 tokens 以內。\n"
    "如果包含程式碼，請使用 ```python 區塊呈現，且只提供一個簡潔範例，並以 ``` 結束。\n"
    "🔹 如果學生的輸入是一個問題，請依照他程度給出合適的解釋。\n"
    "🔹 若學生使用 `XXX -e` 這種格式，請提供一個相關範例並簡要說明其用途。\n"
    "請確保語氣清晰、回應有層次。"
)

LOW_ACHIEVER_PROMPT = (
    "必須使用中文"
    "你有對學生過往的提問紀錄，可以參考這些上下文來判斷本次回覆。\n"
    "你是一位非常有耐心且善於引導的 Python 助教，面對基礎尚未扎實的學生，"
    "請避免直接給出答案，並以簡單舉例與提問的方式幫助學生思考，"
    "例如生活化比喻、反問、循序漸進的解釋方式，建立信心與理解力。\n\n"
    "請將回覆控制在 5~8 行以內、總長度不超過 6 段，避免冗長描述。整體回覆請壓在 450 tokens 以內。\n"
    "如果包含程式碼，請使用 ```python 區塊呈現，且只提供一個簡潔範例，並以 ``` 結束。\n"
    "🔹 如果學生輸入的是一段 Python 程式碼，請不要立刻解釋，"
    "而是詢問學生希望從以下哪個方向獲得幫助，並請他選擇對應的數字：\n"
    "1️⃣ 邏輯解釋\n2️⃣ 語法說明\n3️⃣ 換個寫法\n4️⃣ 加上註解\n5️⃣ 程式碼檢查\n"
    "請等待學生回覆數字後再依指令進行。\n\n"
    "🔹 如果學生的輸入是一個問題，請用簡單比喻或分段說明幫助他理解。\n"
    "🔹 若學生使用 `XXX -e` 這種格式，請提供一個相關範例並用白話解釋其用途。"
)

def get_system_prompt(student_level: str) -> str:
    return LOW_ACHIEVER_PROMPT if student_level == "02" else DEFAULT_PROMPT

def preprocess_message(message: str) -> str:
    message = message.replace('\u3000', ' ')
    if message.endswith(" -e"):
        topic = message[:-3].strip()
        return f"請舉一個 Python 中「{topic}」 的使用範例，並說明它的用途。"
    return message

def semantic_split(text, limit=1800):
    if len(text) <= limit:
        return [text]
    blocks = re.split(r'(?<=[。！？!?.])', text)
    chunks, current = [], ''
    for b in blocks:
        if len(current) + len(b) < limit:
            current += b
        else:
            if '```' in current and current.count('```') % 2 != 0:
                current += '\n```\n'
            chunks.append(current.strip())
            current = b
    if current:
        if '```' in current and current.count('```') % 2 != 0:
            current += '\n```\n'
        chunks.append(current.strip())
    return chunks

def get_runnable(student_id: str, prompt: str):
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-2.0-flash",
        temperature=0.7,
        google_api_key=GOOGLE_API_KEY,
        max_output_tokens=450
    )
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", prompt),
        MessagesPlaceholder("history"),
        ("human", "{input}")
    ])
    chain = chat_prompt | llm

    def history_store(session_id):
        if session_id not in user_sessions:
            chat_history = InMemoryChatMessageHistory()
            sid = session_id.replace("student-", "")
            if sid in student_logs:
                for entry in student_logs[sid]:
                    role = entry["role"]
                    content = entry["content"]
                    if role == "student":
                        chat_history.add_user_message(content)
                    elif role == "ai":
                        chat_history.add_ai_message(content)
            user_sessions[session_id] = chat_history
        return user_sessions[session_id]

    return RunnableWithMessageHistory(
        chain,
        lambda session_id: history_store(session_id),
        input_messages_key="input",
        history_messages_key="history"
    )


@client.event
async def on_ready():
    print(f"✅ 助教上線囉！Logged in as {client.user}")

last_message_time = {}

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    channel_id = message.channel.id
    now = time.time()

    if channel_id in last_message_time and now - last_message_time[channel_id] < 1:
        await message.channel.send("⚠️ 請稍等一下再發送訊息喔！")
        return

    last_message_time[channel_id] = now

    channel_name = message.channel.name
    parts = channel_name.split("-")

    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        await message.channel.send("⚠️ 頻道名稱應為『學號-等級』格式，例如 `10531-01`")
        return

    student_id = parts[0]
    student_level = parts[1]
    content = message.content.strip()
    processed = preprocess_message(content)

    # 測試指令：強制摘要
    if content == "-summarize":
        update_summary_if_needed(student_id)
        await message.channel.send("✅ 已手動觸發摘要")
        return

    session_id = f"student-{student_id}"
    prompt = get_system_prompt(student_level)
    chat = get_runnable(student_id, prompt)
    log_message(student_id, "student", content)

    try:
        response = await chat.ainvoke({"input": processed}, config={"configurable": {"session_id": session_id}})
        text = response.content if hasattr(response, "content") else str(response)
        log_message(student_id, "ai", text)

        for part in semantic_split(text):
            await message.channel.send(part)

        update_summary_if_needed(student_id)

    except Exception as e:
        await message.channel.send(f"⚠️ 發生錯誤：{e}")
        raise e
# 🧠 概要產生
def update_summary_if_needed(student_id: str):
    session_id = f"student-{student_id}"
    history_obj = user_sessions.get(session_id)

    if not history_obj:
        print(f"[DEBUG] ❌ 找不到記憶體：{session_id}")
        return

    history = history_obj.messages
    print(f"[DEBUG] 🧠 嘗試為 student {student_id} 產生摘要，訊息數：{len(history)}")

    if len(history) > 12:
        print(f"[DEBUG] ✅ 訊息數符合條件，開始摘要前段對話")
        try:
            text_history = []
            for msg in history[:-10]:
                if isinstance(msg, HumanMessage):
                    print(f"[DEBUG] 🧍 Human: {msg.content[:30]}...")
                    text_history.append(f"學生：{msg.content}")
                elif isinstance(msg, AIMessage):
                    print(f"[DEBUG] 🤖 AI: {msg.content[:30]}...")
                    text_history.append(f"助教：{msg.content}")
                else:
                    print(f"[DEBUG] ⚠️ 未知訊息類型：{type(msg)}")

            if not text_history:
                print("[DEBUG] ⚠️ 沒有可摘要的訊息，略過儲存")
                return

            combined = "\n".join(text_history)
            summary_text = f"這是與學生 {student_id} 的對話摘要：\n{combined[:2000]}..."
            save_summary(student_id, summary_text)
            print(f"[LOG] ✏️ 自動更新摘要：student {student_id}")
        except Exception as e:
            print(f"[ERROR] ❌ 摘要更新失敗：{e}")
    else:
        print(f"[DEBUG] ❌ 尚未達摘要條件（目前 {len(history)} 筆）")




# ✅ 關機時歸檔 + 儲存摘要 + 清除快取
def graceful_exit(signum, frame):
    print("[LOG] ⚠️ 收到關機訊號，開始歸檔...")
    archive_now()
    for key in user_sessions:
        student_id = key.replace("student-", "")
        update_summary_if_needed(student_id)  # ✅ 使用統一摘要邏輯
    try:
        os.remove("logs/student_logs_tmp.json")
        print("[LOG] 🧹 清除暫存 student_logs_tmp.json")
    except:
        pass
    print("[LOG] ✅ 關機完成")
    exit(0)

signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)

client.run(DISCORD_BOT_TOKEN)
