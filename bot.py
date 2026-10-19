# -*- coding: utf-8 -*-
"""
بوت المدقق (@Al_Modaqaq_Bot)
بوت تيليجرام ذكي لقناة المدقق - دراسة المرحلة الثانوية في السعودية
(قدرات، تحصيلي، تحصيلي مبكر، ستيب STEP)

التشغيل:
    pip install -r requirements.txt
    export TELEGRAM_BOT_TOKEN="توكن البوت"
    export GEMINI_API_KEY="مفتاح Gemini"
    python bot.py

متغيرات البيئة في Render:
    TELEGRAM_BOT_TOKEN  (إجباري) توكن البوت
    GEMINI_API_KEY      (إجباري) مفتاح Gemini
    ALLOWED_CHAT_ID     معرف قروب المدقق. فاضي = البوت يشتغل بأي قروب (وضع الإعداد).
                        محطوط = يشتغل بس بذاك القروب ويطلع من أي قروب ثاني.
    OWNER_USER_ID       معرفك الشخصي. محطوط = الخاص يشتغل لك بس،
                        والباقي يجيهم رابط قروب المدقق. فاضي = الخاص مفتوح للكل.
    BOT_USERNAME        (اختياري) يوزر البوت بدون @
    RESPOND_TO_QUESTIONS (اختياري) "1" = يرد على أي سؤال ينتهي بـ ؟ في القروب

طريقة العمل:
    - إذا سأل طالب وش يذاكر أو طلب مصدر: البوت يسأله عن اختباره ومستواه أول،
      وبعدين يرشح من تقييمات القناة (RATINGS) ودليل القدرات (QUDURAT_GUIDANCE) فقط.
    - ممنوع يخترع تقييم أو سعر أو كود خصم أو رابط.
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
# لا تسجل طلبات HTTP التفصيلية - رابط التيليجرام يحتوي التوكن
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

# قفل البوت على قروب المدقق وصاحبه
ALLOWED_CHAT_ID = os.environ.get("ALLOWED_CHAT_ID", "").strip()
OWNER_USER_ID = os.environ.get("OWNER_USER_ID", "").strip()

# رابط قروب المدقق - يُرسل لمن يكلّم البوت برّا القروب
GROUP_INVITE_LINK = "https://t.me/L69XdHpEl7tjZTJk"
# قناة المدقق الرسمية
OFFICIAL_CHANNEL = "https://t.me/jowabk"

# ============================================================
# تقييمات المصادر - من إدارة قناة المدقق
# هذه هي الحقيقة الوحيدة. البوت ما يخترع ولا يضيف من عنده.
# price فاضي = البوت يقول "السعر تجده بموقعهم" وما يذكر رقم.
# ============================================================
RATINGS = [
    # ---------- ستيب STEP ----------
    {
        "name": "عايد",
        "category": "ستيب STEP",
        "price": "٣٩٩ ريال",
        "discount": "",
        "link": "https://ayedacademy.co",
        "notes": """اكثر دوره لها خبره وسمعتها سابقه، تاسيسه رهيب للي انجليزيته ماش وترتيب الدوره رهيب، لكن شرح تجميعات الريدنق ماش وسعره يعتبر غالي على الطلاب.
السعر ❌ غاليه الصدق على البعض
النماذج ✅ نماذجه ممتازه مافيها مشاكل وعنده استثنائات
ترتيب الدوره ✅ موقعه ممتاز وترتيبه واضح جدا
الكويزات ✅ كويزاته مرتبه وتقدر تشوف اخطائك وترحع لها
شرح الريدنق ❌ تعبان، شرح قديم بعضه متسجل من سنين ومن اكثر من معلم وغير واضح
شرح القرامر والتاسيس ⭐️ توب، فيه تاسيس وتدريب يخليك رهيب جدا حتى لو مالك فيه""",
    },
    {
        "name": "الحساني",
        "category": "ستيب STEP",
        "price": "مجاني",
        "discount": "",
        "link": "https://t.me/step_alhassani",
        "notes": """نماذج توب ومجاني، ينفع غالبا للي انجليزيته كويسه ويقدر يفهم من الملفات لحالها ما يحتاج اي شي غيره. وانه دامه مجاني تقدر تستعمل كويزاته وملفاته مع اي دوره ثانيه عشان تغطي النقص احيانا وتكون اشمل.
