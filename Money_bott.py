import asyncio
import sqlite3
import os
import gspread
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web

# =====================================================================
# НАСТРОЙКИ: Данные
# =====================================================================
TOKEN = "8628691428:AAEZ6Ec44uHwm5ey5xsIS6Ilj-9dNuDYOas"
SPREADSHEET_URL = "https://google.com"

ADMIN_ID = 5551943786  # Кирилл (Админ)
USER2_ID = 5178460435  # Максим
USER3_ID = 5959142753  # Лёня

ALLOWED_USERS = [ADMIN_ID, USER2_ID, USER3_ID]

USER_NAMES = {
    ADMIN_ID: "Кирилл",
    USER2_ID: "Максим",
    USER3_ID: "Лёня"
}

# Подключение к Google Таблице
try:
    gc = gspread.service_account(filename='creds.json')
    sh = gc.open_by_url(SPREADSHEET_URL)
    worksheet = sh.get_worksheet(0)
    print("Успешное подключение к Google Таблице!")
except Exception as e:
    print(f"Ошибка таблицы: {e}")
    worksheet = None

bot = Bot(token=TOKEN)
dp = Dispatcher()

# База данных для учета ручных расходов/вычетов
db = sqlite3.connect("wallet.db")
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL, comment TEXT)")
db.commit()

# =====================================================================
# КЛАВИАТУРЫ
# =====================================================================
def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton(text="💰 Мой баланс"), KeyboardButton(text="📦 Что в работе")],
        [KeyboardButton(text="📊 Общая статистика"), KeyboardButton(text="🧮 Калькулятор %")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="⚙️ Админ-Панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

admin_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔙 Главное меню")]
], resize_keyboard=True)

# =====================================================================
# ЛОГИКА АВТО-ПОДГРУЗКИ И ПАРСИНГА ТАБЛИЦЫ
# =====================================================================
def parse_table_data():
    if not worksheet:
        return 0.0, "⚠️ Таблица недоступна"
    
    records = worksheet.get_all_values()
    total_profit = 0.0
    report_text = "📱 *ТОВАР В РАБОТЕ:*\n\n"
    
    # Пропускаем шапку таблицы (первую строку)
    for row in records[1:]:
        if len(row) < 9 or not row[1]:  # Если строка пустая
            continue
            
        model = row[1]       # Столбец B: Модель
        price = row[2]       # Столбец C: Цена
        status = row[4]      # Столбец E: Состояние/Статус (выкуплен/продан)
        expected_p = row[7]  # Столбец H: Ожидаемая прибыль
        
        # Красиво форматируем вывод статуса
        emoji = "🟢" if "прода" in status.lower() or "выкуп" in status.lower() else "🟡"
        report_text += f"{emoji} *{model}* ({price} руб.) — _{status}_\n"
        
        # Плюсуем прибыль, если позиция успешна
        if "прода" in status.lower() or "выкуп" in status.lower():
            try:
                # Очищаем строку от лишних знаков и переводим в число
                clean_p = expected_p.replace("k", "000").replace("к", "000").replace(" ", "")
                total_profit += float(clean_p)
            except ValueError:
                pass
                
    return total_profit, report_text

# =====================================================================
# ХЕНДЛЕРЫ
# =====================================================================

@dp.message(Command("start"))
@dp.message(F.text == "🔙 Главное меню")
async def start_cmd(message: Message):
    if message.from_user.id not in ALLOWED_USERS: return
    await message.answer("Система активна. Данные синхронизированы с Google.", reply_markup=get_main_keyboard(message.from_user.id))

# Кнопка: Что в работе (выводит список девайсов)
@dp.message(F.text == "📦 Что в работе")
async def what_is_working(message: Message):
    if message.from_user.id not in ALLOWED_USERS: return
    _, report = parse_table_data()
    await message.answer(report, parse_mode="Markdown")

# Кнопка: Личный баланс (с учетом авто-прибыли и вычетов)
@dp.message(F.text == "💰 Мой баланс")
async def my_balance(message: Message):
    if message.from_user.id not in ALLOWED_USERS: return
    
    table_profit, _ = parse_table_data()
    # Считаем сумму всех ручных вычетов/расходов из базы
    total_expenses = cursor.execute("SELECT SUM(amount) FROM expenses").fetchone()[0] or 0.0
    
    # Чистый пул = прибыль из таблицы минус общие расходы
    net_pool = table_profit - total_expenses
    share = round(net_pool / 3, 2)  # Доля каждого участника
    
    await message.answer(f"👤 Твой личный баланс (1/3 доля пула): *{share:,} руб.*", parse_mode="Markdown")

