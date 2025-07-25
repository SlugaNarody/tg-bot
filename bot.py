import asyncio
import os
import json
import re
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.types import FSInputFile
from dotenv import load_dotenv

from admin_panel import admin_router

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
QUESTIONS_FILE = "questions_data.json"
MEDIA_DIR = "media"

ADMIN_ID = 7028215322  # ваш Telegram user_id

class SurveyState(StatesGroup):
    lang = State()
    wait_start = State()
    q = State()
    wait_custom_source = State()

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(admin_router)

def load_questions():
    try:
        with open(QUESTIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Error loading questions:", e)
        return {"ru": [], "en": []}

def lang_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Русский")], [KeyboardButton(text="English")]],
        resize_keyboard=True, one_time_keyboard=True)

def start_keyboard(lang):
    if lang == "en":
        text = "START"
    else:
        text = "СТАРТ"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text)]],
        resize_keyboard=True, one_time_keyboard=True)

def choices_keyboard(choices, special_layout=False):
    if special_layout and len(choices) >= 4:
        rows = [choices[:2], choices[2:4]]
        rest = choices[4:]
        for r in rest:
            rows.append([r])
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=ch) for ch in row] for row in rows],
            resize_keyboard=True, one_time_keyboard=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=ch)] for ch in choices],
            resize_keyboard=True, one_time_keyboard=True)

user_state = {}

    WELCOME_TEXT = {
    "ru": """Благодарим за интерес к нашему проекту. Сейчас вы пройдёте короткий опрос — это поможет нам лучше понять ваши цели и подобрать для вас максимально подходящий путь обучения.

FCK Academy (от англ. Finance Crypto Knowledge) — современная образовательная платформа с более чем 4-летним опытом в сфере криптовалют и цифровых инвестиций. Мы обучаем не теории, а реальной торговле в DeFi секторе: каждый студент работает с живым рынком под руководством профессионалов.

За это время FCK Academy прошли более 1600 студентов. Из них 82 % начали получать доход в первую неделю, а 68 % — сформировали устойчивый инвестиционный портфель за 14 дней. Средняя прибыль по сделкам под кураторским сопровождением составляет от 13 % до 21 % в неделю, в зависимости от стратегии и уровня вовлечённости.

Над результатами студентов работают более 12 опытных кураторов, доступных 24/7. Обучение строится на четырёх ключевых принципах:

— Постоянная практика на реальном рынке  
— Поддержка на каждом этапе  
— Возможность зарабатывать из любой точки мира"""
}

",
    "en": "Thank you for your interest in our project. Now you will take a short survey — this will help us better understand your goals and find the most suitable learning path for you."
}

ERROR_MSG = {
    "ru": "Дай ответ более корректно и открыто",
    "en": "Please answer more clearly and openly"
}

AGE_BLOCK_MSG = {
    "ru": "Извините, наш сервис только для лиц старше 18 лет. Доступ закрыт.",
    "en": "Sorry, our service is only for people over 18 years old. Access denied."
}

def render_final_phrase(phrase: str, contact_link: str) -> str:
    link = contact_link.strip()
    if not link.startswith("@"):
        link = f"@{link}"
    return phrase.replace("{contact_link}", link)

async def send_results_to_admin(user, answers, bot, contact_link, final_phrase):
    user_info = f"@{user.username}" if user.username else ""
    text = (
        f"Новые ответы пользователя:\n"
        f"ID: <code>{user.id}</code>\n"
        f"Username: {user_info}\n"
        f"Имя: {user.first_name or '-'}\n"
        f"Фамилия: {user.last_name or '-'}\n\n"
        "Ответы:\n"
    )
    for k, v in answers.items():
        text += f"{k}: {v}\n"
    text += f"\nКонтакт для пользователя: {contact_link}"
    text += f"\nФраза для пользователя: {render_final_phrase(final_phrase, contact_link)}"
    await bot.send_message(ADMIN_ID, text)

banned_users = set()

def is_only_digits(text):
    return text.isdigit()

def is_text_with_letters_ratio(text, min_ratio=0.7):
    letters = re.findall(r'[a-zA-Zа-яА-ЯёЁ]', text)
    length = len(text.replace(" ", ""))
    if length == 0:
        return False
    letter_ratio = len(letters) / length
    return letter_ratio >= min_ratio

def is_text_with_letters_ratio_or_digits(text, min_ratio=0.5):
    letters = re.findall(r'[a-zA-Zа-яА-ЯёЁ]', text)
    length = len(text.replace(" ", ""))
    if length == 0:
        return False
    letter_ratio = len(letters) / length
    return letter_ratio >= min_ratio

