# main.py (версия для Webhooks)

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from handlers.common import router as common_router
from handlers.tasks import router as tasks_router
from handlers.tests import router as tests_router
from db import Database
from config import BOT_TOKEN, DB_NAME, logger

# --- НАСТРОЙКИ WEBHOOK ---
# Установите FQDN (полное доменное имя) вашего веб-приложения на PythonAnywhere
# Например: kirill2517nv.pythonanywhere.com
WEB_SERVER_HOST = "kirill2517nv.pythonanywhere.com"
# Путь, по которому Telegram будет отправлять обновления. Должен быть секретным.
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
# Полный URL для вебхука
WEBHOOK_URL = f"https://{WEB_SERVER_HOST}{WEBHOOK_PATH}"

# Настройки для веб-сервера, который будет запускаться внутри PythonAnywhere
# Эти адреса стандартны для веб-приложений на PythonAnywhere
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8000  # Вы можете выбрать другой порт, если это необходимо


async def on_startup(bot: Bot, db: Database, scheduler: AsyncIOScheduler):
    """Выполняется при старте бота."""
    logger.info("Установка вебхука...")
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Вебхук успешно установлен.")

    # Запускаем планировщик только если он еще не запущен
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


def main():
    """Основная функция для запуска бота в режиме вебхука."""
    # Инициализация
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    db = Database()

    jobstores = {
        'default': SQLAlchemyJobStore(url=f'sqlite:///{DB_NAME}')
    }
    scheduler = AsyncIOScheduler(jobstores=jobstores)

    # Подключение роутеров
    dp.include_router(common_router)
    dp.include_router(tasks_router)
    dp.include_router(tests_router)

    # Передаем объекты в хендлеры
    dp["db"] = db
    dp["scheduler"] = scheduler

    # Регистрируем функции запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Создаем приложение веб-сервера
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot, db=db, scheduler=scheduler)

    # Запускаем веб-сервер
    logger.info(f"Запуск веб-сервера на {WEBAPP_HOST}:{WEBAPP_PORT}")
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        logger.info("Бот остановлен")