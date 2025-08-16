import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from handlers.common import router as common_router
from handlers.tasks import router as tasks_router
from handlers.tests import router as tests_router
from db import Database
from config import BOT_TOKEN, logger, DB_NAME



async def main() -> None:
    """Основная функция для запуска бота."""
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Инициализация базы данных
    db = Database()

    # Инициализация планировщика
    jobstores = {
        'default': SQLAlchemyJobStore(url=f'sqlite:///{DB_NAME}')
    }
    scheduler = AsyncIOScheduler(jobstores=jobstores)
    scheduler.start()

    # Подключение роутеров
    dp.include_router(common_router)
    dp.include_router(tasks_router)
    dp.include_router(tests_router)

    # Middleware для передачи Database и Scheduler в хендлеры
    async def on_startup(dispatcher: Dispatcher) -> None:
        """Выполняется при старте бота."""
        logger.info("Бот запущен")

    async def on_shutdown(dispatcher: Dispatcher) -> None:
        """Выполняется при остановке бота."""
        scheduler.shutdown()
        await bot.session.close()
        await dp.storage.close()
        logger.info("Бот остановлен")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запуск бота
    try:
        await dp.start_polling(bot, db=db, scheduler=scheduler)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await on_shutdown(dp)


if __name__ == "__main__":
    asyncio.run(main())