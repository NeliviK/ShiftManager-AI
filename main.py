# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import json
from datetime import datetime, timezone, timedelta

import aiohttp
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Telegram libraries
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InputMediaPhoto, InputMediaDocument, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

from dotenv import load_dotenv
from api_provider import load_accounts, get_account_profit, accounts_cache, api_get_accounts
load_dotenv()

# ==================== LOGGING ====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ==================== SAFE ENV LOADING & AUTH ====================
def get_env_int(key, default=0):
    val = os.getenv(key, "")
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        logging.error(f"⚠️ Ошибка чтения переменной {key}: '{val}' не является числом. Использую {default}")
        return default

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logging.critical("⛔ НЕТ ТОКЕНА БОТА! Установите BOT_TOKEN в .env")

# Bulletproof ID parsing (Collects IDs from all possible variable names)
SUPER_ADMIN_ID = get_env_int("SUPER_ADMIN_ID", 0)
MANAGERS_IDS = [SUPER_ADMIN_ID] if SUPER_ADMIN_ID else []

for env_key in ["MANAGERS_IDS", "ADMIN_IDS", "SUPER_ADMIN_ID"]:
    raw_ids = os.getenv(env_key, "")
    for _x in raw_ids.split(","):
        _x = _x.strip()
        if _x.isdigit() and int(_x) not in MANAGERS_IDS:
            MANAGERS_IDS.append(int(_x))

ARCHIVE_CHANNEL_ID = get_env_int("ARCHIVE_CHANNEL_ID", 0)
REPORT_GROUP_ID  = get_env_int("REPORT_GROUP_ID", 0)
REPORT_TOPIC_ID  = get_env_int("REPORT_TOPIC_ID", 0)
STATUS_GROUP_ID  = get_env_int("STATUS_GROUP_ID", 0)
STATUS_TOPIC_ID  = get_env_int("STATUS_TOPIC_ID", 0)

# Dynamic models loading (Optional routing)
MODELS = {}
_i = 1
while True:
    m_name = os.getenv(f"MODEL_{_i}_NAME")
    if not m_name:
        break
    m_group = get_env_int(f"MODEL_{_i}_GROUP", REPORT_GROUP_ID)
    m_topic = get_env_int(f"MODEL_{_i}_TOPIC", REPORT_TOPIC_ID)
    MODELS[m_name] = {'group': m_group, 'topic': m_topic}
    _i += 1

# ==================== ROLE MANAGEMENT (JSON) ====================
ROLES_FILE = "roles.json"
ROLES = {
    'curator': {'id': 0, 'name': 'Куратор'},
    'teamlead': {'id': 0, 'name': 'Тім Лід'}
}