السعر ⭐️ مجاني مافي افضل من كذا
النماذج ⭐️ دورته معتمده عليها، دايما متفوق بقليل عن البقيه
ترتيب الدوره ❌ دورته بالتلجرام عشان كذا ترتيبها سيي وحتى ملفاتها ترتيبها لك عليه
الكويزات ✅ ممتازه موجوده بالتلجرام ومرتبه كويس على كل نموذج
الشرح ❌ العيب الاكبر انه مافيه شرح لاي شي""",
    },
    {
        "name": "نجم",
        "category": "ستيب STEP",
        "price": "٢٧٦ ريال بعد كود الخصم",
        "discount": "كود الخصم: 67 (يخصم لك ٧٠ ريال)",
        "link": "https://najmsa.com",
        "notes": """دوره من الدورات الي عليها تسويق، قديمه بالمجال، نماذجها ممتازه وسعرها جيد.
السعر 🟰 بعد الخصم جيد، مب من اغلى الدورات ولا ارخصها
النماذج ✅ ممتازه نفس عايد والحساني تقريبا، وعندهم ملفات الاكثر تكرار ريدنق
ترتيب الدوره 🟰 عندهم موقع افضل من لاشيئ ولكنه مربك شوي، مو افضل ترتيب لكن الوصول سهل
الكويزات ⭐️ توب، عندهم كويز بعد كل درس تاسيس وعندهم اختبارات محاكيه على كل النماذج كانه الاختبار نفسه
شرح النماذج ✅ ممتاز سواء ريدنق او قرامر، مرتب وواضح
شرح التاسيس قرامر 🟰 مو افضل شي مثل عايد لكنه كويس، اي احد فاهم شوي بيفهم""",
    },
    {
        "name": "اكتمال",
        "category": "ستيب STEP",
        "price": "مجاني",
        "discount": "",
        "link": "https://ektmal.com/units/385",
        "notes": """منصه مب معروفه كثير لكنها ممتازه والافضل انها مجانيه.
ملاحظه: فتحت دوره بفلوس فيها شرح، لكن التقييم على المجانيه حاليا.
السعر ⭐️ مجاني، ممتاز لو تبي تشيك على الدوره قبل تذاكر
النماذج ✅ نماذج كامله وتجي نسخ لصق
ترتيب الدوره ⭐️ رهيب ومريح للاستخدام جدا
الكويزات ✅ مرتبه بشكل ممتاز على كل اسئله النماذج
شرح النماذج ❌ مافيه اي شرح سواء ريدنق او قرامر
شرح التاسيس ❌ مافيه شرح للاسف""",
    },
    {
        "name": "ستيب بدون تعقيد",
        "category": "ستيب STEP",
        "price": "مجاني",
        "discount": "",
        "link": "https://youtube.com/@stepenglishtest",
        "notes": """دوره مجانيه باليوتيوب، تاسيسها عليه مدح جدا وعندها شروحات لباقي الاشياء.
السعر ⭐️ مجانيه، ممتازه تقدر تشيك عليها باليوتيوب
شرح التاسيس ⭐️ ممكن افضل شرح تاسيس مجاني، جميله وهذا المميز فيها
شرح القرامر والليسننق والريدنق ✅ الشرح جميل لكن المشكله الاسئله ماهي كل اسئله التجميعات، تنفع لو مستواك كويس وتبي تتطلع وتتدرب شوي
الملفات والنماذج ❌ الدوره اغلبها شروحات، في ملف للتاسيس فقط""",
    },
    # ---------- تحصيلي وتحصيلي مبكر ----------
    {
        "name": "يلو",
        "category": "تحصيلي وتحصيلي مبكر",
        "price": "١٥٠ ريال",
        "discount": "",
        "link": "https://yellowqt.com/ar",
        "notes": """(مفتوحه للمبكر 🟢) دوره من دورات التوب، تقدر تضمن فيها مئويه، شامله، ترتيبها ممتاز وموقعها تاريخي، والافضل للمبكر.
السعر 🟰 متوسط، حلو ومب غالي خصوصا اذا شفت المزايا
شرح التاسيس ⭐️ ممتاز، عندهم اكثر من مدرس لكل ماده يعني طب وتخير، وعندهم الزبده (تاسيس مختصر لكل المواد)
الملفات ⭐️ ملفاتهم مرتبه وعندهم ملخصات لكل المواد
التجميعات ⭐️ اشمل تجميعات هم واينشتاين
التوقعات ✅ جيده، ١٥٠٠ سؤال لكل ماده
الكويزات ⭐️⭐️⭐️ حرفيا افضل ميزه، كويزاتهم مخصصه وفيها مزايا كثير تقدرون تشوفونها بموقعهم
الترتيب ⭐️⭐️ افضل مافي الدورة، موقع تاريخي جميل ومرتب يفتح النفس للمذاكره والوصول لكل مزاياها سهل جدا""",
    },
    {
        "name": "اينشتاين",
        "category": "تحصيلي وتحصيلي مبكر",
        "price": "٣٥ ريال",
        "discount": "",
        "link": "https://instein100.com/front/ar/",
        "notes": """من دورات التوب. السنه الي فاتت كانت بالتليجرام وهالسنه بيفتح موقع. تقدر تضمن فيها مئويه وشامله، واذا اشتركت تشمل المبكر والاعتيادي.
