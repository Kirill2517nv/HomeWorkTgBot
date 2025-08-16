import asyncio
from aiogram import Bot
from main_web import WEBHOOK_URL, BOT_TOKEN, logger

async def set_webhook():
    """Устанавливает вебхук для бота."""
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Вебхук успешно установлен на: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Ошибка при установке вебхука: {e}")
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(set_webhook())