def save_roles():
    try:
        with open(ROLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(ROLES, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving roles: {e}")

def load_roles():
    global ROLES
    if os.path.exists(ROLES_FILE):
        try:
            with open(ROLES_FILE, 'r', encoding='utf-8') as f:
                saved_roles = json.load(f)
                ROLES['curator']['id'] = saved_roles.get('curator', {}).get('id', 0)
                ROLES['teamlead']['id'] = saved_roles.get('teamlead', {}).get('id', 0)
        except Exception as e:
            logging.error(f"Error loading roles: {e}")
    else:
        # Create default roles file if it doesn't exist
        save_roles()

load_roles()

# ==================== TEXTS (i18n) ====================
TEXTS = {
    'ua': {
        'start': "👋 Привіт! Оберіть мову / Choose language:",
        'menu': "🎛 Головне меню",
        'btn_open': "🟢 Відкрити зміну",
        'btn_close': "🔴 Закрити зміну",
        'btn_custom': "🟣 Order Custom",
        'btn_promo': "💎 Підвищення",
        'btn_lang': "🌍 Змінити мову",
        'btn_confirm': "✅ Все вірно",
        'btn_edit': "📝 Виправити",
        'btn_back': "🔙 Назад",
        'btn_main': "🏠 Головна",
        'btn_yes': "Так",
        'btn_no': "Ні",

        'open_start': "🚀 <b>Розпочинаємо зміну!</b>",
        'close_start': "🏁 <b>Завершуємо зміну!</b>\n⏳ Отримуємо дані з API...",
        'shift_opened': "✅ <b>Зміна ВІДКРИТА!</b>\nДані зафіксовані.",
        'shift_closed': "🏁 <b>Зміна ЗАКРИТА!</b>",
        'error_no_shift': "⚠️ Ви ще не відкрили зміну!",
        'error_already_open': "⚠️ У вас вже є відкрита зміна!",
        'archive_open_caption': "#OPEN\n👤 {user}\n📅 {date}\n\n{details}",
        'report_header': "🏁 <b>ЗВІТ ЗМІНИ</b>\n👤 {user}\n\n{details}\n",
        'total': "\n💰 <b>Разом профіт: {profit:+.2f}$</b>",

        'cust_select_model': "🎭 <b>Оберіть модель (Актора):</b>\nКуди полетить замовлення?",
        'cust_select_approver': "👮‍♂️ <b>Хто погодив сценарій?</b>",
        'cust_approver_actor': "Сама Модель",
        'cust_ask_duration': "⏱ <b>Скільки хвилин?</b>\nВведіть ТІЛЬКИ цифру (наприклад: 5, 10).",
        'cust_ask_scenario': "🎬 <b>Розпиши детально сценарій по пунктам:</b>\nНа ту кількість хвилин, яку ти вказав.",
        'cust_ask_speech': "🗣 <b>Треба щось говорити?</b>",
        'cust_ask_speech_details': "📝 <b>Напиши текст, який треба сказати:</b>",
        'cust_ask_music': "🎵 <b>Музика потрібна?</b>",
        'cust_ask_music_details': "🎼 <b>Яка саме музика?</b>",
        'cust_music_default': "По бажанню моделі",
        'cust_speech_default': "По бажанню моделі",
        'cust_ask_wishes': "✨ <b>Є особливі побажання?</b>",
        'cust_ask_wishes_details': "✍️ <b>Опиши побажання:</b>",
        'cust_wishes_default': "Немає",
        'cust_ask_price': "💰 <b>Ціна замовлення ($)?</b>\nВведи только число (наприклад: 500).",
        'cust_ask_paid': "💸 <b>Оплата вже була?</b>",
        'cust_ask_pay_method': "💳 <b>Оберіть спосіб оплати:</b>",
        'cust_ask_pay_amount': "💵 <b>Скільки заплатили?</b>\nВведи тільки суму (наприклад: 300).",
        'cust_ask_screen': "📸 <b>Надішли скріншот оплати/профілю</b>",
        'cust_screen_example_txt': "💡 <b>Приклад того, що я очікую:</b>",
        'cust_review_header': "📊 <b>ПЕРЕВІРКА ЗАМОВЛЕННЯ</b>\n\n",
        'sent_success': "✅ <b>Замовлення успішно відправлено в групу {model}!</b>",
        'debt_note_txt': "⚠️ <b>(При скиданні встановити ціну!)</b>",

        'promo_menu': "💎 <b>УПРАВЛІННЯ ПЕРСОНАЛОМ</b>\n\nТут ви можете змінити Куратора або Тім Ліда.\n\n👤 <b>Поточний Куратор:</b> <a href='tg://user?id={c_id}'>LINK</a> (ID: {c_id})\n👤 <b>Поточний Тім Лід:</b> <a href='tg://user?id={t_id}'>LINK</a> (ID: {t_id})",
        'promo_select': "Кого будемо міняти?",
        'promo_ask_id': "🆔 <b>Надішли ID нового співробітника:</b>\nМожна тільки цифри.",
        'promo_success': "✅ <b>Успішно!</b> Новий {role} встановлений.",
        'promo_denied': "⛔ <b>Особу не ідентифіковано!</b>\nЗверніться до Тім Ліда."
    },
    'en': {
        'start': "👋 Hello! Choose language:",
        'menu': "🎛 Main Menu",
        'btn_open': "🟢 Start Shift",
        'btn_close': "🔴 End Shift",
        'btn_custom': "🟣 Order Custom",
        'btn_promo': "💎 HR / Promotion",
        'btn_lang': "🌍 Change Lang",
        'btn_confirm': "✅ Confirm",
        'btn_edit': "📝 Edit",
        'btn_back': "🔙 Back",
        'btn_main': "🏠 Main Menu",
        'btn_yes': "Yes",
        'btn_no': "No",
        
        'open_start': "🚀 <b>Starting shift!</b>",
        'close_start': "🏁 <b>Ending shift!</b>\n⏳ Fetching data from API...",
        'shift_opened': "✅ <b>Shift STARTED!</b>",
        'shift_closed': "🏁 <b>Shift ENDED!</b>",
        'error_no_shift': "⚠️ No active shift!",
        'error_already_open': "⚠️ Shift already active!",
        'archive_open_caption': "#OPEN\n👤 {user}\n📅 {date}\n\n{details}",
        'report_header': "🏁 <b>SHIFT REPORT</b>\n👤 {user}\n\n{details}\n",
        'total': "\n💰 <b>Total: {profit:+.2f}$</b>",

        'cust_select_model': "🎭 <b>Select Model:</b>",
        'cust_select_approver': "👮‍♂️ <b>Approved by:</b>",
        'cust_approver_actor': "Model Herself",
        'cust_ask_duration': "⏱ <b>Duration (minutes)?</b>\nDigits only.",
        'cust_ask_scenario': "🎬 <b>Scenario Details:</b>\nList step by step.",
        'cust_ask_speech': "🗣 <b>Need to speak?</b>",
        'cust_ask_speech_details': "📝 <b>What to say?</b>",
        'cust_ask_music': "🎵 <b>Music?</b>",
        'cust_ask_music_details': "🎼 <b>Which music?</b>",
        'cust_music_default': "Model's discretion",
        'cust_speech_default': "Model's discretion",
        'cust_ask_wishes': "✨ <b>Wishes?</b>",
        'cust_ask_wishes_details': "✍️ <b>Details:</b>",
        'cust_wishes_default': "None",
        'cust_ask_price': "💰 <b>Price ($)?</b>",
        'cust_ask_paid': "💸 <b>Paid?</b>",
        'cust_ask_pay_method': "💳 <b>Method:</b>",
        'cust_ask_pay_amount': "💵 <b>Amount?</b>",
        'cust_ask_screen': "📸 <b>Send screenshot</b>",
        'cust_screen_example_txt': "💡 Example:",
        'cust_review_header': "📊 <b>REVIEW</b>\n\n",
        'sent_success': "✅ <b>Sent!</b>",
        'debt_note_txt': "⚠️ <b>(Set price on reset!)</b>",
        
        'promo_menu': "💎 <b>HR MANAGEMENT</b>\n\nCurator ID: {c_id}\nTeamLead ID: {t_id}",
        'promo_select': "Who to change?",
        'promo_ask_id': "🆔 <b>Send new ID:</b>",
        'promo_success': "✅ <b>Success!</b> {role} updated.",
        'promo_denied': "⛔ <b>Access Denied!</b>"
    }
}

# ==================== INITIALIZATION ====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

active_shifts = {}
user_langs = {}
last_status_message_id = None

DB_PATH = "bot_data.db"

# ==================== FSM STATES ====================
class BotStates(StatesGroup):
    select_lang = State()
    main_menu = State()

    cust_model = State()
    cust_approver = State()
    cust_duration = State()
    cust_scenario = State()
    cust_speech_check = State()
    cust_speech_details = State()
    cust_music_check = State()
    cust_music_details = State()
    cust_wishes_check = State()
    cust_wishes_details = State()
    cust_price = State()
    cust_paid_check = State()
    cust_pay_method = State()
    cust_pay_amount = State()
    cust_ask_screen = State()
    cust_wait_screen = State()
    cust_review = State()

    promo_select_role = State()
    promo_wait_id = State()

# ==================== DATABASE ====================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shifts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                telegram_name TEXT NOT NULL,
                profit      REAL NOT NULL,
                shift_date  TIMESTAMP NOT NULL,
                month_year  TEXT NOT NULL
            )
        """)
        await db.commit()
    logging.info("✅ Database initialised: bot_data.db")

async def save_shift_to_db(user_id: int, telegram_name: str, profit: float):
    now = datetime.now()
    month_year = now.strftime("%m-%Y")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO shifts (user_id, telegram_name, profit, shift_date, month_year) VALUES (?, ?, ?, ?, ?)",
            (user_id, telegram_name, profit, now.isoformat(), month_year)
        )
        await db.commit()
    logging.info(f"💾 Shift saved: user_id={user_id}, profit={profit}, month={month_year}")

# ==================== APSCHEDULER — MONTHLY REPORT ====================
async def send_monthly_report():
    now = datetime.now()
    first_of_this_month = now.replace(day=1)
    prev_month_dt = first_of_this_month - timedelta(days=1)
    prev_month_year = prev_month_dt.strftime("%m-%Y")
    logging.info(f"📊 Generating monthly report for: {prev_month_year}")

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT user_id, telegram_name, SUM(profit) AS total_profit
                FROM shifts
                WHERE month_year = ?
                GROUP BY user_id
                ORDER BY total_profit DESC
                """,
                (prev_month_year,)
            )
            rows = await cursor.fetchall()
    except Exception as e:
        logging.error(f"Monthly report DB error: {e}")
        return

    if not rows:
        report_text = f"📊 <b>Підсумки за {prev_month_year}:</b>\n\n<i>Даних немає.</i>"
    else:
        lines = [f"📊 <b>Підсумки за минулий місяць ({prev_month_year}):</b>\n"]
        for row in rows:
            uid  = row["user_id"]
            name = row["telegram_name"]
            tot  = row["total_profit"]
            lines.append(f"<a href='tg://user?id={uid}'>{name}</a> — {tot:.2f}$")
        report_text = "\n".join(lines)

    if REPORT_GROUP_ID:
        try:
            await bot.send_message(
                chat_id=REPORT_GROUP_ID,
                text=report_text,
                message_thread_id=REPORT_TOPIC_ID if REPORT_TOPIC_ID else None,
                parse_mode="HTML"
            )
            logging.info("✅ Monthly report sent.")
        except Exception as e:
            logging.error(f"Failed to send monthly report: {e}")

