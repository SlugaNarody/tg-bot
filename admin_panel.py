from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import json
import os

ADMIN_ID = 7028215322  # замените на ваш Telegram user_id

QUESTIONS_FILE = "questions_data.json"

admin_router = Router()

class AdminState(StatesGroup):
    main = State()
    choose_lang = State()
    choose_question = State()
    edit_text = State()
    edit_link = State()
    edit_text_input = State()
    edit_choices_input = State()
    edit_final_phrase = State()
    edit_final_phrase_input = State()

def load_questions():
    if not os.path.exists(QUESTIONS_FILE):
        return {}
    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_questions(data):
    try:
        with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Проверяем что изменения записались
        with open(QUESTIONS_FILE, encoding="utf-8") as f:
            check = json.load(f)
        if check == data:
            return True
        else:
            return False
    except Exception as ex:
        return False

@admin_router.message(F.text == "/admin")
async def admin_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Изменить вопросы")],
            [KeyboardButton(text="Изменить ссылку менеджера")],
            [KeyboardButton(text="Изменить финальную фразу")],
            [KeyboardButton(text="Выйти")]
        ], resize_keyboard=True)
    await message.answer("Админ-панель:", reply_markup=kb)
    await state.set_state(AdminState.main)

@admin_router.message(AdminState.main, F.text == "Изменить вопросы")
async def admin_choose_lang(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Русский")],[KeyboardButton(text="Назад")]],
        resize_keyboard=True)
    await message.answer("Выберите язык:", reply_markup=kb)
    await state.set_state(AdminState.choose_lang)

@admin_router.message(AdminState.main, F.text == "Изменить ссылку менеджера")
async def admin_edit_link(message: Message, state: FSMContext):
    data = load_questions()
    await message.answer(f"Текущий линк: {data.get('contact_link','')}\n\nОтправьте новый линк (например, @manager):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminState.edit_link)

@admin_router.message(AdminState.main, F.text == "Изменить финальную фразу")
async def admin_edit_final_phrase(message: Message, state: FSMContext):
    data = load_questions()
    final_phrase = data.get("final_phrase", f"Спасибо! Напишите нашему менеджеру {data.get('contact_link','@manager')} для дальнейших инструкций.")
    await message.answer(
        f"Текущая финальная фраза:\n{final_phrase}\n\nВведите новую финальную фразу (можете использовать {{contact_link}} для автоматической подстановки ссылки):",
        reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminState.edit_final_phrase_input)

@admin_router.message(AdminState.edit_final_phrase_input)
async def admin_save_final_phrase(message: Message, state: FSMContext):
    data = load_questions()
    data["final_phrase"] = message.text.strip()
    if save_questions(data):
        await message.answer("Успешно изменено.")
    else:
        await message.answer("Ошибка.")
    await admin_start(message, state)

@admin_router.message(AdminState.main, F.text == "Выйти")
async def admin_exit(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выход из админ-панели.", reply_markup=ReplyKeyboardRemove())

@admin_router.message(AdminState.edit_link)
async def admin_save_link(message: Message, state: FSMContext):
    data = load_questions()
    data["contact_link"] = message.text.strip()
    if save_questions(data):
        await message.answer("Успешно изменено.")
    else:
        await message.answer("Ошибка.")
    await admin_start(message, state)

@admin_router.message(AdminState.choose_lang)
async def admin_choose_question(message: Message, state: FSMContext):
    lang = "ru" if "рус" in message.text.lower() else None
    if not lang:
        await admin_start(message, state)
        return
    data = load_questions()
    qs = data.get(lang, [])
    msg = "Выберите номер вопроса для редактирования:\n"
    for i, q in enumerate(qs):
        msg += f"{i+1}) {q['question']} ({q['type']})\n"
    msg += "\nОтправьте номер вопроса или 'Назад'."
    await state.update_data(lang=lang)
    await message.answer(msg, reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminState.choose_question)

@admin_router.message(AdminState.choose_question)
async def admin_edit_question(message: Message, state: FSMContext):
    if "назад" in message.text.lower():
        await admin_start(message, state)
        return
    try:
        qnum = int(message.text.strip()) - 1
    except Exception:
        await message.answer("Номер вопроса не распознан.")
        return
    data = load_questions()
    sd = await state.get_data()
    lang = sd.get("lang")
    qs = data.get(lang, [])
    if not (0 <= qnum < len(qs)):
        await message.answer("Нет такого вопроса.")
        return
    q = qs[qnum]
    kb = []
    kb.append([KeyboardButton(text="Изменить текст")])
    if q["type"] == "choice":
        kb.append([KeyboardButton(text="Изменить варианты")])
    kb.append([KeyboardButton(text="Назад")])
    await state.update_data(qnum=qnum)
    await message.answer(f"Вопрос: {q['question']}\nТип: {q['type']}", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))
    await state.set_state(AdminState.edit_text)

@admin_router.message(AdminState.edit_text, F.text == "Изменить текст")
async def admin_ask_new_text(message: Message, state: FSMContext):
    await message.answer("Введите новый текст вопроса:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminState.edit_text_input)

@admin_router.message(AdminState.edit_text, F.text == "Изменить варианты")
async def admin_edit_choices(message: Message, state: FSMContext):
    sd = await state.get_data()
    data = load_questions()
    lang = sd.get("lang")
    qnum = sd.get("qnum")
    choices = data[lang][qnum].get("choices",[])
    await message.answer(f"Текущие варианты:\n" + "\n".join(choices) + "\n\nВведите новые варианты через запятую:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminState.edit_choices_input)

@admin_router.message(AdminState.edit_text, F.text == "Назад")
async def admin_back_to_number(message: Message, state: FSMContext):
    await admin_choose_question(message, state)

@admin_router.message(F.state == AdminState.edit_text_input.state)
async def admin_save_new_text(message: Message, state: FSMContext):
    sd = await state.get_data()
    data = load_questions()
    lang = sd.get("lang")
    qnum = sd.get("qnum")
    data[lang][qnum]["question"] = message.text.strip()
    if save_questions(data):
        await message.answer("Успешно изменено.")
    else:
        await message.answer("Ошибка.")
    await admin_choose_question(message, state)

@admin_router.message(F.state == AdminState.edit_choices_input.state)
async def admin_save_new_choices(message: Message, state: FSMContext):
    sd = await state.get_data()
    data = load_questions()
    lang = sd.get("lang")
    qnum = sd.get("qnum")
    new_choices = [c.strip() for c in message.text.split(",") if c.strip()]
    data[lang][qnum]["choices"] = new_choices
    if save_questions(data):
        await message.answer("Успешно изменено.")
    else:
        await message.answer("Ошибка.")
    await admin_choose_question(message, state)
