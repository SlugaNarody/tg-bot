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
        return {"ru": []}

def save_questions(data):
    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def lang_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Русский")]],
        resize_keyboard=True, one_time_keyboard=True)

def start_keyboard(lang):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="СТАРТ")]],
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
    "ru": "Благодарим за интерес к нашему проекту. Сейчас вы пройдёте короткий опрос — это поможет нам лучше понять ваши цели и подобрать для вас максимально подходящий путь обучения"
}

NAME_QUESTION = "ваше имя и фамилия"
COUNTRY_QUESTION = "где вы территориально находитесь"

def render_final_phrase(phrase: str, contact_link: str) -> str:
    # Гарантируем что {contact_link} заменяется на @линк без лишних скобок/кавычек
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

@dp.message(F.text.lower().in_({"/start", "start"}))
async def welcome(message: Message, state: FSMContext):
    await state.clear()
    user_state[message.from_user.id] = {"answers": {}, "lang": "ru"}
    await message.answer("Выберите язык:", reply_markup=lang_keyboard())
    await state.set_state(SurveyState.lang)

@dp.message(SurveyState.lang)
async def choose_lang(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if text not in ("русский", "рус", "ru"):
        await message.answer("Пожалуйста, выберите язык:", reply_markup=lang_keyboard())
        return
    user_state[message.from_user.id]["lang"] = "ru"
    logo_path = os.path.join(MEDIA_DIR, "logo.jpg")
    if os.path.exists(logo_path):
        await message.answer_photo(FSInputFile(logo_path))
    await message.answer(WELCOME_TEXT["ru"])
    await message.answer("Начнем опрос!", reply_markup=start_keyboard("ru"))
    await state.set_state(SurveyState.wait_start)

@dp.message(SurveyState.wait_start)
async def start_survey(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_state[user_id]["lang"]
    expected = "старт"
    if message.text.strip().lower() != expected:
        await message.answer("Нажмите кнопку 'СТАРТ'!", reply_markup=start_keyboard("ru"))
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
        is_source_q = ("узнали про компанию" in q["question"].lower())
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
            f"Спасибо! Напишите нашему менеджеру {contact_link} для дальнейших инструкций."
        )
        # Корректно вставляем ссылку в финальную фразу
        final_phrase_ready = render_final_phrase(final_phrase, contact_link)
        await message.answer(final_phrase_ready, reply_markup=ReplyKeyboardRemove())
        await send_results_to_admin(
            message.from_user,
            user_state[user_id]["answers"],
            bot,
            contact_link,
            final_phrase
        )
        await state.clear()
        return
    user_state[user_id]["q_idx"] = idx

@dp.message(SurveyState.q)
async def handle_answer(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_state[user_id]["lang"]
    data = load_questions()
    idx = user_state[user_id]["q_idx"]
    questions = data[lang]
    q = questions[idx]
    q_text_lower = q["question"].lower()

    is_name_q = NAME_QUESTION in q_text_lower
    is_country_q = COUNTRY_QUESTION in q_text_lower

    if is_name_q or is_country_q:
        if not re.fullmatch(r"[a-zA-Zа-яА-ЯёЁ\s\-]+", message.text.strip()):
            await message.answer(
                "Пожалуйста, используйте только буквы, пробелы и дефис (без цифр и других символов)!"
            )
            return

    is_source_q = ("узнали про компанию" in q_text_lower)
    if q["type"] == "choice":
        if is_source_q:
            if message.text.strip() == "Другое":
                user_state[user_id]["awaiting_manual_source"] = True
                await state.set_state(SurveyState.wait_custom_source)
                await message.answer(
                    "Пожалуйста, напишите свой вариант (не менее 5 символов):",
                    reply_markup=ReplyKeyboardRemove()
                )
                return
            valid_choices = q["choices"]
            if message.text.strip() not in valid_choices:
                await message.answer(
                    "Пожалуйста, выберите один из предложенных вариантов или 'Другое', если ваш вариант не указан.",
                    reply_markup=choices_keyboard(valid_choices, special_layout=True)
                )
                return
        else:
            valid_choices = [ch.strip() for ch in q["choices"]]
            if message.text.strip() not in valid_choices:
                await message.answer(
                    "Пожалуйста, выберите только 'Да' или 'Нет'!",
                    reply_markup=choices_keyboard(valid_choices)
                )
                return

    user_state[user_id]["answers"][f"q{idx+1}"] = message.text
    is_exp_q = ("опыт в сфере криптовалют" in q_text_lower)
    if is_exp_q:
        if message.text.strip().lower() == "нет":
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
    lang = user_state[user_id]["lang"]
    if len(message.text.strip()) < 5:
        await message.answer(
            "Пожалуйста, ответ должен быть не менее 5 символов!"
        )
        return
    idx = user_state[user_id]["q_idx"]
    user_state[user_id]["answers"][f"q{idx+1}"] = message.text
    user_state[user_id]["q_idx"] = idx + 1
    data = load_questions()
    await state.set_state(SurveyState.q)
    await ask_next_question(message, user_id, lang, data, state)

from aiohttp import web

WEBHOOK_HOST = os.getenv("WEBHOOK_URL")  # например: https://tg-bot-xxxxx.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

async def on_startup(bot):
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook set: {WEBHOOK_URL}")

async def handle(request):
    body = await request.text()
    await dp.feed_webhook_update(bot, request.headers, body)
    return web.Response()

async def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)  # Render ждёт порт 10000
    await site.start()

    await on_startup(bot)
    print("Bot is running with webhook...")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
