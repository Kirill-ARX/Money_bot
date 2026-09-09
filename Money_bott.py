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
