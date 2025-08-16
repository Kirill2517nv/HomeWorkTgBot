from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import NewTestStates, TestStates
from db import Database
from utils import is_admin, send_file_message, send_message_with_buttons, download_photo, download_document
from config import logger, QUESTIONS_DIR, TESTS_DIR
from typing import Optional, List, Tuple

router = Router()


async def send_next_question(bot: Bot, message: Message, state: FSMContext, db: Database) -> None:
    """Отправляет следующий вопрос теста или завершает тест."""
    data = await state.get_data()
    questions = data["questions"]
    idx = data["current_index"]

    if idx >= len(questions):
        score = data["correct_answers"]
        total = len(questions)
        user_id = data["user_id"]
        first_name = data["first_name"]
        last_name = data["last_name"]
        test_id = data["test_id"]
        attempt_number = data["attempt_number"]

        result = db.get_user_result(user_id, test_id)
        if result:
            attempts_left = result[0]
            if attempts_left > 0:
                db.update_user_result(user_id, test_id, max(score, result[0]), total)
        else:
            test = db.get_test(test_id)
            if test:
                db.insert_user_result(user_id, first_name, last_name, test_id, score, total, test[2] - 1)

        await message.answer(f"✅ Тест завершен!\nВаш результат: {score}/{total}")
        await state.clear()
        return

    question_id, text = questions[idx]
    await state.update_data(current_question_id=question_id)
    question = db.get_question(question_id)
    if not question:
        await message.answer("Ошибка: вопрос не найден")
        await state.clear()
        return

    q_text, q_file, q_type = question
    await message.answer(f"Вопрос {idx + 1}/{len(questions)}:\n{q_text}")

    if q_file:
        await send_file_message(bot, message.chat.id, q_file)

    if q_type == "choice":
        options = db.get_options_by_question(question_id)
        buttons = []
        for i, opt in enumerate(options, 1):
            opt_id, opt_text, opt_image = opt
            if opt_image:
                await send_file_message(bot, message.chat.id, opt_image, caption=f"Вариант {i}")
                buttons.append((str(i), f"opt_{opt_id}"))
            else:
                buttons.append((opt_text, f"opt_{opt_id}"))

        await send_message_with_buttons(bot, message.chat.id, "Выберите ответ:", buttons)
        await state.set_state(TestStates.question)
    else:
        await message.answer("Введите ваш ответ текстом:")
        await state.update_data(current_question_type="text")
        await state.set_state(TestStates.question)