@dp.message(F.text.lower().in_({"/start", "start"}))
async def welcome(message: Message, state: FSMContext):
    if message.from_user.id in banned_users:
        await message.answer(AGE_BLOCK_MSG["ru"] + "\n" + AGE_BLOCK_MSG["en"])
        return
    await state.clear()
    user_state[message.from_user.id] = {"answers": {}}  # Не задаём язык заранее!
    await message.answer("Выберите язык / Select language:", reply_markup=lang_keyboard())
    await state.set_state(SurveyState.lang)

@dp.message(SurveyState.lang)
async def choose_lang(message: Message, state: FSMContext):
    if message.from_user.id in banned_users:
        await message.answer(AGE_BLOCK_MSG["ru"] + "\n" + AGE_BLOCK_MSG["en"])
        return
    text = message.text.strip().lower()
    if text in ("русский", "рус", "ru"):
        lang = "ru"
    elif text in ("english", "en"):
        lang = "en"
    else:
        await message.answer("Пожалуйста, выберите язык / Please select a language:", reply_markup=lang_keyboard())
        return
    user_state[message.from_user.id]["lang"] = lang
    logo_path = os.path.join(MEDIA_DIR, "logo.jpg")
    if os.path.exists(logo_path):
        await message.answer_photo(FSInputFile(logo_path))
    await message.answer(WELCOME_TEXT[lang])
    await message.answer("Начнем опрос! / Let's start the survey!", reply_markup=start_keyboard(lang))
    await state.set_state(SurveyState.wait_start)

@dp.message(SurveyState.wait_start)
async def start_survey(message: Message, state: FSMContext):
    if message.from_user.id in banned_users:
        await message.answer(AGE_BLOCK_MSG["ru"] + "\n" + AGE_BLOCK_MSG["en"])
        return
    user_id = message.from_user.id
    lang = user_state[user_id].get("lang", "ru")
    expected = "старт" if lang == "ru" else "start"
    if message.text.strip().lower() != expected:
        msg = "Нажмите кнопку 'СТАРТ'!" if lang == "ru" else "Press the 'START' button!"
        await message.answer(msg, reply_markup=start_keyboard(lang))
        return
    data = load_questions()
    user_state[user_id]["q_idx"] = 0
    user_state[user_id]["skip_next"] = False
    await ask_next_question(message, user_id, lang, data, state)
    await state.set_state(SurveyState.q)

async def ask_next_question(message, user_id, lang, data, state):
    questions = data.get(lang, [])
    idx = user_state[user_id].get("q_idx", 0)
    while idx < len(questions):
        q = questions[idx]
        if "depends_on" in q:
            dep_idx = q["depends_on"]["question_idx"]
            dep_vals = [v.lower() for v in q["depends_on"]["values"]]
            prev_answer = user_state[user_id]["answers"].get(f"q{dep_idx+1}", "").strip().lower()
            if prev_answer not in dep_vals:
                idx += 1
                user_state[user_id]["q_idx"] = idx
                continue
        img_name = f"{idx+1}.jpg"
        img_path = os.path.join(MEDIA_DIR, img_name)
        show_image = True
        if "depends_on" in q:
            dep_idx = q["depends_on"]["question_idx"]
            prev_answer = user_state[user_id]["answers"].get(f"q{dep_idx+1}", "").strip().lower()
            if prev_answer not in [v.lower() for v in q["depends_on"]["values"]]:
                show_image = False
        if show_image and os.path.exists(img_path):
            await message.answer_photo(FSInputFile(img_path))
        is_source_q = ("узнали про компанию" in q["question"].lower() or "how did you hear about" in q["question"].lower())
        if q["type"] == "choice":
            kb = choices_keyboard(
                q["choices"],
                special_layout=is_source_q
            )
        else:
            kb = ReplyKeyboardRemove()
        await message.answer(q["question"], reply_markup=kb)
        break
    else:
        contact_link = data.get("contact_link", "@manager")
        final_phrase = data.get("final_phrase",
            {
                "ru": f"Спасибо! Напишите нашему менеджеру {contact_link} для дальнейших инструкций.",
                "en": f"Thank you! Please message our manager {contact_link} for further instructions."
            }
        )
        lang_final_phrase = final_phrase[lang] if isinstance(final_phrase, dict) else final_phrase
        final_phrase_ready = render_final_phrase(lang_final_phrase, contact_link)
        await message.answer(final_phrase_ready, reply_markup=ReplyKeyboardRemove())
        await send_results_to_admin(
            message.from_user,
            user_state[user_id]["answers"],
            bot,
            contact_link,
            lang_final_phrase
        )
        await state.clear()
        return
    user_state[user_id]["q_idx"] = idx

