# main.py (финальная версия для PythonAnywhere)

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp.web import Application, run_app

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from handlers.common import router as common_router
from handlers.tasks import router as tasks_router
from handlers.tests import router as tests_router
from db import Database
from config import BOT_TOKEN, DB_NAME, logger

# --- НАСТРОЙКИ WEBHOOK ---
WEB_SERVER_HOST = "kirill2517nv.pythonanywhere.com"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"https://{WEB_SERVER_HOST}{WEBHOOK_PATH}"

# Настройки для локального запуска
WEBAPP_HOST = "localhost"  # или 0.0.0.0
WEBAPP_PORT = 8000


async def on_startup(bot: Bot, scheduler: AsyncIOScheduler):
    """Выполняется при старте бота."""
    logger.info("Установка вебхука...")
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Вебхук успешно установлен.")
    if not scheduler.running:
        scheduler.start()
        logger.info("Планировщик запущен.")


async def on_shutdown(bot: Bot, scheduler: AsyncIOScheduler):
    """Выполняется при остановке бота."""
    logger.info("Удаление вебхука...")
    await bot.delete_webhook()
    logger.info("Вебхук удален.")
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Планировщик остановлен.")


def create_app() -> Application:
    """
    Создает и настраивает экземпляр aiohttp приложения.
    Эта функция будет вызываться WSGI-сервером.
    """
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    db = Database()

    jobstores = {
        'default': SQLAlchemyJobStore(url=f'sqlite:///{DB_NAME}')
    }
    scheduler = AsyncIOScheduler(jobstores=jobstores)

    dp.include_router(common_router)
    dp.include_router(tasks_router)
    dp.include_router(tests_router)

    dp["db"] = db
    dp["scheduler"] = scheduler

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot, scheduler=scheduler)

    return app


if __name__ == "__main__":
    # Этот блок выполняется, только если запустить файл напрямую (для локального теста)
    app = create_app()
    logger.info(f"Запуск локального веб-сервера на {WEBAPP_HOST}:{WEBAPP_PORT}")
    run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)