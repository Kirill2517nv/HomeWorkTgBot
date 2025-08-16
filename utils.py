from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import logger, ADMIN_ID
from pathlib import Path
from typing import Optional, List, Tuple
import os

async def download_file(bot: Bot, file_id: str, dest_dir: Path, file_name: str) -> str:
    """Скачивает файл из Telegram и возвращает путь к нему."""
    file = await bot.get_file(file_id)
    os.makedirs(dest_dir, exist_ok=True)
    file_path = dest_dir / file_name
    await bot.download_file(file.file_path, file_path)
    logger.info(f"Скачан файл: {file_path}")
    return str(file_path)

async def download_photo(bot: Bot, photo_id: str, dest_dir: Path, suffix: str = "") -> str:
    """Скачивает фото из Telegram с уникальным именем."""
    file_name = f"photo_{photo_id}{suffix}.jpg"
    return await download_file(bot, photo_id, dest_dir, file_name)

async def download_document(bot: Bot, document_id: str, document_name: str, dest_dir: Path, suffix: str = "") -> str:
    """Скачивает документ из Telegram с уникальным именем."""
    file_name = f"doc_{document_id}{suffix}_{document_name}"
    return await download_file(bot, document_id, dest_dir, file_name)

async def send_file_message(bot: Bot, chat_id: int, file_path: str, caption: Optional[str] = None) -> None:
    """Отправляет файл (фото или документ) с подписью."""
    try:
        if file_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            await bot.send_photo(chat_id=chat_id, photo=FSInputFile(file_path), caption=caption)
        else:
            await bot.send_document(chat_id=chat_id, document=FSInputFile(file_path), caption=caption)
        logger.info(f"Отправлен файл {file_path} в чат {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки файла {file_path} в чат {chat_id}: {e}")
        await bot.send_message(chat_id=chat_id, text=f"Ошибка загрузки файла: {e}")

async def send_message_with_buttons(bot: Bot, chat_id: int, text: str, buttons: List[Tuple[str, str]]) -> None:
    """Отправляет сообщение с инлайн-кнопками."""
    keyboard = InlineKeyboardBuilder()
    for button_text, callback_data in buttons:
        keyboard.button(text=button_text, callback_data=callback_data)
    keyboard.adjust(2)
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard.as_markup())
    logger.info(f"Отправлено сообщение с кнопками в чат {chat_id}")

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == ADMIN_ID

def format_answer_message(answer_text: Optional[str], answer_files: List[str]) -> str:
    """Форматирует сообщение с подтверждением ответа."""
    msg = "✅ Ваш ответ на задание записан:\n"
    if answer_text:
        msg += f"📝 Текст: {answer_text}\n"
    if answer_files:
        msg += f"📎 Файлов: {len(answer_files)}\n"
    return msg