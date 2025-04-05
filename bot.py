import os
from dotenv import load_dotenv
import discord
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from log_archiver import log_message  # 匯入 log 寫入函式

# ✅ 載入環境變數
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# ✅ Discord 設定
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# 🧠 使用者記憶
user_chats = {}

# ✅ 預設提示（高成就）
DEFAULT_PROMPT = (
    "你是一位精簡且專業的 Python 助教，請針對學生問題給出直接、有效的提示，"
    "避免贅詞，鼓勵學生自行思考與查詢，必要時提供專業術語與實例。\n\n"
    "🔹 如果學生輸入的是一段 Python 程式碼，請不要立刻解釋，"
    "而是詢問學生希望從以下哪個方向獲得幫助，並請他選擇對應的數字：\n"
    "1️⃣ 邏輯解釋\n2️⃣ 語法說明\n3️⃣ 換個寫法\n4️⃣ 加上註解\n5️⃣ 程式碼檢查\n"
    "請等待學生回覆數字後再依指令進行。\n\n"
    "🔹 如果學生的輸入是一個問題，請依照他程度給出合適的解釋。\n"
    "🔹 若學生使用 `XXX -e` 這種格式，請提供一個相關範例並簡要說明其用途。\n"
    "請確保語氣清晰、回應有層次。"
)

# ✅ 低成就學生提示
LOW_ACHIEVER_PROMPT = (
    "你是一位非常有耐心且善於引導的 Python 助教，面對基礎尚未扎實的學生，"
    "請避免直接給出答案，並以簡單舉例與提問的方式幫助學生思考，"
    "例如生活化比喻、反問、循序漸進的解釋方式，建立信心與理解力。\n\n"
    "🔹 如果學生輸入的是一段 Python 程式碼，請不要立刻解釋，"
    "而是詢問學生希望從以下哪個方向獲得幫助，並請他選擇對應的數字：\n"
    "1️⃣ 邏輯解釋\n2️⃣ 語法說明\n3️⃣ 換個寫法\n4️⃣ 加上註解\n5️⃣ 程式碼檢查\n"
    "請等待學生回覆數字後再依指令進行。\n\n"
    "🔹 如果學生的輸入是一個問題，請用簡單比喻或分段說明幫助他理解。\n"
    "🔹 若學生使用 `XXX -e` 這種格式，請提供一個相關範例並用白話解釋其用途。"
)

def preprocess_message(message: str) -> str:
    if message.endswith(" -e"):
        topic = message[:-3].strip()
        return f"請舉一個 Python 中「{topic}」的使用範例，並說明它的用途。"
    return message

def get_system_prompt(student_number: int) -> str:
    if student_number <= 2:
        return LOW_ACHIEVER_PROMPT
    else:
        return DEFAULT_PROMPT

def get_user_conversation(student_number: int) -> ConversationChain:
    key = f"student-{student_number}"
    if key not in user_chats:
        llm = ChatGoogleGenerativeAI(
            model="models/gemini-1.5-pro",
            temperature=0.7,
            google_api_key=GOOGLE_API_KEY
        )
        memory = ConversationBufferMemory(return_messages=True)
        conversation = ConversationChain(llm=llm, memory=memory, verbose=False)

        prompt = get_system_prompt(student_number)
        conversation.memory.chat_memory.add_user_message(prompt)
        conversation.memory.chat_memory.add_ai_message("了解，我是你的 Python 助教，有問題儘管問我吧！")

        user_chats[key] = conversation
    return user_chats[key]

@client.event
async def on_ready():
    print(f"✅ 助教上線囉！Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    channel_name = message.channel.name
    parts = channel_name.split("-")

    if len(parts) < 1 or not parts[0].isdigit():
        await message.channel.send("⚠️ 頻道名稱應為『編號-名字』格式，例如 `001-小明`")
        return

    student_number = int(parts[0])
    content = message.content.strip()
    processed = preprocess_message(content)

    conversation = get_user_conversation(student_number)
    log_message(str(student_number), "student", content)

    try:
        response = conversation.predict(input=processed)
        log_message(str(student_number), "ai", response)
        await message.channel.send(response)
    except Exception as e:
        await message.channel.send(f"⚠️ 發生錯誤：{e}")
        raise e

client.run(DISCORD_BOT_TOKEN)