السعر ⭐️⭐️⭐️ جمييل لاي احد مو مقتدر، اتوقع ارخص دوره تحصيلي
شرح التاسيس ⭐️ ممتاز لكل المواد، والسنه هذي اضاف معلمين اكثر للتاسيس
الملفات 🟰 ملفاته للتوقعات والتجميعات مرتبه، لكن التاسيس يعتمد على كتاب ناصر ببعض المواد وعنده كتاب لبعضهم
التجميعات ⭐️ شامله، هو ويلو تقدر تقفل فيها
التوقعات ⭐️⭐️ افضل مافي دورته، شامله جدا وجاء منها العام الي فات كثير، ٤٠٠٠ سؤال تقريبا
الكويزات 🟰 السنه الي فاتت كانت سيئه، لكن هالسنه بيفتحها بالموقع فما نقدر نقيم
الترتيب 🟰 بيفتح موقع جديد للدوره لكن لسى ما نزل، فما نقدر نقيمه""",
    },
    {
        "name": "غشام",
        "category": "تحصيلي وتحصيلي مبكر",
        "price": "٩٥ ريال",
        "discount": "",
        "link": "https://ghasham1.com/",
        "notes": """(فتحت للمبكر 🟢) دوره جميله لكن الافضل ما تعتمد عليها لحالها، تنفع اذا بتاخذ جزء منها زي التوقعات.
السعر ✅ ممتاز رخيصه، تسوى لو بتاخذها مع دوره ثانيه
شرح التاسيس 🟰 عنده معلمين للتاسيس لكن الصدق فيه افضل منهم، وهو مجاني يمديك تشيك عليه باليوتيوب
الملفات ⭐️ افضل مافي دورته مرتبه، والاهم عنده بحر الاسئله (اسئله مجمعه من الكتاب المدرسي مستواها اعلى وشامله كل الافكار، غير ضروريه) والاختبار المقنن (من الكتاب المدرسي، غير ضروريه للاستزاده)
التجميعات 🟰 كويسه عددها قليل يجي منها لكن مو الاشمل، ينفع تاخذها مع تجميعات مصدر ثاني
التوقعات ✅ ممتازه يجي منها، ينفع تاخذها مع توقعات اي احد ثاني
الكويزات ❌ موجوده بالموقع لكن مب مرتبه وحوسه ماش
الترتيب 🟰 عنده موقع لكن ترتيبه عادي، لك عليه شوي""",
    },
    {
        "name": "كتاب ناصر عبدالكريم",
        "category": "تحصيلي",
        "price": "١٠٠ ريال",
        "discount": "",
        "link": "https://www.jarir.com/arabic-books-674256.html",
        "notes": """(مانزل 🛑) كتاب متوفر بجرير وامازون، رهيب ومعروف للتاسيس.
السعر ✅ جميل لكن يعتبر كثير شوي لان تحتاج معه دوره ثانيه للتجميعات
شرح التاسيس ⭐️ ممتاز، له معلمين كثييير يشرحونه
الملفات (الكتاب) ⭐️ جميل ومرتب للتاسيس وفيه تجميعات لكل درس مرتبه زين
التجميعات 🟰 تجميعاته ابد مو كفايه خصوصا الي بالكتاب
التوقعات ❌ مافيه توقعات
الكويزات ❌ مافيه كويزات
الترتيب ⭐️ حلو لانه كتاب، بيكون سهل التعامل معه جدا""",
    },
]

# ============================================================
# دليل القدرات - من إدارة القناة
# الأسعار غير متوفرة: البوت يقول "السعر تجده بموقعهم" وما يذكر رقم
# ============================================================
QUDURAT_GUIDANCE = """مصادر القدرات المعتمدة وطريقة الترشيح:
- الاقسام الحمراء (كمي): https://itqaaaan.com/
  عبارة عن تجميعات تتكرر جدا في الاختبار وتعتبر منصة تدريب للكمي.
  رشحها للي اختباره قريب ومزنوق.
