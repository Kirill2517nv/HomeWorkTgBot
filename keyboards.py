from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from typing import List, Tuple

def get_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Создает и возвращает главное меню (Reply-клавиатуру) в зависимости от статуса пользователя.
    """
    builder = ReplyKeyboardBuilder()

    # Кнопки, доступные всем пользователям
    builder.row(
        KeyboardButton(text="📚 Мои задания"),
        KeyboardButton(text="📝 Пройти тест")
    )
    builder.row(KeyboardButton(text="❌ Отмена"))

    # Кнопки, доступные только администратору
    if is_admin:
        builder.row(KeyboardButton(text="--- Админ-панель ---"))
        builder.row(
            KeyboardButton(text="➕ Новое задание"),
            KeyboardButton(text="📤 Отправить задание")
        )
        builder.row(
            KeyboardButton(text="➕ Новый тест"),
            KeyboardButton(text="📊 Результаты тестов")
        )
        builder.row(
            KeyboardButton(text="📥 Ответы на задания")
        )

    # Свойство resize_keyboard=True делает кнопки компактными
    return builder.as_markup(resize_keyboard=True)

def get_class_selection_keyboard(classes: List[int], prefix: str = "class_") -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора класса."""
    builder = InlineKeyboardBuilder()
    for cls in classes:
        builder.button(text=str(cls), callback_data=f"{prefix}{cls}")
    builder.adjust(2)
    return builder.as_markup()

def get_task_selection_keyboard(tasks: List[Tuple[int, str]], prefix: str = "task_") -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора задания."""
    builder = InlineKeyboardBuilder()
    for task_id, title in tasks:
        builder.button(text=title, callback_data=f"{prefix}{task_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_unsent_tasks_keyboard(tasks: List[Tuple[int, str]]) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора задания для отправки."""
    builder = InlineKeyboardBuilder()
    for task_id, title in tasks:
        builder.button(text=title, callback_data=f"send_task_{task_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_send_method_keyboard() -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора метода отправки задания."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Отправить сейчас", callback_data="send_now")
    builder.button(text="Запланировать", callback_data="send_schedule")
    builder.adjust(1)
    return builder.as_markup()