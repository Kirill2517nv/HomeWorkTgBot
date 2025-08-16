from aiogram.fsm.state import State, StatesGroup

class RegisterStates(StatesGroup):
    """Состояния для процесса регистрации студента."""
    first_name = State()  # Ввод имени
    last_name = State()   # Ввод фамилии
    class_number = State()  # Ввод номера класса

class NewTaskStates(StatesGroup):
    """Состояния для создания нового задания."""
    title = State()         # Ввод заголовка
    description = State()  # Ввод описания задания
    file = State()        # Прикрепление файла (или "нет")

class SendTaskStates(StatesGroup):
    """Состояния для отправки задания."""
    task_id = State()       # Выбор задания (инлайн)
    class_number = State()  # Выбор класса (если нужно)
    method = State()        # Выбор метода отправки (немедленно/по расписанию)
    schedule_time = State()  # Ввод времени отправки (для расписания)

class AnswerStates(StatesGroup):
    """Состояния для ответа на задание."""
    task_id = State()       # Выбор задания (инлайн)
    waiting_for_more_files = State()  # Ожидание текста или файлов ответа

class NewTestStates(StatesGroup):
    """Состояния для создания нового теста."""
    title = State()              # Ввод названия теста
    max_attempts = State()       # Ввод количества попыток
    question_text = State()      # Ввод текста вопроса
    question_file = State()      # Прикрепление файла к вопросу
    question_type = State()      # Выбор типа вопроса (choice/text)
    option_text = State()        # Ввод текста варианта ответа
    option_image = State()       # Прикрепление изображения для варианта
    correct_option = State()     # Указание правильного варианта
    correct_text_answer = State()  # Ввод правильного текстового ответа
    add_more_question = State()   # Решение о добавлении ещё вопроса

class TestStates(StatesGroup):
    """Состояния для прохождения теста."""
    select_test = State()  # Выбор теста
    question = State()     # Ответ на вопрос теста

class ListStudentsStates(StatesGroup):
    """Состояния для просмотра списка учеников."""
    class_number = State()  # Выбор класса (инлайн)

class ShowAnswersStates(StatesGroup):
    """Состояния для просмотра ответов."""
    task_id = State()  # Выбор задания (инлайн)