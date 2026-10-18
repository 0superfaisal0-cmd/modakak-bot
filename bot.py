# -*- coding: utf-8 -*-
"""
بوت المدقق (@Al_Modaqaq_Bot)
بوت تيليجرام ذكي لقناة دراسة المرحلة الثانوية في السعودية
(قدرات، تحصيلي، ستيب، تحصيلي مبكر)

التشغيل:
    pip install python-telegram-bot google-genai
    export TELEGRAM_BOT_TOKEN="توكن البوت"
    export GEMINI_API_KEY="مفتاح Gemini"
    python bot.py

المصادر:
    البوت ذكي ويجاوب بشكل عام، لكن:
    - لما أحد يسأل عن أفضل المصادر، يجاوب فقط من قائمة SOURCES_LIST تحت.
    - لما أحد يطلب تقييم مصدر، يحوّله لقناة المدقق الرسمية (OFFICIAL_CHANNEL).
"""

import os
import re
import time
import asyncio
import logging
from collections import defaultdict, deque

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, filters

from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("modakak")
# لا تسجل طلبات HTTP التفصيلية — رابط التيليجرام يحتوي التوكن
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
# نماذج احتياطية لو الأساسي ضاغط (الطبقة المجانية تتأثر بضغط الطلب)
MODEL_FALLBACKS = [GEMINI_MODEL, "gemini-3.8-flash", "gemini-3.5-flash-lite"]
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Al_Modaqaq_Bot").lstrip("@").lower()
# لو تبغاه يرد على أي رسالة تنتهي بعلامة استفهام في القروب حط "1"
RESPOND_TO_QUESTIONS = os.environ.get("RESPOND_TO_QUESTIONS", "0") == "1"

# قناة المدقق الرسمية — تُرسل لمن يطلب تقييم مصدر
OFFICIAL_CHANNEL = "https://t.me/jowabk"

# قائمة المصادر المعتمدة — تُجاب منها فقط لما أحد يسأل عن أفضل المصادر
SOURCES_LIST = """القدرات:
- الكمي:
  - المفكر: https://almfkr.sa/
  - المنصف: https://elmonsf.com/
  - اينشتاين: https://instein100.com/
  - الاقسام الحمراء: https://itqaaaan.com/
- اللفظي:
  - ايهاب: https://hadafak-ehab.com/
التحصيلي:
- يلو: https://yellowqt.com/ar/
- اينشتاين: https://instein100.com/
- غشام: https://ghasham1.com/
ستيب STEP:
- منصة معين للدورات: https://share.google/N3s3PL1ndg2Hagai5
- أكاديمية عايد للتدريب: https://share.google/LKtGgj9xCKC5IL7yk
- منصة نجم: https://share.google/23j2ms9bMYkS3dgdn
- قناة الحساني: https://t.me/step_alhassani
التحصيلي المبكر:
- اينشتاين: https://instein100.com/
- يلو: https://yellowqt.com/ar/
"""