@dp.message(SurveyState.q)
async def handle_answer(message: Message, state: FSMContext):
    if message.from_user.id in banned_users:
        await message.answer(AGE_BLOCK_MSG["ru"] + "\n" + AGE_BLOCK_MSG["en"])
        await state.clear()
        return
    user_id = message.from_user.id
    lang = user_state[user_id].get("lang", "ru")
    data = load_questions()
    idx = user_state[user_id]["q_idx"]
    questions = data[lang]
    q = questions[idx]
    q_text_lower = q["question"].lower()

    error_msg = ERROR_MSG[lang]

    # 1. "Сколько вам лет?" / "How old are you?" — только цифры, >= 18
    if (
        ("сколько вам лет" in q_text_lower) or
        ("how old are you" in q_text_lower)
    ):
        if not is_only_digits(message.text.strip()):
            await message.answer(error_msg)
            return
        age = int(message.text.strip())
        if age < 18:
            banned_users.add(user_id)
            await message.answer(AGE_BLOCK_MSG[lang])
            await state.clear()
            return
    # 2. Вопрос про доход — минимум 50% букв
    elif (
        ("какой доход вы хотите получать" in q_text_lower) or
        ("what income would you like to receive" in q_text_lower)
    ):
        if not is_text_with_letters_ratio_or_digits(message.text.strip(), min_ratio=0.5):
            await message.answer(error_msg)
            return
    # 3. Остальные текстовые вопросы — минимум 70% букв
    elif q["type"] == "text":
        if not is_text_with_letters_ratio(message.text.strip(), min_ratio=0.7):
            await message.answer(error_msg)
            return

    is_source_q = (
        "узнали про компанию" in q_text_lower or
        "how did you hear about" in q_text_lower
    )
    if q["type"] == "choice":
        if is_source_q:
            other_variants = ["другое", "other"]
            if message.text.strip().lower() in other_variants:
                user_state[user_id]["awaiting_manual_source"] = True
                await state.set_state(SurveyState.wait_custom_source)
                msg = "Пожалуйста, напишите свой вариант (не менее 5 символов):" if lang == "ru" else "Please write your own option (at least 5 characters):"
                await message.answer(
                    msg,
                    reply_markup=ReplyKeyboardRemove()
                )
                return
            valid_choices = [ch.strip() for ch in q["choices"]]
            if message.text.strip() not in valid_choices:
                await message.answer(error_msg, reply_markup=choices_keyboard(valid_choices, special_layout=True))
                return
        else:
            valid_choices = [ch.strip() for ch in q["choices"]]
            if message.text.strip() not in valid_choices:
                await message.answer(error_msg, reply_markup=choices_keyboard(valid_choices))
                return

    user_state[user_id]["answers"][f"q{idx+1}"] = message.text
    is_exp_q = (
        "опыт в сфере криптовалют" in q_text_lower or
        "experience in cryptocurrencies" in q_text_lower
    )
    if is_exp_q:
        if message.text.strip().lower() in ["нет", "no"]:
            for i in range(idx + 1, len(questions)):
                qn = questions[i]
                if "depends_on" in qn and qn["depends_on"]["question_idx"] == idx:
                    user_state[user_id]["q_idx"] = i + 1
                    break
            else:
                user_state[user_id]["q_idx"] = idx + 1
        else:
            user_state[user_id]["q_idx"] = idx + 1
    else:
        user_state[user_id]["q_idx"] = idx + 1
    await ask_next_question(message, user_id, lang, data, state)

@dp.message(SurveyState.wait_custom_source)
async def handle_manual_source(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_state[user_id].get("lang", "ru")
    if user_id in banned_users:
        await message.answer(AGE_BLOCK_MSG["ru"] + "\n" + AGE_BLOCK_MSG["en"])
        await state.clear()
        return
    min_len = 5
    if len(message.text.strip()) < min_len:
        await message.answer(ERROR_MSG[lang])
        return
    idx = user_state[user_id]["q_idx"]
    user_state[user_id]["answers"][f"q{idx+1}"] = message.text
    user_state[user_id]["q_idx"] = idx + 1
    data = load_questions()
    await state.set_state(SurveyState.q)
    await ask_next_question(message, user_id, lang, data, state)

from aiohttp import web

WEBHOOK_HOST = os.getenv("WEBHOOK_URL")  # Например, https://tg-bot-xxxxx.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

async def on_startup(bot):
    await bot.set_webhook(WEBHOOK_URL)

async def handle(request):
    update = await request.json()
    await dp.feed_webhook_update(bot=bot, update=update)
    return web.Response()

async def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle)

    await on_startup(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

    print(f"Webhook running at {WEBHOOK_URL}")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