@router.message(F.text == "➕ Новый тест")
async def new_test_from_button(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("Эта функция доступна только учителю.")
        return

    await message.answer("Введите название теста:")
    await state.set_state(NewTestStates.title)


@router.message(NewTestStates.title)
async def process_test_title(message: Message, state: FSMContext, db: Database) -> None:
    """Сохраняет название теста и запрашивает количество попыток."""
    await state.update_data(test_title=message.text)
    await message.answer("Сколько раз можно пройти этот тест? (например: 2)")
    await state.set_state(NewTestStates.max_attempts)


@router.message(NewTestStates.max_attempts)
async def process_max_attempts(message: Message, state: FSMContext, db: Database) -> None:
    """Сохраняет количество попыток и начинает создание первого вопроса."""
    try:
        attempts = int(message.text)
        if attempts <= 0:
            raise ValueError("Количество попыток должно быть положительным.")

        data = await state.get_data()
        test_id = db.insert_test(data["test_title"], attempts)
        await state.update_data(test_id=test_id)
        await message.answer(
            f"Тест создан: {data['test_title']}\nМаксимум попыток: {attempts}\nВведите текст первого вопроса:")
        await state.set_state(NewTestStates.question_text)
    except ValueError as e:
        await message.answer(f"Ошибка: {e}. Введите число.")
        logger.error(f"Ошибка в /new_test (max_attempts): {e}, user_id: {message.from_user.id}")


@router.message(NewTestStates.question_text)
async def process_question_text(message: Message, state: FSMContext) -> None:
    """Сохраняет текст вопроса и запрашивает файл."""
    await state.update_data(question_text=message.text)
    await message.answer("Хотите прикрепить файл к этому вопросу? (да/нет)")
    await state.set_state(NewTestStates.question_file)


@router.message(NewTestStates.question_file)
async def process_question_file(message: Message, state: FSMContext, bot: Bot, db: Database) -> None:
    """Обрабатывает файл вопроса или переходит к выбору типа вопроса."""
    file_path: Optional[str] = None

    if message.text and message.text.lower() == "да":
        await message.answer("Загрузите файл (фото или документ):")
        return
    elif message.photo:
        file_path = await download_photo(bot, message.photo[-1].file_id, QUESTIONS_DIR,
                                         f"_question_{message.from_user.id}")
    elif message.document:
        file_path = await download_document(bot, message.document.file_id, message.document.file_name, QUESTIONS_DIR,
                                            f"_question_{message.from_user.id}")

    await state.update_data(question_file=file_path)
    await message.answer("Какой тип вопроса? (напишите: choice или text)")
    await state.set_state(NewTestStates.question_type)


@router.message(NewTestStates.question_type)
async def process_question_type(message: Message, state: FSMContext, db: Database) -> None:
    """Сохраняет тип вопроса и переходит к созданию вариантов или текстового ответа."""
    q_type = message.text.lower()
    if q_type not in ["choice", "text"]:
        await message.answer("Введите 'choice' или 'text'.")
        return

    data = await state.get_data()
    question_id = db.insert_question(
        test_id=data["test_id"],
        text=data["question_text"],
        file_path=data["question_file"],
        q_type=q_type
    )
    await state.update_data(question_id=question_id)

    if q_type == "choice":
        await state.update_data(options=[])
        await message.answer("Введите текст варианта 1 (или напишите 'фото'):")
        await state.set_state(NewTestStates.option_text)
    else:
        await message.answer("Введите правильный текстовый ответ:")
        await state.set_state(NewTestStates.correct_text_answer)


@router.message(NewTestStates.correct_text_answer)
async def process_correct_text_answer(message: Message, state: FSMContext, db: Database) -> None:
    """Сохраняет правильный текстовый ответ и запрашивает добавление нового вопроса."""
    data = await state.get_data()
    db.update_question_correct_text(data["question_id"], message.text)
    await message.answer("Вопрос сохранён. Добавить ещё вопрос? (да/нет)")
    await state.set_state(NewTestStates.add_more_question)


@router.message(NewTestStates.option_text)
async def process_option_text(message: Message, state: FSMContext) -> None:
    """Сохраняет текст варианта ответа или запрашивает фото."""
    data = await state.get_data()
    options: List[dict] = data.get("options", [])

    if message.text.lower() == "фото":
        await message.answer("Загрузите изображение для варианта:")
        await state.set_state(NewTestStates.option_image)
        return

    options.append({"text": message.text, "image": None})
    await state.update_data(options=options)

    if len(options) < 4:
        await message.answer(f"Введите текст варианта {len(options) + 1} (или 'фото'):")
    else:
        await message.answer("Какой вариант правильный? (введите номер 1-4)")
        await state.set_state(NewTestStates.correct_option)


@router.message(NewTestStates.option_image)
async def process_option_image(message: Message, state: FSMContext, bot: Bot) -> None:
    """Сохраняет изображение варианта ответа."""
    if not message.photo:
        await message.answer("Отправьте изображение.")
        return

    data = await state.get_data()
    options: List[dict] = data.get("options", [])
    file_path = await download_photo(bot, message.photo[-1].file_id, TESTS_DIR, f"_option_{message.from_user.id}")

    options.append({"text": None, "image": file_path})
    await state.update_data(options=options)

    if len(options) < 4:
        await message.answer(f"Введите текст варианта {len(options) + 1} (или 'фото'):")
        await state.set_state(NewTestStates.option_text)
    else:
        await message.answer("Какой вариант правильный? (введите номер 1-4)")
        await state.set_state(NewTestStates.correct_option)


@router.message(NewTestStates.correct_option)
async def process_correct_option(message: Message, state: FSMContext, db: Database) -> None:
    """Сохраняет варианты ответа и правильный вариант."""
    try:
        correct_index = int(message.text) - 1
        if not 0 <= correct_index < 4:
            raise ValueError("Номер должен быть от 1 до 4.")
    except ValueError:
        await message.answer("Введите число от 1 до 4.")
        logger.error(f"Ошибка в /new_test (correct_option): неверный номер, user_id: {message.from_user.id}")
        return

    data = await state.get_data()
    question_id = data["question_id"]
    options = data["options"]

    for i, opt in enumerate(options):
        db.insert_option(
            question_id=question_id,
            text=opt["text"],
            image_path=opt["image"],
            is_correct=(i == correct_index)
        )

    await message.answer("Вопрос сохранён. Добавить ещё вопрос? (да/нет)")
    await state.set_state(NewTestStates.add_more_question)


@router.message(NewTestStates.add_more_question)
async def process_add_more_question(message: Message, state: FSMContext) -> None:
    """Обрабатывает решение о добавлении нового вопроса."""
    if message.text.lower() == "да":
        await message.answer("Введите текст следующего вопроса:")
        await state.set_state(NewTestStates.question_text)
    else:
        await message.answer("Тест завершён!")
        await state.clear()


@router.message(F.text == "📝 Пройти тест")
async def test_from_button(message: Message, state: FSMContext, db: Database, bot: Bot) -> None:
    user_id = message.from_user.id
    tests = db.get_tests()
    available_tests: List[Tuple[int, str, int]] = []

    for test in tests:
        test_id, title, max_attempts = test
        result = db.get_user_result(user_id, test_id)
        if result:
            attempts_left = result[0]
            if attempts_left > 0:
                available_tests.append((test_id, title, attempts_left))
        else:
            available_tests.append((test_id, title, max_attempts))

    if not available_tests:
        await message.answer("Нет доступных тестов или попытки исчерпаны.")
        return

    buttons = [(f"{title} (осталось {attempts} попыток)", f"test_{test_id}") for test_id, title, attempts in available_tests]
    await send_message_with_buttons(bot, message.from_user.id, "Выберите тест:", buttons)
    await state.set_state(TestStates.select_test)


@router.callback_query(F.data.startswith("test_"))
async def process_test_selection(callback: CallbackQuery, state: FSMContext, db: Database, bot: Bot) -> None:
    """Обрабатывает выбор теста и начинает его прохождение."""
    test_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    first_name = callback.from_user.first_name
    last_name = callback.from_user.last_name or ""

    test = db.get_test(test_id)
    if not test:
        await callback.message.answer(f"Тест не найден.")
        await state.clear()
        return

    attempt_number = db.get_user_attempts(user_id, test_id) + 1
    if attempt_number > test[2]:
        await callback.message.answer("У вас больше нет попыток.")
        await state.clear()
        return

    questions = db.get_questions_by_test(test_id)
    if not questions:
        await callback.message.answer("В этом тесте нет вопросов.")
        await state.clear()
        return

    await state.update_data(
        test_id=test_id,
        questions=questions,
        current_index=0,
        correct_answers=0,
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        attempt_number=attempt_number
    )
    await send_next_question(bot, callback.message, state, db)
    await callback.answer()


@router.message(TestStates.question)
async def handle_text_answer(message: Message, state: FSMContext, db: Database, bot: Bot) -> None:
    """Обрабатывает текстовый ответ на вопрос теста."""
    data = await state.get_data()
    if "current_question_id" not in data:
        await message.answer("Ошибка: вопрос не найден")
        await state.clear()
        return

    if data.get("current_question_type") == "text":
        question_id = data["current_question_id"]
        correct_text = db.get_correct_text(question_id)

        user_answer = message.text.lower().strip()
        if user_answer == correct_text:
            await state.update_data(correct_answers=data["correct_answers"] + 1)

        db.insert_user_answer(
            user_id=data["user_id"],
            test_id=data["test_id"],
            question_id=question_id,
            answer_id=None,
            text_answer=user_answer,
            attempt_number=data["attempt_number"]
        )

        await state.update_data(current_index=data["current_index"] + 1)
        await send_next_question(bot, message, state, db)


@router.callback_query(F.data.startswith("opt_"))
async def process_answer(callback: CallbackQuery, state: FSMContext, db: Database, bot: Bot) -> None:
    """Обрабатывает выбор варианта ответа."""
    data = await state.get_data()
    if "current_question_id" not in data:
        await callback.message.answer("Ошибка: вопрос не найден")
        await state.clear()
        return

    option_id = int(callback.data.split("_")[1])
    is_correct = db.get_correct_option(option_id)

    if is_correct:
        await state.update_data(correct_answers=data["correct_answers"] + 1)

    db.insert_user_answer(
        user_id=data["user_id"],
        test_id=data["test_id"],
        question_id=data["current_question_id"],
        answer_id=option_id,
        text_answer=None,
        attempt_number=data["attempt_number"]
    )

    await state.update_data(current_index=data["current_index"] + 1)
    await send_next_question(bot, callback.message, state, db)
    await callback.answer()


@router.message(F.text == "📊 Результаты тестов")
async def test_results_from_button(message: Message, db: Database, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("Эта функция доступна только учителю.")
        return

    tests = db.get_tests()
    if not tests:
        await message.answer("Нет доступных тестов.")
        return

    buttons = [(test[1], f"results_{test[0]}") for test in tests]
    await send_message_with_buttons(bot, message.from_user.id, "Выберите тест для просмотра результатов:", buttons)

@router.callback_query(F.data.startswith("results_"))
async def process_test_results_selection(callback: CallbackQuery, db: Database, bot: Bot) -> None:
    """Показывает список студентов, проходивших тест."""
    test_id = int(callback.data.split("_")[1])
    users = db.get_test_users(test_id)

    if not users:
        await callback.message.answer("Нет результатов для этого теста.")
        await callback.answer()
        return

    buttons = [(f"{user[1]} {user[2]}", f"user_results_{test_id}_{user[0]}") for user in users]
    await send_message_with_buttons(bot, callback.from_user.id, "Выберите ученика:", buttons)
    await callback.answer()


@router.callback_query(F.data.startswith("user_results_"))
async def show_user_test_results(callback: CallbackQuery, db: Database, bot: Bot) -> None:
    """Показывает попытки студента для теста."""
    parts = callback.data.split("_")
    test_id = int(parts[2])
    user_id = int(parts[3])

    attempts = db.get_user_attempt_numbers(user_id, test_id)
    if not attempts:
        await callback.message.answer("Нет результатов для этого пользователя.")
        await callback.answer()
        return

    buttons = [(f"Попытка {attempt[0]}", f"attempt_{test_id}_{user_id}_{attempt[0]}") for attempt in attempts]
    await send_message_with_buttons(bot, callback.from_user.id, "Выберите попытку:", buttons)
    await callback.answer()


@router.callback_query(F.data.startswith("attempt_"))
async def show_attempt_details(callback: CallbackQuery, db: Database) -> None:
    """Показывает детали конкретной попытки."""
    parts = callback.data.split("_")
    test_id = int(parts[1])
    user_id = int(parts[2])
    attempt_number = int(parts[3])

    answers = db.get_attempt_details(user_id, test_id, attempt_number)
    if not answers:
        await callback.message.answer("Нет данных об этой попытке.")
        await callback.answer()
        return

    result = [
        f"{i}. {answer[0]}\nОтвет: {answer[1] or answer[2]} {answer[3]}\n"
        for i, answer in enumerate(answers, 1)
    ]
    await callback.message.answer("\n".join(result))
    await callback.answer()