SYSTEM_PROMPT = """أنت "المدقق"، بوت ودي لقناة تيليجرام سعودية عن دراسة المرحلة الثانوية:
اختبار القدرات (قياس)، التحصيلي، اختبار ستيب STEP، والتحصيلي المبكر، والقبول الجامعي.

شخصيتك وأسلوبك:
- أجب بالعربية، بلهجة سعودية مفهومة، أسلوب بين الخفيف والرسمي.
- المزح الخفيف مسموح، لكن لا يطغى على الفايدة.
- كن مختصرًا وواضحًا، وردودك مناسبة لطلاب وطالبات الثانوية.

الدقة والحياد أهم من كل شيء:
- لا تخترع أبدًا تواريخ اختبارات أو تسجيل أو نتائج أو نسب قبول أو رسوم أو إحصائيات.
- ممنوع منعًا باتًا تخترع مصادر أو روابط أو أسماء مواقع أو قنوات من عندك.
- إذا السؤال عن موعد أو رقم أو خبر رسمي وما عندك تأكيد، قل بصراحة إنك ما تقدر تتأكد.
- إذا ما تعرف الإجابة قل "ما أدري" بدل التخمين.
- لا تقدم وعودًا باسم إدارة القناة ولا تنصح بقرارات مصيرية؛ أعطِ معلومة وخلي القرار لهم.
- خلّ إجابتك قصيرة ومركزة (أقل من ١٠٠ كلمة غالبًا) عشان توصل كاملة.

قاعدتان خاصتان بالمصادر (مهمة جدًا):
1. إذا أحد سألك عن أفضل المصادر أو وش تنصحهم فيه (دورات، قنوات، مواقع، معلمين، كتب):
   أجب فقط من قائمة "المصادر المعتمدة" المرفقة تحت. لا تضف ولا تحذف من عندك.
2. إذا أحد طلب منك تقييم مصدر أو قال "قيّم لي المصدر فلان" أو سأل عن جودة مصدر معين:
   لا تقيّمه بنفسك. قل له إن التقييم موجود في قناة المدقق الرسمية وأرسل له رابطها.

تذكّر أنك في قروب نقاش: رد على السؤال المطروح فقط، ولا تفتي في أمور خارج موضوع الدراسة
إلا برد قصير لطيف يرجع النقاش للموضوع."""

MAX_HISTORY = 8          # آخر كم رسالة يتذكرها لكل محادثة
COOLDOWN_SECONDS = 5     # فاصل بسيط بين رد ورد لنفس المحادثة

genai_client = genai.Client(api_key=GEMINI_API_KEY)


def clean_answer(text: str) -> str:
    """تيليجرام هنا نص عادي — نشيل رموز الماركداون ونقص بشكل نظيف."""
    t = text
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)          # **عريض**
    t = re.sub(r"__(.+?)__", r"\1", t)
    t = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", t)    # `كود`
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)    # عناوين
    t = re.sub(r"^\s*[-*]\s+", "- ", t, flags=re.M)
    return t.strip()


def tidy_cut(text: str) -> str:
    """لو النص انقصّ من النموذج، قص عند آخر جملة كاملة."""
    for sep in [". ", "؟ ", "! ", "؟", "!", ".", "\n"]:
        i = text.rfind(sep)
        if i > len(text) // 2:
            return text[: i + len(sep)].strip() + "…"
    return text.strip() + "…"


def build_system_instruction() -> str:
    parts = [SYSTEM_PROMPT]
    parts.append(f'\nرابط قناة المدقق الرسمية (لمن يطلب تقييم مصدر): {OFFICIAL_CHANNEL}')
    if SOURCES_LIST.strip():
        parts.append("\nالمصادر المعتمدة (أجب منها فقط لما أحد يسأل عن أفضل المصادر):\n" + SOURCES_LIST.strip())
    else:
        parts.append(
            "\nملاحظة: قائمة المصادر المعتمدة غير مضافة بعد. إذا أحد سأل عن أفضل المصادر، "
            "قل إن القائمة بتنزل قريبًا في قناة المدقق الرسمية وأرسل رابطها."
        )
    return "".join(parts)


histories: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
last_reply: dict[int, float] = defaultdict(float)
lock = asyncio.Lock()


def should_respond(update: Update) -> bool:
    msg = update.message
    if not msg or not msg.text:
        return False
    chat = msg.chat
    if chat.type == ChatType.PRIVATE:
        return True
    text = msg.text.lower()
    # منشن مباشر للبوت
    if f"@{BOT_USERNAME}" in text:
        return True
    # رد على رسالة البوت
    if msg.reply_to_message and msg.reply_to_message.from_user and \
            msg.reply_to_message.from_user.username and \
            msg.reply_to_message.from_user.username.lower() == BOT_USERNAME:
        return True
    # اختياري: أي سؤال ينتهي بعلامة استفهام
    if RESPOND_TO_QUESTIONS and msg.text.strip().endswith(("؟", "?")):
        return True
    return False


