from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import NewTaskStates, SendTaskStates, AnswerStates, ShowAnswersStates
from db import Database
from utils import is_admin, send_file_message, send_message_with_buttons, download_document, download_photo, \
    format_answer_message
from config import logger, HOMEWORKS_DIR, BOT_TOKEN, DB_NAME
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from keyboards import get_task_selection_keyboard, get_class_selection_keyboard, get_unsent_tasks_keyboard, get_send_method_keyboard
from typing import List
import os
import shutil

router = Router()


async def scheduled_task_job(task_id: int, class_number: int) -> None:
    """
    Эта функция вызывается планировщиком. Она сама создает необходимые
    объекты Bot и Database для выполнения задачи.
    """
    logger.info(f"Запускается запланированная задача: отправка задания {task_id} классу {class_number}")
    bot = Bot(token=BOT_TOKEN)
    db = Database(db_path=DB_NAME)

    try:
        task = db.get_task(task_id)
        if not task:
            logger.error(f"Запланированная задача не нашла задание {task_id}")
            return

        _, title, description, file_path = task
        students = db.get_students_by_class(class_number)

        for student in students:
            try:
                msg = f"Новое задание: {title}\nОписание: {description}"
                if file_path:
                    await send_file_message(bot, student[0], file_path, caption=msg)
                else:
                    await bot.send_message(student[0], msg)
            except Exception as e:
                logger.error(f"Ошибка отправки запланированного задания {task_id} студенту {student[0]}: {e}")

        db.assign_task_to_class(task_id, class_number)
        logger.info(f"Запланированное задание {task_id} успешно отправлено классу {class_number}")
    finally:
        # Важно закрыть сессию, созданную для этой задачи
        await bot.session.close()

async def send_scheduled_task(bot: Bot, task_id: int, class_number: int, db: Database) -> None:
    """Отправляет задание всем студентам указанного класса."""
    task = db.get_task(task_id)
    if not task:
        logger.error(f"Задание {task_id} не найдено для отправки по расписанию")
        return

    id, title, description, file_path = task
    students = db.get_students_by_class(class_number)

    for student in students:
        try:
            msg = f"Новое задание: {title}\nОписание: {description}"
            if file_path:
                await send_file_message(bot, student[0], file_path, msg)
            else:
                await bot.send_message(chat_id=student[0], text=msg)
        except Exception as e:
            logger.error(f"Ошибка отправки задания {task_id} студенту {student[0]}: {e}")

    db.assign_task_to_class(task_id, class_number)
    logger.info(f"Задание {task_id} успешно отправлено классу {class_number}")