# ==================== HELPERS ====================
async def safe_delete(chat_id, msg_id):
    try: await bot.delete_message(chat_id, msg_id)
    except Exception: pass

async def clear_ui(chat_id: int, state: FSMContext):
    data = await state.get_data()
    ids = data.get('msgs_to_del', [])
    for m_id in ids: await safe_delete(chat_id, m_id)
    await state.update_data(msgs_to_del=[])

async def track(state: FSMContext, msg_id: int):
    data = await state.get_data()
    ids = data.get('msgs_to_del', [])
    if msg_id not in ids: ids.append(msg_id)
    await state.update_data(msgs_to_del=ids)

def get_txt(uid, key, **kwargs):
    lang = user_langs.get(uid, 'ua')
    text = TEXTS[lang].get(key, key)
    if kwargs: return text.format(**kwargs)
    return text

def is_admin(uid: int) -> bool:
    return uid in MANAGERS_IDS

# ==================== STATUS VIEW ====================
async def update_status_view():
    global last_status_message_id
    if not STATUS_GROUP_ID: return
    if active_shifts:
        lines = [f"👤 <a href='tg://user?id={uid}'>{d.get('name', 'Unknown')}</a>" for uid, d in active_shifts.items()]
        current_text = "🟢 <b>ОНЛАЙН НА ЗМІНІ:</b>\n" + "\n".join(lines)
    else:
        current_text = "💤 <b>На зміні нікого немає.</b>"

    try:
        if last_status_message_id:
            try:
                await bot.edit_message_text(
                    text=current_text,
                    chat_id=STATUS_GROUP_ID,
                    message_id=last_status_message_id,
                    parse_mode="HTML"
                )
                return
            except TelegramBadRequest:
                last_status_message_id = None

        msg = await bot.send_message(
            chat_id=STATUS_GROUP_ID,
            text=current_text,
            message_thread_id=STATUS_TOPIC_ID if STATUS_TOPIC_ID else None,
            disable_notification=True
        )
        try:
            await bot.pin_chat_message(chat_id=STATUS_GROUP_ID, message_id=msg.message_id, disable_notification=True)
        except Exception:
            pass
        last_status_message_id = msg.message_id
    except Exception as e:
        logging.error(f"Status Update Error: {e}")