- المنصف: https://elmonsf.com/
  منصة تدريب ممتازة جدا. اذا فيه وقت على اختبارك خذها بعد التأسيس،
  كمنصة تدربك من التأسيس الى المستوى المرتفع.
- المفكر: https://almfkr.sa/
  نفس فكرة المنصف، بس ميزته ان اسئلته تتكرر اكثر بالاختبارات.
- ايهاب (لفظي): https://hadafak-ehab.com/
  افضل مصدر لفظي، يتكرر بالاختبار كثير ويجي نسخ لصق.
  افضل منصة تأسيس وتدريب للفظي.
- اينشتاين: https://instein100.com/
ملاحظة مهمة: اسعار مصادر القدرات غير مسجلة عندك. اذا سأل الطالب عن السعر قل له
"السعر تجده بموقعهم" ولا تذكر اي رقم."""

SYSTEM_PROMPT = """أنت "المدقق"، بوت قروب المدقق في تيليجرام - قناة سعودية عن دراسة المرحلة الثانوية:
اختبار القدرات (قياس)، التحصيلي، التحصيلي المبكر، اختبار ستيب STEP، والقبول الجامعي.

شخصيتك وأسلوبك:
- أجب بالعربية، بلهجة سعودية مفهومة، أسلوب بين الخفيف والرسمي.
- المزح الخفيف مسموح، لكن لا يطغى على الفايدة.
- كن مختصرًا وواضحًا، وردودك مناسبة لطلاب وطالبات الثانوية.
- خلّ إجابتك قصيرة ومركزة (أقل من ١٠٠ كلمة غالبًا) عشان توصل كاملة.

الدقة والحياد أهم من كل شيء:
- لا تخترع أبدًا تواريخ اختبارات أو تسجيل أو نتائج أو نسب قبول أو رسوم أو إحصائيات.
- ممنوع منعًا باتًا تخترع مصادر أو روابط أو أسعار أو أكواد خصم أو تقييمات من عندك.
- إذا السؤال عن موعد أو رقم أو خبر رسمي وما عندك تأكيد، قل بصراحة إنك ما تقدر تتأكد.
- إذا ما تعرف الإجابة قل "ما أدري" بدل التخمين.
- لا تقدم وعودًا باسم إدارة القناة ولا تنصح بقرارات مصيرية؛ أعطِ معلومة وخلي القرار لهم.

طريقة ترشيح المصادر (أهم قاعدة):
- عندك تحت "تقييمات المصادر" و"دليل القدرات" من إدارة القناة. هذه هي الحقيقة الوحيدة.
- إذا سألك طالب وش يذاكر أو طلب مصدر أو دورة: لا ترشح فورًا.
  اسأله أولًا باختصار وبلطف:
  1) وش اختبارك؟ (قدرات / تحصيلي / تحصيلي مبكر / ستيب)
  2) هل أنت مؤسس ولا تحتاج تأسيس؟
  3) متى اختبارك تقريبًا؟
  وبعد ما يجاوب، رشح له الأنسب من التقييمات لاحتياجه، وأرسل:
  اسم المصدر + الرابط + السعر + كود الخصم إن وجد + سبب الترشيح من التقييم.
- اذكر السعر فقط إذا كان مسجلًا في التقييم. إذا غير مسجل قل "السعر تجده بموقعهم".
- إذا سأل عن مصدر غير موجود في التقييمات، قل إنه غير مقيّم عندنا بعد
  وانصحه يتابع قناة المدقق، ولا تقيّمه من عندك.
- التحصيلي المبكر منهجه أول وثاني ثانوي وقسم المهارات - التقييمات تذكر وش مفتوح للمبكر.

