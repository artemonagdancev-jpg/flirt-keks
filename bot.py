import os
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))  # приклад: -1001234567890
MODERATOR_CHAT_ID = int(os.getenv("MODERATOR_CHAT_ID", "0"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "")  # без @, наприклад "my_ads_bot"

if not TOKEN or not CHANNEL_ID or not MODERATOR_CHAT_ID:
    print("Не задані необхідні змінні середовища: BOT_TOKEN, CHANNEL_ID, MODERATOR_CHAT_ID")
    exit(1)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

DB_PATH = os.getenv("DB_PATH", "bot.db")

# ---- DB helpers ----
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        name TEXT,
        age INTEGER,
        gender TEXT,
        looking_for TEXT,
        content TEXT,
        photo_file_id TEXT,
        tg_username TEXT,
        status TEXT,
        created_at DATETIME DEFAULT (datetime('now','localtime'))
    );
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        is_banned INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT (datetime('now','localtime'))
    );
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS replies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        sender_user_id INTEGER,
        name TEXT,
        age INTEGER,
        gender TEXT,
        content TEXT,
        photo_file_id TEXT,
        created_at DATETIME DEFAULT (datetime('now','localtime'))
    );
    """)
    conn.commit()
    conn.close()

def save_post(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    INSERT INTO posts (user_id,type,name,age,gender,looking_for,content,photo_file_id,tg_username,status)
    VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (data['user_id'], data['type'], data['name'], data['age'], data['gender'], data['looking_for'],
          data['content'], data.get('photo'), data.get('tg_username'), 'pending'))
    conn.commit()
    post_id = c.lastrowid
    conn.close()
    return post_id

def get_post(post_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id,user_id,type,name,age,gender,looking_for,content,photo_file_id,tg_username,status,created_at FROM posts WHERE id=?",(post_id,))
    row = c.fetchone()
    conn.close()
    return row

# ---- States for creating ad ----
class AdForm(StatesGroup):
    type = State()
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    content = State()
    photo = State()
    tg_username = State()
    preview = State()

# ---- Handlers ----
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    text = "Привіт! Це бот оголошень.\nВиберіть дію:"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Створити оголошення", "Переглянути оголошення")
    await message.answer(text, reply_markup=keyboard)

@dp.message_handler(lambda m: m.text == "Створити оголошення")
async def start_create(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Публічне", "Анонімне")
    await message.answer("Оберіть тип оголошення:", reply_markup=kb)
    await AdForm.type.set()

@dp.message_handler(state=AdForm.type)
async def ad_type_chosen(message: types.Message, state: FSMContext):
    ad_type = message.text.lower()
    if ad_type not in ("публічне", "анонімне"):
        await message.answer("Будь ласка, оберіть: Публічне або Анонімне")
        return
    await state.update_data(type=ad_type)
    await AdForm.next()
    await message.answer("Ваше ім'я (можна псевдонім):", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=AdForm.name)
async def ad_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await AdForm.next()
    await message.answer("Вік (введіть число):")

@dp.message_handler(lambda m: not m.text.isdigit(), state=AdForm.age)
async def ad_age_invalid(message: types.Message):
    await message.answer("Введіть, будь ласка, число (вік).")

@dp.message_handler(lambda m: m.text.isdigit(), state=AdForm.age)
async def ad_age(message: types.Message, state: FSMContext):
    await state.update_data(age=int(message.text.strip()))
    await AdForm.next()
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Чоловік", "Жінка", "Пара")
    await message.answer("Вкажіть вашу стать:", reply_markup=kb)

@dp.message_handler(state=AdForm.gender)
async def ad_gender(message: types.Message, state: FSMContext):
    g = message.text
    await state.update_data(gender=g)
    await AdForm.next()
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Чоловік", "Жінка", "Пара", "Без різниці")
    await message.answer("Кого шукаєте?", reply_markup=kb)

@dp.message_handler(state=AdForm.looking_for)
async def ad_looking(message: types.Message, state: FSMContext):
    await state.update_data(looking_for=message.text)
    await AdForm.next()
    await message.answer("Текст оголошення (мінімум 10 символів):", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=AdForm.content)
async def ad_content(message: types.Message, state: FSMContext):
    if len(message.text.strip()) < 10:
        await message.answer("Текст замалий, напишіть детальніше.")
        return
    await state.update_data(content=message.text.strip())
    await AdForm.next()
    await message.answer("Додати фото? Надішліть фото або напишіть /skip")

@dp.message_handler(content_types=['photo'], state=AdForm.photo)
async def ad_photo(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(photo=file_id)
    data = await state.get_data()
    if data['type'] == 'публічне':
        await AdForm.tg_username.set()
        await message.answer("Введіть ваш @username (наприклад @ivan) або /skip якщо нема:")
    else:
        await preview_and_confirm(message, state)

@dp.message_handler(commands=['skip'], state=AdForm.photo)
async def ad_photo_skip(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data['type'] == 'публічне':
        await AdForm.tg_username.set()
        await message.answer("Введіть ваш @username (наприклад @ivan) або /skip якщо нема:")
    else:
        await preview_and_confirm(message, state)

@dp.message_handler(state=AdForm.tg_username)
async def ad_tg_username(message: types.Message, state: FSMContext):
    text = message.text.strip()
    await state.update_data(tg_username=text if text != "/skip" else None)
    await preview_and_confirm(message, state)

async def preview_and_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = f"ПРЕВ'Ю ОГОЛОШЕННЯ\n\nІм'я: {data.get('name')}\nВік: {data.get('age')}\nСтать: {data.get('gender')}\nХто цікавить: {data.get('looking_for')}\n\n{data.get('content')}\n"
    if data.get('tg_username'):
        text += f"\nЛогін: {data.get('tg_username')}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Опублікувати", callback_data="publish"))
    kb.add(types.InlineKeyboardButton("Редагувати", callback_data="edit"))
    await message.answer(text, reply_markup=kb)
    await AdForm.preview.set()

@dp.callback_query_handler(lambda c: c.data == 'edit', state=AdForm.preview)
async def cb_edit(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("Редагування: знову натисніть 'Створити оголошення' у меню.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'publish', state=AdForm.preview)
async def cb_publish(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    user_id = call.from_user.id

    # Перевірка підписки - робиться лише зараз (Soft варіант)
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        stat = member.status
        if stat not in ('member','creator','administrator'):
            # не підписаний
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Перевірити підписку", url=f"https://t.me/{os.getenv('CHANNEL_USERNAME','yourchannel')}"))
            await call.message.answer("❗ Для публікації ви маєте бути підписані на канал. Підпишіться і натисніть «Перевірити підписку».", reply_markup=kb)
            await state.finish()
            return
    except Exception as e:
        logging.exception("check subscription failed")
        # якщо помилка — дозволимо пройти (щоб не блокувати тестування)
        pass

    post = {
        'user_id': user_id,
        'type': data.get('type'),
        'name': data.get('name'),
        'age': data.get('age'),
        'gender': data.get('gender'),
        'looking_for': data.get('looking_for'),
        'content': data.get('content'),
        'photo': data.get('photo'),
        'tg_username': data.get('tg_username'),
    }
    post_id = save_post(post)

    # Надіслати модератору
    text = f"Нове оголошення #{post_id}\n\nІм'я: {post['name']}\nВік: {post['age']}\nСтать: {post['gender']}\nХто: {post['looking_for']}\n\n{post['content']}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Approve", callback_data=f"approve:{post_id}"))
    kb.add(types.InlineKeyboardButton("Reject", callback_data=f"reject:{post_id}"))
    if post.get('photo'):
        await bot.send_photo(MODERATOR_CHAT_ID, post['photo'], caption=text, reply_markup=kb)
    else:
        await bot.send_message(MODERATOR_CHAT_ID, text, reply_markup=kb)

    await call.message.answer("Оголошення надіслано на модерацію. Дякуємо!")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('approve:'))
async def cb_approve(call: types.CallbackQuery):
    await call.answer()
    post_id = int(call.data.split(':')[1])
    row = get_post(post_id)
    if not row:
        await call.message.answer("Оголошення не знайдено.")
        return
    # Оновлюємо статус
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE posts SET status='approved' WHERE id=?", (post_id,))
    conn.commit()
    conn.close()

    # Публікуємо у канал
    _, user_id, ad_type, name, age, gender, looking_for, content, photo_file_id, tg_username, status, created_at = row
    text = f"📌 Оголошення #{post_id}\n\n👤 {name}, {age}\n⚪ Стать: {gender}\n🔎 Шукає: {looking_for}\n\n{content}\n\n📅 {created_at}"
    if ad_type == 'публічне' and tg_username:
        text += f"\n\n@{tg_username.lstrip('@')}"
    # Створюємо посилання відповіді через deep link
    if BOT_USERNAME:
        reply_link = f"https://t.me/{BOT_USERNAME}?start=reply_{post_id}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Відповісти", url=reply_link))
    else:
        kb = None

    if photo_file_id:
        await bot.send_photo(CHANNEL_ID, photo_file_id, caption=text, reply_markup=kb)
    else:
        await bot.send_message(CHANNEL_ID, text, reply_markup=kb)

    await call.message.answer(f"Оголошення #{post_id} опубліковане.")
    
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('reject:'))
async def cb_reject(call: types.CallbackQuery):
    await call.answer()
    post_id = int(call.data.split(':')[1])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE posts SET status='rejected' WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    await call.message.answer(f"Оголошення #{post_id} відхилено.")

# Simple handler for deep-link start=reply_123
@dp.message_handler(lambda m: m.text and m.text.startswith('/start reply_'))
async def deep_reply_handler(message: types.Message):
    # формально Telegram надсилає параметр у format: /start reply_123 якщо юзер відкрив бот через посилання
    await message.answer("Ви хочете відповісти на оголошення. Заповніть, будь ласка, коротку форму.")
    # тут ми можемо стартувати FSM для відповіді — пропущено для стислості

if __name__ == "__main__":
    init_db()
    executor.start_polling(dp, skip_updates=True)