# ==================== KEYBOARDS ====================
def kb_langs():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🇺🇦 Українська"), KeyboardButton(text="🇺🇸 English")]],
        resize_keyboard=True
    )

def kb_main(uid):
    lang = user_langs.get(uid, 'ua')
    t = TEXTS[lang]
    rows = [
        [KeyboardButton(text=t['btn_open']), KeyboardButton(text=t['btn_close'])],
        [KeyboardButton(text=t['btn_custom']), KeyboardButton(text=t['btn_lang'])]
    ]
    # Show Promotion HR Management ONLY to Super Admin
    if uid == SUPER_ADMIN_ID:
        rows.append([KeyboardButton(text=t['btn_promo'])])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def kb_nav(uid, extras=None):
    lang = user_langs.get(uid, 'ua')
    t = TEXTS[lang]
    row = [KeyboardButton(text=t['btn_back']), KeyboardButton(text=t['btn_main'])]
    kb = []
    if extras: kb.extend(extras)
    kb.append(row)
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def kb_yes_no(uid):
    lang = user_langs.get(uid, 'ua')
    t = TEXTS[lang]
    return kb_nav(uid, [[KeyboardButton(text=t['btn_yes']), KeyboardButton(text=t['btn_no'])]])

def kb_models_dynamic(uid, account_names: list[str]):
    buttons = [[KeyboardButton(text=name)] for name in account_names]
    return kb_nav(uid, buttons)

def kb_approvers(uid):
    lang = user_langs.get(uid, 'ua')
    t = TEXTS[lang]
    buttons = [
        [KeyboardButton(text=ROLES['curator']['name'])],
        [KeyboardButton(text=ROLES['teamlead']['name'])],
        [KeyboardButton(text=t['cust_approver_actor'])]
    ]
    return kb_nav(uid, buttons)

def kb_pay_methods(uid):
    return kb_nav(uid, [[KeyboardButton(text="Tip"), KeyboardButton(text="PayPal")], [KeyboardButton(text="Spent")]])

def kb_roles_select(uid):
    return kb_nav(uid, [[KeyboardButton(text="Куратор")], [KeyboardButton(text="Тім Лід")]])

def kb_custom_final(uid):
    lang = user_langs.get(uid, 'ua')
    t = TEXTS[lang]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t['btn_confirm'])], [KeyboardButton(text=t['btn_main'])]],
        resize_keyboard=True
    )

# ==================== HANDLERS ====================

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    logging.info(f"User {uid} sent /start command.")

    await state.clear()
    await clear_ui(message.chat.id, state)

    if not is_admin(uid):
        logging.warning(f"User {uid} ACCESS DENIED.")
        await message.answer("⛔ Доступ заборонено. Зверніться до адміністратора.")
        return

    await state.set_state(BotStates.select_lang)
    msg = await message.answer(TEXTS['ua']['start'], reply_markup=kb_langs())
    await track(state, msg.message_id)

@router.message(BotStates.select_lang)
async def set_language(message: types.Message, state: FSMContext):
    user_langs[message.from_user.id] = 'en' if "English" in message.text else 'ua'
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.main_menu)
    await message.answer(get_txt(message.from_user.id, 'menu'), reply_markup=kb_main(message.from_user.id))

@router.message(F.text.in_([TEXTS['ua']['btn_main'], TEXTS['en']['btn_main']]))
async def go_main(message: types.Message, state: FSMContext):
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.main_menu)
    await message.answer(get_txt(message.from_user.id, 'menu'), reply_markup=kb_main(message.from_user.id))

@router.message(F.text.in_([TEXTS['ua']['btn_back'], TEXTS['en']['btn_back']]))
async def go_back(message: types.Message, state: FSMContext):
    await go_main(message, state)

@router.message(F.text.in_([TEXTS['ua']['btn_lang'], TEXTS['en']['btn_lang']]))
async def change_lang(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.select_lang)
    await message.answer(TEXTS['ua']['start'], reply_markup=kb_langs())

# --- PROMOTION (HR MANAGEMENT) ---
@router.message(F.text.in_([TEXTS['ua']['btn_promo'], TEXTS['en']['btn_promo']]))
async def promo_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid != SUPER_ADMIN_ID:
        await message.answer("⛔ Access Denied")
        return
    await clear_ui(message.chat.id, state)
    c_id = ROLES['curator']['id']
    t_id = ROLES['teamlead']['id']
    info_txt = get_txt(uid, 'promo_menu', c_id=c_id, t_id=t_id)
    await message.answer(info_txt)
    await state.set_state(BotStates.promo_select_role)
    msg = await message.answer(get_txt(uid, 'promo_select'), reply_markup=kb_roles_select(uid))
    await track(state, msg.message_id)

@router.message(BotStates.promo_select_role)
async def promo_role_selected(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    role_key = 'curator' if "Куратор" in message.text else 'teamlead'
    await state.update_data(role_to_change=role_key)
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.promo_wait_id)
    msg = await message.answer(get_txt(message.from_user.id, 'promo_ask_id'), reply_markup=kb_nav(message.from_user.id))
    await track(state, msg.message_id)

