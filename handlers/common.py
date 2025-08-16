from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from states import RegisterStates, ListStudentsStates
from db import Database
from utils import is_admin, send_message_with_buttons
from config import logger
from keyboards import get_main_menu

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, db: Database) -> None:
    """Обработчик команды /start. Приветствует пользователя и показывает главное меню."""
    user_id = message.from_user.id
    student = db.get_student(user_id)

    if not student:
        await message.answer("Добро пожаловать! Для начала нужно зарегистрироваться.\nВведите ваше имя:")
        await state.set_state(RegisterStates.first_name)
        return

    await message.answer("Добро пожаловать обратно!")
    admin_status = is_admin(user_id)
    await message.answer("Выберите действие:", reply_markup=get_main_menu(admin_status))


@router.message(RegisterStates.first_name)
async def process_first_name(message: Message, state: FSMContext) -> None:
    await state.update_data(first_name=message.text)
    await message.answer("Введите вашу фамилию:")
    await state.set_state(RegisterStates.last_name)


@router.message(RegisterStates.last_name)
async def process_last_name(message: Message, state: FSMContext) -> None:
    await state.update_data(last_name=message.text)
    await message.answer("Введите номер класса:")
    await state.set_state(RegisterStates.class_number)


@router.message(RegisterStates.class_number)
async def process_class_number(message: Message, state: FSMContext, db: Database) -> None:
    try:
        class_number = int(message.text)
        if class_number <= 0:
            raise ValueError("Номер класса должен быть положительным числом.")

        data = await state.get_data()
        db.insert_student(
            first_name=data["first_name"],
            last_name=data["last_name"],
            class_number=class_number,
            telegram_id=message.from_user.id
        )

        await message.answer("Регистрация успешно завершена!")
        admin_status = is_admin(message.from_user.id)
        await message.answer("Выберите действие:", reply_markup=get_main_menu(admin_status))
        await state.clear()
    except ValueError as e:
        await message.answer(f"Ошибка: {e}. Попробуйте снова.")
        logger.error(f"Ошибка регистрации (class_number): {e}, user_id: {message.from_user.id}")


@router.message(F.text == "📋 Список учеников")
async def list_students_from_button(message: Message, state: FSMContext, db: Database, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("Эта функция доступна только учителю.")
        return

    classes = db.get_unique_classes()
    if not classes:
        await message.answer("Нет зарегистрированных классов.")
        return

    buttons = [(str(cls), f"list_class_{cls}") for cls in classes]
    await send_message_with_buttons(bot, message.from_user.id, "Выберите класс:", buttons)
    await state.set_state(ListStudentsStates.class_number)


@router.callback_query(ListStudentsStates.class_number, F.data.startswith("list_class_"))
async def process_class_selection_for_list(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    class_number = int(callback.data.split("_")[2])
    students = db.get_student_names_by_class(class_number)

    if not students:
        await callback.message.answer(f"В классе {class_number} нет студентов.")
        await state.clear()
        await callback.answer()
        return

    response = "\n".join([f"{i + 1}. {s[0]} {s[1]}" for i, s in enumerate(students)])
    await callback.message.answer(response)
    await state.clear()
    await callback.answer()

@router.message(F.text == "❌ Отмена")
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Обработчик отмены любого действия и возврата в главное меню."""
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await message.answer(
            "Действие отменено.",
            reply_markup=get_main_menu(is_admin(message.from_user.id))
        )
    else:
        await message.answer(
            "Нет активных действий для отмены.",
            reply_markup=get_main_menu(is_admin(message.from_user.id))
        )