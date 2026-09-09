import asyncio
import sqlite3
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web

# =====================================================================
# НАСТРОЙКИ: Твои актуальные данные
# =====================================================================
TOKEN = "8628691428:AAEZ6Ec44uHwm5ey5xsIS6Ilj-9dNuDYOas"  # Токен твоего бота

ADMIN_ID = 5551943786  # Твой Telegram ID (Кирилл - админ и юзер)
USER2_ID = 5178460435  # Telegram ID второго партнера (Максим)
USER3_ID = 5959142753  # Telegram ID третьего партнера (Лёня)

# Список разрешенных пользователей (белый список на 3 человек)
ALLOWED_USERS = [ADMIN_ID, USER2_ID, USER3_ID]

# Словарь для красивого отображения имен в отчетах
USER_NAMES = {
    ADMIN_ID: "Кирилл",
    USER2_ID: "Максим",
    USER3_ID: "Лёня"
}

# =====================================================================
# ИНИЦИАЛИЗАЦИЯ И БАЗА ДАННЫХ
# =====================================================================
bot = Bot(token=TOKEN)
dp = Dispatcher()

db = sqlite3.connect("wallet.db")
cursor = db.cursor()

# Создаем таблицы, если их еще нет
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0.0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS global_stats (
    id INTEGER PRIMARY KEY,
    profit REAL DEFAULT 0.0,
    ozon_percent REAL DEFAULT 15.0
)
""")
db.commit()

# Заполняем базу начальными данными, если она пустая
for uid in ALLOWED_USERS:
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
cursor.execute("INSERT OR IGNORE INTO global_stats (id) VALUES (1)")
db.commit()


# =====================================================================
# КЛАВИАТУРЫ (КНОПКИ)
# =====================================================================
# Главное меню для всех трех участников
def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton(text="💰 Мой баланс"), KeyboardButton(text="📊 Общая статистика")],
        [KeyboardButton(text="🧮 Калькулятор процентов")]
    ]
    # Если кнопку нажимает админ (Кирилл) — добавляем ему кнопку админки
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="⚙️ Admin-Панель")])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# Кнопки админки (управление балансом и процентами)
admin_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="➕ Изменить баланс Максим"), KeyboardButton(text="➕ Изменить баланс Лёня")],
    [KeyboardButton(text="➕ Изменить мой баланс"), KeyboardButton(text="📈 Поменять % вклада")],
    [KeyboardButton(text="🔙 Главное меню")]
], resize_keyboard=True)


# =====================================================================
# ЛОГИКА БОТА (ХЕНДЛЕРЫ)
# =====================================================================

# Проверка: если пишет левый челик — бот его игнорирует
@dp.message(lambda msg: msg.from_user.id not in ALLOWED_USERS)
async def auth_kick(message: Message):
    if message.chat.type == "private":
        await message.answer("❌ Доступ закрыт. Вы не входите в список участников.")


# Команда /start и кнопка Назад
@dp.message(Command("start"))
@dp.message(F.text == "🔙 Главное меню")
async def start_cmd(message: Message):
    if message.from_user.id not in ALLOWED_USERS: return
    await message.answer(
        f"Привет, {message.from_user.first_name}! Что хочешь посмотреть?",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

# Кнопка: Личный баланс
@dp.message(F.text == "💰 Мой баланс")
async def my_balance(message: Message):
    if message.from_user.id not in ALLOWED_USERS: return
    uid = message.from_user.id
    res = cursor.execute("SELECT balance FROM users WHERE user_id = ?", (uid,)).fetchone()
    balance = res[0] if res else 0.0
    await message.answer(f"👤 Твой личный баланс: *{balance:,} руб.*", parse_mode="Markdown")


# Кнопка и команда: Общая статистика
@dp.message(F.text == "📊 Общая статистика")
@dp.message(Command("stat"))
async def global_status(message: Message):
    if message.from_user.id not in ALLOWED_USERS: return
    
    # Считаем сумму всех личных балансов
    total_balances = cursor.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0.0
    # Берем чистую прибыль и процент из глобальной таблицы
    profit, ozon_pct = cursor.execute("SELECT profit, ozon_percent FROM global_stats WHERE id = 1").fetchone()

    # Собираем инфу по каждому игроку для наглядности
    users_info = ""
    all_users = cursor.execute("SELECT user_id, balance FROM users").fetchall()
    for row in all_users:
        users_info += f"• {USER_NAMES.get(row[0], 'Unknown')}: {row[1]:,} руб.\n"

    text = (
        f"🌍 *ОБЩАЯ СТАТИСТИКА* 🌍\n\n"
        f"💰 *Всего денег в обороте:* {total_balances:,} руб.\n"
        f"📈 *Чистая прибыль:* {profit:,} руб.\n"
        f"🏦 *Процент вклада в банке:* {ozon_pct}%\n\n"
        f"👥 *Разбивка по участникам:*\n{users_info}"
    )
    await message.answer(text, parse_mode="Markdown")


# Кнопка и команда: Калькулятор процентов (ИСПРАВЛЕНО НАЗВАНИЕ)
@dp.message(F.text == "🧮 Калькулятор процентов")
@dp.message(Command("calculator"))
async def ozon_calc(message: Message):
    if message.from_user.id not in ALLOWED_USERS: return
    
    # Считаем общую сумму денег
    total_balances = cursor.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0.0
    _, ozon_pct = cursor.execute("SELECT profit, ozon_percent FROM global_stats WHERE id = 1").fetchone()

    # Считаем доход
    year_income = total_balances * (ozon_pct / 100)
    month_income = year_income / 12
    day_income = year_income / 365

    text = (
        f"🧮 *Прогноз доходности вклада Ozon*\n"
        f"Расчет от общей суммы: *{total_balances:,} руб.* под *{ozon_pct}%*\n\n"
        f"💰 В день: `+{round(day_income, 2):,} руб.`\n"
        f"📅 В месяц: `+{round(month_income, 2):,} руб.`\n"
        f"🗓 В год: `+{round(year_income, 2):,} руб.`"
    )
    await message.answer(text, parse_mode="Markdown")


# Команда: /id
@dp.message(Command("id"))
async def get_chat_and_user_id(message: Message):
    if message.from_user.id not in ALLOWED_USERS: return
    thread_id = message.message_thread_id
    text = (
        f"🆔 *Твой личный Telegram ID:* `{message.from_user.id}`\n"
        f"💬 *ID этой группы:* `{message.chat.id}`\n"
        f"📌 *ID текущей темы (топика):* `{thread_id if thread_id else 'Основной чат'}`"
    )
    await message.answer(text, parse_mode="Markdown")


# =====================================================================
# АДМИНКА (ИСПРАВЛЕНО НАЗВАНИЕ НА КНОПКЕ "⚙️ Admin-Панель")
# =====================================================================
@dp.message(F.text == "⚙️ Admin-Панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Добро пожаловать в панель управления, Мяу!", reply_markup=admin_kb)


# Инструкции по изменению данных
@dp.message(F.text.startswith("➕ Изменить"))
async def info_how_to_change(message: Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer(
        "ℹ️ Чтобы изменить баланс или прибыль, просто отправь боту сообщение в формате:\n\n"
        "`сет баланс 2 50000` (установит баланс Максиму равным 50к)\n"
        "`сет баланс 3 0` (жестко сбросит баланс Лёне в 0)\n"
        "`сет админ 10000` (установит тебе баланс 10к)\n"
        "`сет прибыль 15000` (установит общую чистую прибыль)\n",
        parse_mode="Markdown"
    )


@dp.message(F.text == "📈 Поменять % вклада")
async def info_how_to_pct(message: Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("ℹ️ Чтобы поменять % ставку Озона, напиши:\n`сет процент 16.5`", parse_mode="Markdown")


# ИСПРАВЛЕННЫЙ ТЕКСТОВЫЙ ОБРАБОТЧИК: Настройка "сет ..." без багов
@dp.message(F.text.lower().startswith("сет "))
async def admin_commands(message: Message):
    if message.from_user.id != ADMIN_ID: return

    parts = message.text.split()
    try:
        # Берем второе слово из команды и переводим его в нижний регистр
        cmd_type = parts[1].lower()

        if cmd_type == "баланс":
            target_user = USER2_ID if parts[2] == "2" else USER3_ID
            amount = float(parts[3])
            # '=' вместо '+' — теперь баланс ЖЕСТКО ПЕРЕЗАПИСЫВАЕТСЯ (фикс нуля)
            cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, target_user))
            await message.answer(f"✅ Баланс участника {USER_NAMES.get(target_user)} изменен на {amount} руб.")

        elif cmd_type == "админ":
            amount = float(parts[2])
            cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, ADMIN_ID))
            await message.answer(f"✅ Твой баланс изменен на {amount} руб.")

        elif cmd_type == "прибыль":
            amount = float(parts[2])
            cursor.execute("UPDATE global_stats SET profit = ? WHERE id = 1", (amount,))
            await message.answer(f"✅ Чистая прибыль установлена: {amount} руб.")

        elif cmd_type == "процент":
            pct = float(parts[2])
            cursor.execute("UPDATE global_stats SET ozon_percent = ? WHERE id = 1", (pct,))
            await message.answer(f"✅ Процентная ставка Ozon обновлена: {pct}%")

        db.commit()
    except Exception:
        await message.answer("❌ Ошибка в формате команды. Пример: `сет баланс 2 0`")


# =====================================================================
# ВЕБ-СЕРВЕР («Будильник» для Render)
# =====================================================================
async def handle_web_request(request):
    return web.Response(text="Бот онлайн!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web_request)
    runner = web.AppRunner(app)
    await runner.setup()