async def ask_gemini(chat_id: int, user_text: str) -> str:
    history = histories[chat_id]
    contents = list(history) + [types.Content(role="user", parts=[types.Part(text=user_text)])]
    system_instruction = build_system_instruction()

    def _call():
        last_err = None
        for model in MODEL_FALLBACKS:
            for attempt in range(2):  # محاولة ثانية بعد مهلة قصيرة لكل نموذج
                try:
                    return genai_client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.7,
                            max_output_tokens=2048,
                        ),
                    )
                except Exception as e:
                    last_err = e
                    err = str(e)
                    if "503" in err or "429" in err or "UNAVAILABLE" in err or "RESOURCE_EXHAUSTED" in err:
                        log.warning("model %s busy (attempt %s): %s", model, attempt + 1, err[:120])
                        time.sleep(3 * (attempt + 1))
                        continue
                    raise
        raise last_err

    resp = await asyncio.to_thread(_call)
    answer = (resp.text or "").strip()
    try:
        fr = resp.candidates[0].finish_reason
        if str(fr).endswith("MAX_TOKENS") or "MAX_TOKENS" in str(fr):
            log.warning("answer truncated by model (MAX_TOKENS)")
            answer = tidy_cut(answer)
    except Exception:
        pass
    answer = clean_answer(answer)
    if not answer:
        answer = "ما قدرت أطلع إجابة واضحة، جرّب تعيد السؤال بصيغة ثانية."
    history.append(types.Content(role="user", parts=[types.Part(text=user_text)]))
    history.append(types.Content(role="model", parts=[types.Part(text=answer)]))
    return answer


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not should_respond(update):
        return
    msg = update.message
    chat_id = msg.chat_id

    async with lock:
        now = asyncio.get_event_loop().time()
        if now - last_reply[chat_id] < COOLDOWN_SECONDS:
            return
        last_reply[chat_id] = now

    log.info("incoming from chat %s: %s", chat_id, msg.text[:60])
    user_text = msg.text.replace(f"@{BOT_USERNAME}", "").strip()
    if not user_text:
        user_text = "سلّم عليهم وعرّفهم بنفسك بجملة وحدة."

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        answer = await ask_gemini(chat_id, user_text)
        await msg.reply_text(answer)
        log.info("replied to chat %s", chat_id)
    except Exception as e:
        log.exception("Gemini/Telegram error: %s", e)
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            await msg.reply_text("ضغط عليّ شوي الحين 😅 جرب تسألني بعد دقيقة.")
        else:
            await msg.reply_text("السيرفر ضاغط شوي الحين 😅 جرب تسألني بعد دقيقة.")


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "هلا! أنا المدقق 🤖\n"
        "أجاوب على أسئلتكم عن القدرات والتحصيلي وستيب والقبول الجامعي.\n"
        "في القروب: اكتب سؤالك ومنشّني @" + BOT_USERNAME + " أو رد على رسالتي.\n"
        "ولو تبغى تقييم أي مصدر: " + OFFICIAL_CHANNEL
    )


async def log_everything(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message or update.channel_post or update.edited_message
    if m:
        kind = "message" if update.message else ("channel_post" if update.channel_post else "edited")
        log.info("SAW %s chat=%s type=%s text=%s", kind, m.chat_id, m.chat.type, (m.text or "")[:60])
    else:
        log.info("SAW non-message update: %s", list(update.to_dict().keys()))


def start_health_server():
    """خادم ويب صغير عشان الاستضافة المجانية تعرف أن البوت حي (Render يتطلب منفذ مفتوح)."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"bot is alive")

        def log_message(self, *args):
            pass

    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("health server listening on port %s", port)


def main():
    start_health_server()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, log_everything), group=-1)
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    log.info("Bot is running (polling)...")
    app.run_polling(allowed_updates=["message", "channel_post", "edited_message"])


if __name__ == "__main__":
    main()