@router.message(BotStates.promo_wait_id)
async def promo_id_received(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    try:
        new_id = int(message.text.strip())
        data = await state.get_data()
        role_key = data.get('role_to_change', 'teamlead')
        ROLES[role_key]['id'] = new_id
        save_roles()
        await message.answer(
            get_txt(message.from_user.id, 'promo_success', role=ROLES[role_key]['name']),
            reply_markup=kb_main(message.from_user.id)
        )
        await state.set_state(BotStates.main_menu)
    except ValueError:
        await message.answer("⚠️ ID must be a number! Try again.")

# ==================== SHIFT HANDLERS ====================

@router.message(F.text.in_([TEXTS['ua']['btn_open'], TEXTS['en']['btn_open']]))
async def open_shift(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid in active_shifts:
        await message.answer(get_txt(uid, 'error_already_open'))
        return

    await load_accounts()
    start_time_utc = datetime.now(timezone.utc)
    active_shifts[uid] = {
        'start_time_utc': start_time_utc,
        'start_time_local': datetime.now(),
        'name': message.from_user.full_name
    }
    await update_status_view()

    if ARCHIVE_CHANNEL_ID:
        try:
            caption = get_txt(
                uid, 'archive_open_caption',
                user=f"{message.from_user.full_name} (ID: {uid})",
                date=datetime.now().strftime('%d.%m %H:%M'),
                details=f"⏰ Старт: {start_time_utc.strftime('%H:%M UTC')}"
            )
            await bot.send_message(ARCHIVE_CHANNEL_ID, caption, disable_notification=True)
        except Exception as e:
            logging.error(f"Archive send error: {e}")

    await message.answer(get_txt(uid, 'shift_opened'), reply_markup=kb_main(uid))

@router.message(F.text.in_([TEXTS['ua']['btn_close'], TEXTS['en']['btn_close']]))
async def close_shift(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in active_shifts:
        await message.answer(get_txt(uid, 'error_no_shift'))
        return

    end_time_utc = datetime.now(timezone.utc)
    start_time_utc: datetime = active_shifts[uid]['start_time_utc']
    start_time_local: datetime = active_shifts[uid]['start_time_local']
    user_name = message.from_user.full_name

    wait_msg = await message.answer(get_txt(uid, 'close_start'), reply_markup=ReplyKeyboardRemove())

    total_profit = 0.0
    details_text = ""
    
    accounts_to_check = list(accounts_cache.keys())
    if not accounts_to_check:
        await load_accounts()
        accounts_to_check = list(accounts_cache.keys())

    try:
        for acc_name in accounts_to_check:
            profit = await get_account_profit(acc_name, start_time_utc, end_time_utc)
            total_profit += profit
            details_text += f"📱 {acc_name} — 💰 Профіт: {profit:+.2f}$\n"
    except Exception as e:
        logging.error(f"Shift close API error: {e}")
        details_text += f"⚠️ Помилка API: {e}\n"

    details_text += get_txt(uid, 'total', profit=total_profit)

    end_time_local = datetime.now()
    duration = end_time_local - start_time_local
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    time_range = f"{start_time_local.strftime('%H:%M')} - {end_time_local.strftime('%H:%M')}"
    user_display = f"{user_name} (ID: {uid})"
    report_text = get_txt(uid, 'report_header', user=user_display, time_range=time_range, duration=f"{hours}h {minutes}m", details=details_text)

    try:
        await bot.delete_message(message.chat.id, wait_msg.message_id)
    except Exception:
        pass

    await message.answer(report_text, reply_markup=kb_main(uid))

    if REPORT_GROUP_ID:
        try:
            await bot.send_message(
                REPORT_GROUP_ID,
                report_text,
                message_thread_id=REPORT_TOPIC_ID if REPORT_TOPIC_ID else None
            )
        except Exception as e:
            logging.error(f"Failed to send report to group: {e}")

    try:
        await save_shift_to_db(uid, user_name, total_profit)
    except Exception as e:
        logging.error(f"Failed to save shift to DB: {e}")

    del active_shifts[uid]
    await update_status_view()

# ==================== CUSTOM ORDER FSM ====================

@router.message(F.text.contains("Order Custom"))
async def start_custom(message: types.Message, state: FSMContext):
    logging.info(f"Custom Order started by {message.from_user.id}")
    await clear_ui(message.chat.id, state)
    await state.set_data({'custom': {}})
    await state.set_state(BotStates.cust_model)
    await ask_custom_step(message, state, 'cust_model')

async def ask_custom_step(message, state, step_key):
    uid = message.from_user.id
    msg = None
    if step_key == 'cust_model':
        api_accounts = await api_get_accounts()
        account_names = [a.get("name", "") for a in api_accounts if a.get("name")]
        if not account_names:
            account_names = list(MODELS.keys())
        await state.update_data(api_account_names=account_names)
        kb = kb_models_dynamic(uid, account_names)
        msg = await message.answer(get_txt(uid, 'cust_select_model'), reply_markup=kb)
    elif step_key == 'cust_approver':
        msg = await message.answer(get_txt(uid, 'cust_select_approver'), reply_markup=kb_approvers(uid))
    elif step_key == 'cust_duration':
        msg = await message.answer(get_txt(uid, 'cust_ask_duration'), reply_markup=kb_nav(uid))
    elif step_key == 'cust_scenario':
        msg = await message.answer(get_txt(uid, 'cust_ask_scenario'), reply_markup=kb_nav(uid))
    elif step_key == 'cust_speech_check':
        msg = await message.answer(get_txt(uid, 'cust_ask_speech'), reply_markup=kb_yes_no(uid))
    elif step_key == 'cust_speech_details':
        msg = await message.answer(get_txt(uid, 'cust_ask_speech_details'), reply_markup=kb_nav(uid))
    elif step_key == 'cust_music_check':
        msg = await message.answer(get_txt(uid, 'cust_ask_music'), reply_markup=kb_yes_no(uid))
    elif step_key == 'cust_music_details':
        msg = await message.answer(get_txt(uid, 'cust_ask_music_details'), reply_markup=kb_nav(uid))
    elif step_key == 'cust_wishes_check':
        msg = await message.answer(get_txt(uid, 'cust_ask_wishes'), reply_markup=kb_yes_no(uid))
    elif step_key == 'cust_wishes_details':
        msg = await message.answer(get_txt(uid, 'cust_ask_wishes_details'), reply_markup=kb_nav(uid))
    elif step_key == 'cust_price':
        msg = await message.answer(get_txt(uid, 'cust_ask_price'), reply_markup=kb_nav(uid))
    elif step_key == 'cust_paid_check':
        msg = await message.answer(get_txt(uid, 'cust_ask_paid'), reply_markup=kb_yes_no(uid))
    elif step_key == 'cust_pay_method':
        msg = await message.answer(get_txt(uid, 'cust_ask_pay_method'), reply_markup=kb_pay_methods(uid))
    elif step_key == 'cust_pay_amount':
        msg = await message.answer(get_txt(uid, 'cust_ask_pay_amount'), reply_markup=kb_nav(uid))
    elif step_key == 'cust_ask_screen':
        example_path = "example.jpg"
        if not os.path.exists(example_path): example_path = "example.png"
        if os.path.exists(example_path):
            try:
                photo_file = FSInputFile(example_path)
                await message.answer_photo(photo_file, caption=get_txt(uid, 'cust_screen_example_txt'))
            except Exception:
                pass
        msg = await message.answer(get_txt(uid, 'cust_ask_screen'), reply_markup=kb_nav(uid))
        await state.set_state(BotStates.cust_wait_screen)
    if msg: await track(state, msg.message_id)

@router.message(BotStates.cust_model)
async def custom_model_chosen(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    uid = message.from_user.id
    data = await state.get_data()
    valid_names = data.get('api_account_names', list(MODELS.keys()))
    if message.text not in valid_names:
        msg = await message.answer("Please select from the buttons / Оберіть зі списку.")
        await track(state, msg.message_id)
        return
    data['custom']['model_name'] = message.text
    if message.text in MODELS:
        data['custom']['model_data'] = MODELS[message.text]
    else:
        data['custom']['model_data'] = {'group': REPORT_GROUP_ID, 'topic': REPORT_TOPIC_ID}
    await state.update_data(data)
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.cust_approver)
    await ask_custom_step(message, state, 'cust_approver')

@router.message(BotStates.cust_approver)
async def custom_approver_chosen(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    approver_name = message.text
    approver_id = None
    if approver_name == ROLES['curator']['name']:
        approver_id = ROLES['curator']['id']
    elif approver_name == ROLES['teamlead']['name']:
        approver_id = ROLES['teamlead']['id']
    data = await state.get_data()
    data['custom']['approver_name'] = approver_name
    data['custom']['approver_id'] = approver_id
    await state.update_data(data)
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.cust_duration)
    await ask_custom_step(message, state, 'cust_duration')

@router.message(BotStates.cust_duration)
async def custom_duration_set(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    raw_text = message.text.strip()
    final_text = f"{raw_text} хв" if raw_text.isdigit() else raw_text
    data = await state.get_data()
    data['custom']['duration'] = final_text
    await state.update_data(data)
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.cust_scenario)
    await ask_custom_step(message, state, 'cust_scenario')

@router.message(BotStates.cust_scenario)
async def custom_scenario_set(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    lines = message.text.split('\n')
    formatted_scenario = ""
    idx = 1
    for line in lines:
        if line.strip():
            formatted_scenario += f"{idx}️⃣ {line.strip()}\n"
            idx += 1
    data = await state.get_data()
    data['custom']['scenario'] = formatted_scenario
    await state.update_data(data)
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.cust_speech_check)
    await ask_custom_step(message, state, 'cust_speech_check')

@router.message(BotStates.cust_speech_check)
async def custom_speech_check(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    await track(state, message.message_id)
    is_yes = message.text in [TEXTS['ua']['btn_yes'], TEXTS['en']['btn_yes']]
    await clear_ui(message.chat.id, state)
    if is_yes:
        await state.set_state(BotStates.cust_speech_details)
        await ask_custom_step(message, state, 'cust_speech_details')
    else:
        data = await state.get_data()
        data['custom']['speech'] = get_txt(uid, 'cust_speech_default')
        await state.update_data(data)
        await state.set_state(BotStates.cust_music_check)
        await ask_custom_step(message, state, 'cust_music_check')

@router.message(BotStates.cust_speech_details)
async def custom_speech_details(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    data = await state.get_data()
    data['custom']['speech'] = message.text
    await state.update_data(data)
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.cust_music_check)
    await ask_custom_step(message, state, 'cust_music_check')

@router.message(BotStates.cust_music_check)
async def custom_music_check(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    await track(state, message.message_id)
    is_yes = message.text in [TEXTS['ua']['btn_yes'], TEXTS['en']['btn_yes']]
    await clear_ui(message.chat.id, state)
    if is_yes:
        await state.set_state(BotStates.cust_music_details)
        await ask_custom_step(message, state, 'cust_music_details')
    else:
        data = await state.get_data()
        data['custom']['music'] = get_txt(uid, 'cust_music_default')
        await state.update_data(data)
        await state.set_state(BotStates.cust_wishes_check)
        await ask_custom_step(message, state, 'cust_wishes_check')

@router.message(BotStates.cust_music_details)
async def custom_music_details(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    data = await state.get_data()
    data['custom']['music'] = message.text
    await state.update_data(data)
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.cust_wishes_check)
    await ask_custom_step(message, state, 'cust_wishes_check')

@router.message(BotStates.cust_wishes_check)
async def custom_wishes_check(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    await track(state, message.message_id)
    is_yes = message.text in [TEXTS['ua']['btn_yes'], TEXTS['en']['btn_yes']]
    await clear_ui(message.chat.id, state)
    if is_yes:
        await state.set_state(BotStates.cust_wishes_details)
        await ask_custom_step(message, state, 'cust_wishes_details')
    else:
        data = await state.get_data()
        data['custom']['wishes'] = get_txt(uid, 'cust_wishes_default')
        await state.update_data(data)
        await state.set_state(BotStates.cust_price)
        await ask_custom_step(message, state, 'cust_price')

@router.message(BotStates.cust_wishes_details)
async def custom_wishes_details(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    data = await state.get_data()
    data['custom']['wishes'] = message.text
    await state.update_data(data)
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.cust_price)
    await ask_custom_step(message, state, 'cust_price')

@router.message(BotStates.cust_price)
async def custom_price(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    try:
        price = float(message.text.replace("$", "").replace(",", "."))
    except Exception:
        msg = await message.answer("⚠️ Numbers only / Тільки цифри")
        await track(state, msg.message_id)
        return
    data = await state.get_data()
    data['custom']['price'] = price
    await state.update_data(data)
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.cust_paid_check)
    await ask_custom_step(message, state, 'cust_paid_check')

@router.message(BotStates.cust_paid_check)
async def custom_paid_check(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    is_yes = message.text in [TEXTS['ua']['btn_yes'], TEXTS['en']['btn_yes']]
    await clear_ui(message.chat.id, state)
    data = await state.get_data()
    if is_yes:
        await state.set_state(BotStates.cust_pay_method)
        await ask_custom_step(message, state, 'cust_pay_method')
    else:
        data['custom']['payment_info'] = "Ні / No"
        data['custom']['debt'] = data['custom']['price']
        await state.update_data(data)
        await state.set_state(BotStates.cust_ask_screen)
        await ask_custom_step(message, state, 'cust_ask_screen')

@router.message(BotStates.cust_pay_method)
async def custom_pay_method_selected(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    data = await state.get_data()
    data['custom']['pay_method'] = message.text
    await state.update_data(data)
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.cust_pay_amount)
    await ask_custom_step(message, state, 'cust_pay_amount')

@router.message(BotStates.cust_pay_amount)
async def custom_pay_amount(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    try:
        paid_val = float(message.text.replace("$", "").replace(",", "."))
    except Exception:
        msg = await message.answer("⚠️ Numbers only / Тільки цифри")
        await track(state, msg.message_id)
        return
    data = await state.get_data()
    price = data['custom']['price']
    method = data['custom']['pay_method']
    debt = max(0, price - paid_val)
    payment_info = f"{paid_val}$ ({method})"
    data['custom']['payment_info'] = payment_info
    data['custom']['debt'] = debt
    await state.update_data(data)
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.cust_ask_screen)
    await ask_custom_step(message, state, 'cust_ask_screen')

@router.message(BotStates.cust_wait_screen, F.photo)
async def custom_screen_received(message: types.Message, state: FSMContext):
    logging.info(f"Custom screen received from {message.from_user.id}")
    await track(state, message.message_id)
    file_id = message.photo[-1].file_id
    data = await state.get_data()
    data['custom']['photo'] = file_id
    await state.update_data(data)
    uid = message.from_user.id
    c = data['custom']
    txt = get_txt(uid, 'cust_review_header')
    txt += f"👤 Model: {c.get('model_name')}\n💰 Price: {c.get('price')}$\n📉 Debt: {c.get('debt')}$"
    await clear_ui(message.chat.id, state)
    await state.set_state(BotStates.cust_review)
    msg = await message.answer_photo(photo=c['photo'], caption=txt, reply_markup=kb_custom_final(uid))
    await track(state, msg.message_id)

@router.message(BotStates.cust_review, F.text.in_([TEXTS['ua']['btn_confirm'], TEXTS['en']['btn_confirm']]))
async def custom_confirm_send(message: types.Message, state: FSMContext):
    await track(state, message.message_id)
    uid = message.from_user.id
    data = await state.get_data()
    c = data['custom']
    model_name = c.get('model_name', '')
    model_data = c.get('model_data', {})

    if model_name in MODELS:
        target_group = MODELS[model_name]['group']
        target_topic = MODELS[model_name]['topic']
    else:
        target_group = model_data.get('group', REPORT_GROUP_ID)
        target_topic = model_data.get('topic', REPORT_TOPIC_ID)

    if not target_group:
        target_group = REPORT_GROUP_ID
        target_topic = REPORT_TOPIC_ID

    speech_block = c.get('speech', '')
    if speech_block != get_txt(uid, 'cust_speech_default') and speech_block != "Ні":
        speech_block = f"Так\n\"{c['speech']}\""

    debt_alert = get_txt(uid, 'debt_note_txt') if c.get('debt', 0) > 0 else ""
    approver_display = c.get('approver_name', '')
    if c.get('approver_id') and c['approver_id'] != 0:
        approver_display = f"<a href='tg://user?id={c['approver_id']}'>{c['approver_name']}</a>"

    sender_display = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>"

    caption = f"""📸📸📸<b>CUSTOM</b>🎦🎦🎦

📜📜📜 <b>DETAILS</b> 📜📜📜

<b>Відео</b>
⏱ <b>Тривалість:</b> {c.get('duration')}
🗣 <b>Потрібно щось говорити:</b> {speech_block}
🎵 <b>Музика:</b> {c.get('music')}
✨ <b>Побажання:</b> {c.get('wishes')}

💰 <b>Погоджена Ціна:</b> {c.get('price')}$
💳 <b>Оплата:</b> {c.get('payment_info')}
📉 <b>Борг:</b> {c.get('debt')}$ {debt_alert}

🎬 <b>Сценарій:</b>
{c.get('scenario')}

👤 <b>Відправив:</b> {sender_display}
👮‍♂️ <b>Погодив:</b> {approver_display}"""

    await clear_ui(message.chat.id, state)
    try:
        await bot.send_photo(
            chat_id=target_group,
            photo=c['photo'],
            caption=caption,
            message_thread_id=target_topic if target_topic else None
        )
        await message.answer(get_txt(uid, 'sent_success', model=model_name), reply_markup=kb_main(uid))
    except Exception as e:
        logging.error(f"Failed to send custom order: {e}")
        await message.answer(f"⚠️ Error sending: {e}")
    await state.clear()
    await state.set_state(BotStates.main_menu)

# ==================== ADMIN COMMANDS ====================

@router.message(Command("force_report"))
async def cmd_force_report(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied.")
        return
    now = datetime.now()
    month_year = now.strftime("%m-%Y")
    logging.info(f"/force_report triggered for month: {month_year}")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT user_id, telegram_name, SUM(profit) AS total_profit FROM shifts WHERE month_year = ? GROUP BY user_id ORDER BY total_profit DESC",
                (month_year,)
            )
            rows = await cursor.fetchall()
    except Exception as e:
        await message.answer(f"⚠️ DB error: {e}")
        return

    if not rows:
        await message.answer(f"📊 Немає даних за {month_year}.")
        return

    lines = [f"📊 <b>Підсумки за {month_year} (force):</b>\n"]
    for row in rows:
        uid  = row["user_id"]
        name = row["telegram_name"]
        tot  = row["total_profit"]
        lines.append(f"<a href='tg://user?id={uid}'>{name}</a> — {tot:.2f}$")
    report_text = "\n".join(lines)

    await message.answer(report_text)
    if REPORT_GROUP_ID:
        try:
            await bot.send_message(
                REPORT_GROUP_ID,
                report_text,
                message_thread_id=REPORT_TOPIC_ID if REPORT_TOPIC_ID else None,
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"force_report send fail: {e}")

@router.message(Command("test_api_calc"))
async def cmd_test_api_calc(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied.")
        return

    uid = message.from_user.id
    user_name = message.from_user.full_name
    mock_profit = 45.50

    try:
        await save_shift_to_db(uid, user_name, mock_profit)
        db_status = "✅ Записано в БД"
    except Exception as e:
        db_status = f"⚠️ Помилка БД: {e}"

    mock_details = ""
    accounts_to_check = list(accounts_cache.keys())
    if not accounts_to_check:
        accounts_to_check = ["Анкета 1 (Тест)", "Анкета 2 (Тест)"]

    for acc in accounts_to_check:
        mock_details += f"📱 {acc} — 💰 Профіт: +{mock_profit / max(len(accounts_to_check), 1):.2f}$ (mock)\n"
    mock_details += get_txt(uid, 'total', profit=mock_profit)

    user_display = f"{user_name} (ID: {uid})"
    time_range = "14:00 - 22:00"
    report_text = get_txt(uid, 'report_header', user=user_display, time_range=time_range, duration="8h 0m", details=mock_details)
    report_text += f"\n\n🧪 <b>ТЕСТ-МОД</b>\n{db_status}"

    await message.answer(report_text, reply_markup=kb_main(uid))
    logging.info(f"/test_api_calc: mock shift written for user {uid}, profit={mock_profit}")

# ==================== GLOBAL CATCH-ALL HANDLERS ====================

@router.callback_query()
async def catch_all_callbacks(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer(
        "⏳ Ця кнопка більше не активна. Оновіть меню через /start",
        show_alert=True
    )
    try:
        await callback.message.delete()
    except Exception:
        pass

@router.message(F.chat.type == "private")
async def catch_all_messages(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    logging.info(f"Unhandled message from {uid}: {message.text!r}")
    await message.answer(
        "🤷‍♂️ Я не розумію цю команду або повідомлення.\nНатисніть /start для оновлення меню."
    )

# ==================== MAIN ====================

async def main():
    await init_db()
    await load_accounts()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_monthly_report, trigger='cron', day=1, hour=0, minute=5, id='monthly_report')
    scheduler.start()
    logging.info("⏰ APScheduler started: monthly report on 1st at 00:05")

    await bot.delete_webhook(drop_pending_updates=True)
    dp.include_router(router)
    logging.info("🤖 Bot starting polling...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Polling crashed: {e}")
    finally:
        scheduler.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")