@router.message(F.text == "➕ Новое задание")
async def new_task(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Введите заголовок нового задания:")
    await state.set_state(NewTaskStates.title)

@router.message(NewTaskStates.title)
async def process_task_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введите описание задания:")
    await state.set_state(NewTaskStates.description)

@router.message(NewTaskStates.description)
async def process_task_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Прикрепите файл к заданию или напишите 'нет'.")
    await state.set_state(NewTaskStates.file)


@router.message(NewTaskStates.file)
async def process_task_file(message: Message, state: FSMContext, bot: Bot, db: Database):
    file_path = None
    if message.document:
        file_path = await download_document(
            bot, message.document.file_id, message.document.file_name, HOMEWORKS_DIR
        )
    elif message.text and message.text.lower() != 'нет':
        await message.answer("Пожалуйста, прикрепите файл или напишите 'нет'.")
        return

    data = await state.get_data()
    task_id = db.insert_task(
        title=data['title'],
        description=data['description'],
        file_path=file_path
    )
    await message.answer(f"Задание '{data['title']}' успешно создано с ID {task_id}.")
    await state.clear()


@router.message(F.text == "📤 Отправить задание")
async def send_task_start(message: Message, state: FSMContext, db: Database):
    if not is_admin(message.from_user.id):
        return

    tasks = db.get_tasks_not_sent_to_all()
    if not tasks:
        await message.answer("Все созданные задания уже отправлены всем классам, или заданий нет.")
        return

    await message.answer(
        "Выберите задание для отправки:",
        reply_markup=get_unsent_tasks_keyboard(tasks)
    )
    await state.set_state(SendTaskStates.task_id)


@router.callback_query(SendTaskStates.task_id, F.data.startswith("send_task_"))
async def process_send_task_selection(callback: CallbackQuery, state: FSMContext, db: Database):
    task_id = int(callback.data.split("_")[2])
    await state.update_data(task_id=task_id)

    classes = db.get_classes_for_task(task_id)
    if not classes:
        await callback.message.edit_text("Это задание уже отправлено всем существующим классам.")
        await state.clear()
        return

    await callback.message.edit_text(
        "Выберите класс, которому нужно отправить это задание:",
        reply_markup=get_class_selection_keyboard(classes, prefix="send_to_class_")
    )
    await state.set_state(SendTaskStates.class_number)
    await callback.answer()

@router.callback_query(SendTaskStates.task_id, F.data.startswith("task_"))
async def process_task_selection_for_send(callback: CallbackQuery, state: FSMContext) -> None:
    task_id = int(callback.data.split("_")[1])
    await state.update_data(task_id=task_id)
    buttons = [
        ("Немедленно", "immediate"),
        ("По расписанию", "schedule")
    ]
    await send_message_with_buttons(callback.bot, callback.from_user.id, "Выберите способ отправки:", buttons)
    await state.set_state(SendTaskStates.method)
    await callback.answer()


@router.callback_query(SendTaskStates.class_number, F.data.startswith("send_to_class_"))
async def process_send_class_selection(callback: CallbackQuery, state: FSMContext):
    class_number = int(callback.data.split("_")[3])
    await state.update_data(class_number=class_number)

    await callback.message.edit_text(
        "Как вы хотите отправить задание?",
        reply_markup=get_send_method_keyboard()
    )
    await state.set_state(SendTaskStates.method)
    await callback.answer()


@router.callback_query(SendTaskStates.method)
async def process_send_method(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database,
                              scheduler: AsyncIOScheduler):
    data = await state.get_data()
    task_id = data['task_id']
    class_number = data['class_number']

    if callback.data == "send_now":
        await send_scheduled_task(bot, task_id, class_number, db)
        await callback.message.edit_text(f"Задание немедленно отправлено ученикам {class_number} класса.")
        await state.clear()
    elif callback.data == "send_schedule":
        await callback.message.edit_text("Введите дату и время отправки в формате 'ДД.ММ.ГГГГ ЧЧ:ММ'")
        await state.set_state(SendTaskStates.schedule_time)

    await callback.answer()


@router.message(SendTaskStates.schedule_time)
async def process_schedule_time(message: Message, state: FSMContext, scheduler: AsyncIOScheduler, bot: Bot,
                                db: Database):
    try:
        schedule_time = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        if schedule_time < datetime.now():
            await message.answer("Нельзя запланировать отправку на прошедшее время. Попробуйте снова.")
            return

        data = await state.get_data()
        task_id = data['task_id']
        class_number = data['class_number']

        scheduler.add_job(
            scheduled_task_job,
            "date",
            run_date=schedule_time,
            args=[task_id, class_number]  # <--- Только простые типы!
        )

        await message.answer(f"Задание запланировано на {schedule_time.strftime('%d.%m.%Y %H:%M')}.")
        await state.clear()

    except ValueError:
        await message.answer("Неверный формат даты. Пожалуйста, введите дату в формате 'ДД.ММ.ГГГГ ЧЧ:ММ'.")

@router.message(F.text == "📚 Мои задания")
async def my_tasks(message: Message, state: FSMContext, db: Database):
    tasks = db.get_tasks_for_student_class(message.from_user.id)
    if not tasks:
        await message.answer("Для вашего класса нет назначенных заданий.")
        return

    await message.answer(
        "Выберите задание, на которое хотите ответить:",
        # Используем универсальную клавиатуру с префиксом для ответа
        reply_markup=get_task_selection_keyboard(tasks, prefix="answer_task_")
    )
    await state.set_state(AnswerStates.task_id)


@router.callback_query(AnswerStates.task_id, F.data.startswith("answer_task_"))
async def process_task_selection_for_answer(callback: CallbackQuery, state: FSMContext) -> None:
    task_id = int(callback.data.split("_")[2])
    await state.update_data(current_task_id=task_id, answer_text="", answer_files=[])

    await callback.message.answer(
        "Отправьте ваш ответ на задание. Вы можете присылать:\n"
        "1. Текстовое сообщение\n"
        "2. Файлы (документы или фото)\n"
        "3. И то и другое\n\n"
        "После отправки всех материалов напишите 'все'"
    )
    await state.set_state(AnswerStates.waiting_for_more_files)
    await callback.answer()


@router.message(AnswerStates.waiting_for_more_files, F.text)
async def handle_answer_text(message: Message, state: FSMContext, db: Database) -> None:
    if message.text.lower() == "все":
        await confirm_answer(message, state, db)
        return

    await state.update_data(answer_text=message.text)
    await message.answer(
        "Текст ответа сохранён. Можете прикрепить файлы или написать 'все', если файлов нет."
    )


@router.message(AnswerStates.waiting_for_more_files, F.document | F.photo)
async def handle_answer_files(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    files: List[str] = data.get("answer_files", [])
    user_id = message.from_user.id
    task_id = data["current_task_id"]

    if message.document:
        file_path = await download_document(bot, message.document.file_id, message.document.file_name, HOMEWORKS_DIR,
                                            f"_answer_{user_id}_{task_id}_{len(files)}")
    elif message.photo:
        file_path = await download_photo(bot, message.photo[-1].file_id, HOMEWORKS_DIR,
                                         f"_answer_{user_id}_{task_id}_{len(files)}")

    files.append(file_path)
    await state.update_data(answer_files=files)

    await message.answer(
        f"Файл сохранён. Всего файлов: {len(files)}\n"
        "Пришлите ещё файлы или напишите 'все', если это всё."
    )


async def confirm_answer(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    user_id = message.from_user.id
    task_id = data["current_task_id"]
    answer_text = data.get("answer_text")
    answer_files = data.get("answer_files", [])

    if not answer_text and not answer_files:
        await message.answer("Ответ не может быть пустым. Пожалуйста, отправьте текст или файл.")
        return

    student = db.get_student(user_id)
    if not student:
        await message.answer("Вы не зарегистрированы.")
        await state.clear()
        return

    student_id = student[0]
    if db.get_answers_by_task_and_student(student_id, task_id):
        await message.answer("Вы уже отправили ответ на это задание.")
        await state.clear()
        return

    db.insert_answer(
        student_id=student_id,
        task_id=task_id,
        answer_text=answer_text,
        answer_file_path=";".join(answer_files) if answer_files else None
    )

    await message.answer(format_answer_message(answer_text, answer_files))
    await state.clear()


@router.message(F.text == "📥 Скачать ответы учеников")
async def show_answers_from_button(message: Message, state: FSMContext, db: Database):
    if not is_admin(message.from_user.id):
        return
    tasks = db.get_all_tasks()
    if not tasks:
        await message.answer("Еще не создано ни одного задания.")
        return

    await message.answer(
        "Выберите задание, чтобы посмотреть ответы:",
        reply_markup=get_task_selection_keyboard(tasks, prefix="show_answers_")
    )
    await state.set_state(ShowAnswersStates.task_id)


@router.callback_query(ShowAnswersStates.task_id, F.data.startswith("show_answers_"))
async def process_task_selection_for_answers(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    task_id = int(callback.data.split("_")[2])
    answers = db.get_answers_by_task(task_id)
    if not answers:
        await callback.message.answer("Нет ответов на это задание.")
        await state.clear()
        await callback.answer()
        return

    task = db.get_task(task_id)
    task_title = task[1]
    output_dir = HOMEWORKS_DIR / task_title
    output_dir.mkdir(exist_ok=True)

    for answer in answers:
        answer_text, answer_file_path, first_name, last_name = answer
        student_dir = output_dir / f"{first_name}_{last_name}"
        student_dir.mkdir(exist_ok=True)

        if answer_text:
            with open(student_dir / "answer.txt", "w", encoding="utf-8") as f:
                f.write(answer_text)

        if answer_file_path:
            for i, file_path in enumerate(answer_file_path.split(";")):
                if os.path.exists(file_path):
                    ext = os.path.splitext(file_path)[1] or ".bin"
                    shutil.copy(file_path, student_dir / f"file_{i}{ext}")

    await callback.message.answer(f"Все ответы сохранены в папке {output_dir}")
    await state.clear()
    await callback.answer()

# Для множественного выбора классов (в будущем): Добавьте в get_class_selection_keyboard кнопку "Добавить еще" и "Завершить", state.update_data(selected_classes=state.data.get('selected_classes', []) + [cls])
# В хендлерах callback проверяйте data == 'class_finish', затем переходите к следующему состоянию.