# Кнопка: Общая статистика
@dp.message(F.text == "📊 Общая статистика")
@dp.message(Command("stat"))
async def global_status(message: Message):
    if message.from_user.id not in ALLOWED_USERS: return
    
    table_profit, _ = parse_table_data()
    total_expenses = cursor.execute("SELECT SUM(amount) FROM expenses").fetchone()[0] or 0.0
    net_pool = table_profit - total_expenses
    share = round(net_pool / 3, 2)
    
    # Берем процент из глобальной локальной настройки (по умолчанию 16%)
    bank_pct = 16.0 

    text = (
        f"🌍 *ОБЩАЯ СТАТИСТИКА ТЕМКЕ* 🌍\n\n"
        f"📈 *Вся прибыль из таблицы:* {table_profit:,} руб.\n"
        f"📉 *Общие расходы/вычеты:* {total_expenses:,} руб.\n"
        f"💰 *Чистый пул в обороте:* *{net_pool:,} руб.*\n\n"
        f"👥 *Разбивка долей (на 3 человек):*\n"
        f"• Кирилл: {share:,} руб.\n"
        f"• Максим: {share:,} руб.\n"
        f"• Лёня: {share:,} руб."
    )
    await message.answer(text, parse_mode="Markdown")

# Кнопка: Калькулятор процентов
@dp.message(F.text == "🧮 Калькулятор %")
@dp.message(Command("calculator"))
async def bank_calc(message: Message):
    if message.from_user.id not in ALLOWED_USERS: return
    
    table_profit, _ = parse_table_data()
    total_expenses = cursor.execute("SELECT SUM(amount) FROM expenses").fetchone()[0] or 0.0
    net_pool = table_profit - total_expenses
    
    bank_pct = 16.0  # Примерная ставка банка
    year_income = net_pool * (bank_pct / 100)
    month_income = year_income / 12
    day_income = year_income / 365

    text = (
        f"🧮 *Прогноз доходности вклада*\n"
        f"Расчет от чистого пула: *{net_pool:,} руб.* под *{bank_pct}%*\n\n"
        f"💰 В день: `+{round(day_income, 2):,} руб.`\n"
        f"📅 В месяц: `+{round(month_income, 2):,} руб.`\n"
        f"🗓 В год: `+{round(year_income, 2):,} руб.`"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("id"))
async def get_chat_and_user_id(message: Message):
    if message.from_user.id not in ALLOWED_USERS: return
    await message.answer(f"💬 ID чата: `{message.chat.id}`\n📌 ID топика: `{message.message_thread_id}`", parse_mode="Markdown")

# =====================================================================
# АДМИНКА И ФУНКЦИЯ ВЫЧЕТА (ДОЛЕВОЙ МИНУС)
# =====================================================================
@dp.message(F.text == "⚙️ Админ-Панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer(
        "⚙️ *Панель управления вычетами*\n\n"
        "Прибыль бот считает сам на основе таблицы.\n"
        "Если нужно записать общий расход или вычесть деньги, напиши в чат:\n"
        "`минус сумма коммент` (Пример: `минус 1500 проезд ремонт`)\n\n"
        "Чтобы сбросить все вычеты в ноль, напиши:\n"
        "`сброс вычетов`", 
        reply_markup=admin_kb, parse_mode="Markdown"
    )

# Обработчик команды вычета расходов "минус 1500 ремонт"
@dp.message(F.text.lower().startswith("минус "))
async def admin_minus_command(message: Message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split()
    try:
        amount = float(parts[1])
        comment = " ".join(parts[2:]) if len(parts) > 2 else "Расход по темке"
        
        cursor.execute("INSERT INTO expenses (amount, comment) VALUES (?, ?)", (amount, comment))
        db.commit()
        await message.answer(f"📉 Вычет зафиксирован: *-{amount} руб.* ({comment}). Сумма вычтена из долей каждого участника.", parse_mode="Markdown")
    except Exception:
        await message.answer("❌ Ошибка формата. Пример: `минус 500 бензин`")

# Команда полного обнуления расходов
@dp.message(F.text.lower() == "сброс вычетов")
async def clear_expenses(message: Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("DELETE FROM expenses")
    db.commit()
    await message.answer("✅ Все ручные расходы и вычеты успешно сброшены в 0. Балансы пересчитаны.")

# =====================================================================
# ВЕБ-СЕРВЕР И АВТО-ПИНГ («Будильник» для Render)
# =====================================================================
async def handle_web_request(request): 
    return web.Response(text="Бот онлайн!")

# Функция, которая каждые 10 минут стучится на твой сайт, чтобы Render не спал
async def auto_ping_loop():
    await asyncio.sleep(30) # Даем боту сначала спокойно запуститься
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Бот сам заходит на твой URL на Render
                async with session.get("https://onrender.com") as response:
                    print(f"⏰ Будильник сработал! Статус ответа сервера: {response.status}")
            except Exception as e:
                print(f"⚠️ Ошибка будильника: {e}")
            await asyncio.sleep(600) # Ждем 10 минут перед следующим пингом

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web_request)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    print(f"Фоновый веб-сервер успешно запущен на порту {port}!")

# =====================================================================
# ЗАПУСК
# =====================================================================
async def main():
    import aiohttp # Добавим импорт для авто-пинга
    await start_web_server()
    # Запускаем бесконечный фоновый цикл само-пингования
    asyncio.create_task(auto_ping_loop())
    print("Бот успешно запущен на сервере и защищен от засыпания!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