تذكّر أنك في قروب نقاش: رد على السؤال المطروح فقط، ولا تفتي في أمور خارج موضوع الدراسة
إلا برد قصير لطيف يرجع النقاش للموضوع."""


def clean_answer(text: str) -> str:
    """تيليجرام هنا نص عادي - نشيل رموز الماركداون."""
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
    parts.append(f"\nقناة المدقق الرسمية: {OFFICIAL_CHANNEL}")
    parts.append(f"رابط قروب المدقق: {GROUP_INVITE_LINK}")
    parts.append("\n\nتقييمات المصادر (من إدارة القناة - أجب منها فقط):")
    for r in RATINGS:
        block = f"\n### {r['name']} ({r['category']})"
        block += f"\nالرابط: {r['link']}"
        block += f"\nالسعر: {r['price']}" if r["price"] else ""
        block += f"\n{r['discount']}" if r["discount"] else ""
        block += f"\nالتقييم:\n{r['notes']}"
        parts.append(block)
    parts.append("\n\n" + QUDURAT_GUIDANCE)
    return "".join(parts)


MAX_HISTORY = 8          # آخر كم رسالة يتذكرها لكل محادثة
COOLDOWN_SECONDS = 5     # فاصل بسيط بين رد ورد لنفس المحادثة

genai_client = genai.Client(api_key=GEMINI_API_KEY)

histories: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
last_reply: dict[int, float] = defaultdict(float)
lock = asyncio.Lock()


def is_allowed_chat(msg) -> bool:
    """هل المحادثة مسموحة؟
    - القروبات: بس القروب المحدد في ALLOWED_CHAT_ID (لو فاضي، الكل مسموح = وضع الإعداد).
    - الخاص: لو OWNER_USER_ID محطوط، بس هو. لو فاضي، الخاص مفتوح.
    """
    chat = msg.chat
    if chat.type == ChatType.PRIVATE:
        if OWNER_USER_ID:
            return bool(msg.from_user) and str(msg.from_user.id) == OWNER_USER_ID
        return True
    if ALLOWED_CHAT_ID:
        return str(chat.id) == ALLOWED_CHAT_ID
    return True


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
    msg = update.message
    if not msg:
        return

    # قفل البوت: قروب غير مسموح -> ودّع واطلع منه. خاص غير مسموح -> حوّله للقروب.
    if not is_allowed_chat(msg):
        if msg.chat.type == ChatType.PRIVATE:
            await msg.reply_text(
                "هلا! أنا بوت المدقق وأرد بس داخل قروب المدقق 🙏\n"
                "تفضل معنا واسأل هناك: " + GROUP_INVITE_LINK
            )
        else:
            try:
                await msg.reply_text("هذا البوت خاص بقروب المدقق بس، بتطلع من هنا 👋")
            except Exception:
                pass
            try:
                await context.bot.leave_chat(msg.chat_id)
                log.info("left unauthorized chat %s", msg.chat_id)
            except Exception as e:
                log.warning("couldn't leave chat %s: %s", msg.chat_id, e)
        return

    if not should_respond(update):
        return
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
        await msg.reply_text("ضغط عليّ شوي الحين 😅 جرب تسألني بعد دقيقة.")


async def on_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لو أحد ضاف البوت لقروب غير قروب المدقق، يطلع فورًا حتى لو ما أحد كتب شي."""
    msg = update.message
    if not msg or not ALLOWED_CHAT_ID:
        return
    if str(msg.chat_id) == ALLOWED_CHAT_ID:
        return
    try:
        await context.bot.leave_chat(msg.chat_id)
        log.info("left unauthorized group %s on join", msg.chat_id)
    except Exception as e:
        log.warning("couldn't leave group %s: %s", msg.chat_id, e)


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    # رد /start بس في محادثة مسموحة
    if not is_allowed_chat(msg):
        if msg.chat.type == ChatType.PRIVATE:
            await msg.reply_text(
                "هلا! أنا بوت المدقق وأرد بس داخل قروب المدقق 🙏\n"
                "تفضل معنا: " + GROUP_INVITE_LINK
            )
        return
    await msg.reply_text(
        "هلا! أنا المدقق 🤖\n"
        "أجاوب على أسئلتكم عن القدرات والتحصيلي وستيب والقبول الجامعي،\n"
        "وأرشح لكم أفضل مصدر حسب احتياجكم من تقييمات القناة.\n"
        "في القروب: اكتب سؤالك ومنشّني @" + BOT_USERNAME + " أو رد على رسالتي."
    )


async def on_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعطيك معرف المحادثة ومعرفك الشخصي - عشان تعبي متغيرات Render."""
    msg = update.message
    user_id = msg.from_user.id if msg.from_user else "؟"
    await msg.reply_text(
        f"معرف هذه المحادثة (chat id): {msg.chat_id}\n"
        f"معرفك الشخصي (user id): {user_id}"
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
    app.add_handler(CommandHandler("id", on_id))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_added_to_group))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    log.info(
        "Bot is running (polling)... lock: %s",
        f"group {ALLOWED_CHAT_ID}" if ALLOWED_CHAT_ID else "OPEN (setup mode)",
    )
    app.run_polling(allowed_updates=["message", "channel_post", "edited_message"])


if __name__ == "__main__":
    main()
