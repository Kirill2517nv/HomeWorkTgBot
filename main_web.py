import asyncio
from flask import Flask, request, abort
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from handlers.common import router as common_router
from handlers.tasks import router as tasks_router
from handlers.tests import router as tests_router
from db import Database
from config import BOT_TOKEN, DB_NAME, logger

# --- НАСТРОЙКИ ---
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
# Это доменное имя используется только для установки вебхука, не для запуска сервера
WEB_SERVER_HOST = "kirill2517nv.pythonanywhere.com"
WEBHOOK_URL = f"https://{WEB_SERVER_HOST}{WEBHOOK_PATH}"

# --- ИНИЦИАЛИЗАЦИЯ AIOGRAM ---
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

# Настраиваем планировщик
jobstores = {
    'default': SQLAlchemyJobStore(url=f'sqlite:///{DB_NAME}')
}
scheduler = BackgroundScheduler(jobstores=jobstores)

# Подключаем роутеры и передаем зависимости
dp.include_router(common_router)
dp.include_router(tasks_router)
dp.include_router(tests_router)
dp["db"] = db
dp["scheduler"] = scheduler

# --- ИНИЦИАЛИЗАЦИЯ FLASK ---
app = Flask(__name__)


@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    """
    Этот метод принимает обновления от Telegram и передает их в aiogram.
    """
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.model_validate_json(json_string)
        # Запускаем обработку обновления в асинхронном контексте
        asyncio.run(dp.feed_update(bot=bot, update=update))
        return '', 200
    else:
        abort(403)


# Функции для запуска/остановки планировщика
@app.before_request
def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("Планировщик запущен.")


@app.teardown_request
def shutdown_scheduler(exception=None):
    # Этот обработчик нам не нужен, т.к. планировщик должен работать всегда
    pass

if not scheduler.running:
    scheduler.start()
    logger.info("Планировщик запущен в фоновом режиме.")

# --- ДЛЯ ЛОКАЛЬНОГО ТЕСТА ---
# Этот блок больше не нужен для продакшена, но может быть полезен для отладки
if __name__ == '__main__':
    # Внимание! Этот способ запуска не подходит для PythonAnywhere,
    # он нужен только для локальной отладки.
    # Для установки вебхука используйте set_webhook.py
    logger.info("Запуск бота в режиме polling для локальной отладки...")


    async def run_polling():
        if not scheduler.running:
            scheduler.start()
        await dp.start_polling(bot, db=db, scheduler=scheduler)


    asyncio.run(run_polling())