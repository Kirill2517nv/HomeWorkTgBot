import sqlite3
from typing import List, Tuple, Optional, Any
from datetime import datetime
from pathlib import Path
from config import DB_NAME, logger

class Database:
    """Класс для работы с базой данных SQLite."""

    def __init__(self, db_path: Path = DB_NAME):
        """Инициализация базы данных."""
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Создаёт и возвращает соединение с базой данных."""
        return sqlite3.connect(self.db_path)

    def init_db(self) -> None:
        """Создаёт все необходимые таблицы в базе данных."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    class_number INTEGER NOT NULL,
                    telegram_id INTEGER UNIQUE NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    file_path TEXT DEFAULT NULL
                );
                
                CREATE TABLE IF NOT EXISTS task_assignments (
                    task_id INTEGER,
                    class_number INTEGER,
                    send_date DATETIME,
                    PRIMARY KEY (task_id, class_number),
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                );

                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER REFERENCES students(id),
                    task_id INTEGER REFERENCES tasks(id),
                    answer_text TEXT DEFAULT NULL,
                    answer_file_path TEXT DEFAULT NULL,
                    sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    max_attempts INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id INTEGER REFERENCES tests(id),
                    file_path TEXT,
                    type TEXT DEFAULT 'choice',
                    correct_text TEXT,
                    text TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS options (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER REFERENCES questions(id),
                    text TEXT,
                    image_path TEXT,
                    is_correct BOOLEAN NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS user_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    first_name TEXT,
                    last_name TEXT,
                    test_id INTEGER,
                    best_score INTEGER DEFAULT 0,
                    total INTEGER,
                    attempts_left INTEGER,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    test_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    answer_id INTEGER DEFAULT NULL, 
                    text_answer TEXT DEFAULT NULL,   
                    attempt_number INTEGER NOT NULL,
                    answer_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES students(telegram_id),
                    FOREIGN KEY(test_id) REFERENCES tests(id),
                    FOREIGN KEY(question_id) REFERENCES questions(id),
                    FOREIGN KEY(answer_id) REFERENCES options(id)
                );
            """)
            conn.commit()
            logger.info("База данных инициализирована")

    def insert_student(self, first_name: str, last_name: str, class_number: int, telegram_id: int) -> None:
        """Добавляет нового студента в базу данных."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO students (first_name, last_name, class_number, telegram_id)
                VALUES (?, ?, ?, ?)
            """, (first_name, last_name, class_number, telegram_id))
            conn.commit()
            logger.info(f"Добавлен студент: {first_name} {last_name}")

    def get_student(self, telegram_id: int) -> Optional[Tuple[int, str, str, int, int]]:
        """Возвращает данные студента по telegram_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM students WHERE telegram_id = ?", (telegram_id,))
            return cursor.fetchone()

    def insert_task(self, title: str, description: str, file_path: Optional[str] = None) -> int:
        """Добавляет новое задание и возвращает его ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tasks (title, description, file_path) VALUES (?, ?, ?)",
                (title, description, file_path)
            )
            conn.commit()
            task_id = cursor.lastrowid
            logger.info(f"Создано задание: {title}, ID: {task_id}")
            return task_id

    def assign_task_to_class(self, task_id: int, class_number: int) -> None:
        """Отмечает, что задание было отправлено определенному классу."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO task_assignments (task_id, class_number, send_date) VALUES (?, ?, ?)",
                (task_id, class_number, datetime.now())
            )
            conn.commit()
            logger.info(f"Задание {task_id} назначено классу {class_number}")

    def get_tasks_not_sent_to_all(self) -> List[Tuple[int, str]]:
        """
        Возвращает список заданий (id, title), которые не были отправлены
        всем существующим классам.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, t.title
                FROM tasks t
                WHERE (
                    SELECT COUNT(DISTINCT class_number)
                    FROM students
                ) > (
                    SELECT COUNT(class_number)
                    FROM task_assignments ta
                    WHERE ta.task_id = t.id
                )
            """)
            return cursor.fetchall()

    def get_classes_for_task(self, task_id: int) -> List[int]:
        """
        Возвращает список уникальных номеров классов, которым
        заданное задание еще не было отправлено.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT s.class_number
                FROM students s
                WHERE s.class_number NOT IN (
                    SELECT ta.class_number
                    FROM task_assignments ta
                    WHERE ta.task_id = ?
                )
                ORDER BY s.class_number
            """, (task_id,))
            return [row[0] for row in cursor.fetchall()]

    def get_task(self, task_id: int) -> Optional[Tuple[int, str, str, str]]:
        """Возвращает данные задания по ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            return cursor.fetchone()

    def get_students_by_class(self, class_number: int) -> List[Tuple[int]]:
        """Возвращает telegram_id студентов определённого класса."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id FROM students WHERE class_number = ?", (class_number,))
            return cursor.fetchall()

    def get_student_names_by_class(self, class_number: int) -> List[Tuple[str, str]]:
        """Возвращает список студентов (имя, фамилия) по номеру класса."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT first_name, last_name
                FROM students
                WHERE class_number = ?
            """, (class_number,))
            return cursor.fetchall()

    def insert_answer(self, student_id: int, task_id: int, answer_text: Optional[str], answer_file_path: Optional[str]) -> None:
        """Добавляет ответ студента на задание."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO answers (student_id, task_id, answer_text, answer_file_path)
                VALUES (?, ?, ?, ?)
            """, (student_id, task_id, answer_text, answer_file_path))
            conn.commit()
            logger.info(f"Добавлен ответ на задание {task_id} от студента {student_id}")

    def get_answers_by_task(self, task_id: int) -> List[Tuple[str, str, str, str]]:
        """Возвращает ответы на задание с именами студентов."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.answer_text, a.answer_file_path, s.first_name, s.last_name
                FROM answers a
                JOIN students s ON a.student_id = s.id
                WHERE a.task_id = ?
            """, (task_id,))
            return cursor.fetchall()

    def get_answers_by_task_and_student(self, student_id: int, task_id: int) -> List[Tuple[str, str, str, str]]:
        """Возвращает ответ студента на задание."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.answer_text, a.answer_file_path, s.first_name, s.last_name
                FROM answers a
                JOIN students s ON a.student_id = s.id
                WHERE a.task_id = ? AND a.student_id = ?
            """, (task_id, student_id))
            return cursor.fetchall()

    def get_unique_classes(self) -> List[int]:
        """Возвращает список уникальных номеров классов из таблицы students."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT class_number FROM students ORDER BY class_number")
            return [row[0] for row in cursor.fetchall()]

    def get_tasks_for_student_class(self, telegram_id: int) -> List[Tuple[int, str]]:
        """
        Возвращает список заданий (id, title), назначенных классу, в котором учится студент.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, t.title
                FROM tasks t
                JOIN task_assignments ta ON t.id = ta.task_id
                JOIN students s ON ta.class_number = s.class_number
                WHERE s.telegram_id = ?
                ORDER BY t.id DESC
            """, (telegram_id,))
            return cursor.fetchall()

    def get_all_tasks(self) -> List[Tuple[int, str]]:
        """Возвращает список всех созданных заданий (id, title)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM tasks ORDER BY id DESC")
            return cursor.fetchall()

    def insert_test(self, title: str, max_attempts: int) -> int:
        """Добавляет новый тест и возвращает его ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tests (title, max_attempts) VALUES (?, ?)", (title, max_attempts))
            conn.commit()
            test_id = cursor.lastrowid
            logger.info(f"Создан тест: {title}, ID: {test_id}")
            return test_id

    def get_test(self, test_id: int) -> Optional[Tuple[int, str, int]]:
        """Возвращает данные теста по ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, max_attempts FROM tests WHERE id = ?", (test_id,))
            return cursor.fetchone()

    def get_tests(self) -> List[Tuple[int, str, int]]:
        """Возвращает список тестов (id, title, max_attempts)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, max_attempts FROM tests")
            return cursor.fetchall()

    def insert_question(self, test_id: int, text: str, file_path: Optional[str], q_type: str) -> int:
        """Добавляет вопрос к тесту и возвращает его ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO questions (test_id, text, file_path, type)
                VALUES (?, ?, ?, ?)
            """, (test_id, text, file_path, q_type))
            conn.commit()
            question_id = cursor.lastrowid
            logger.info(f"Добавлен вопрос к тесту {test_id}, ID: {question_id}")
            return question_id

    def update_question_correct_text(self, question_id: int, correct_text: str) -> None:
        """Обновляет правильный текстовый ответ для вопроса."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE questions SET correct_text = ? WHERE id = ?", (correct_text.lower().strip(), question_id))
            conn.commit()
            logger.info(f"Обновлён правильный ответ для вопроса {question_id}")

    def insert_option(self, question_id: int, text: Optional[str], image_path: Optional[str], is_correct: bool) -> None:
        """Добавляет вариант ответа для вопроса."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO options (question_id, text, image_path, is_correct)
                VALUES (?, ?, ?, ?)
            """, (question_id, text, image_path, is_correct))
            conn.commit()
            logger.info(f"Добавлен вариант ответа для вопроса {question_id}")

    def get_questions_by_test(self, test_id: int) -> List[Tuple[int, str]]:
        """Возвращает вопросы теста (id, text)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, text FROM questions WHERE test_id = ?", (test_id,))
            return cursor.fetchall()

    def get_question(self, question_id: int) -> Optional[Tuple[str, str, str]]:
        """Возвращает данные вопроса (text, file_path, type)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT text, file_path, type FROM questions WHERE id = ?", (question_id,))
            return cursor.fetchone()

    def get_options_by_question(self, question_id: int) -> List[Tuple[int, str, str]]:
        """Возвращает варианты ответа для вопроса (id, text, image_path)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, text, image_path FROM options WHERE question_id = ?", (question_id,))
            return cursor.fetchall()

    def get_correct_option(self, option_id: int) -> bool:
        """Проверяет, является ли вариант ответа правильным."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_correct FROM options WHERE id = ?", (option_id,))
            result = cursor.fetchone()
            return result[0] if result else False

    def get_correct_text(self, question_id: int) -> Optional[str]:
        """Возвращает правильный текстовый ответ для вопроса."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT correct_text FROM questions WHERE id = ?", (question_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def insert_user_answer(self, user_id: int, test_id: int, question_id: int, answer_id: Optional[int], text_answer: Optional[str], attempt_number: int) -> None:
        """Добавляет ответ пользователя на вопрос теста."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_answers (user_id, test_id, question_id, answer_id, text_answer, attempt_number)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, test_id, question_id, answer_id, text_answer, attempt_number))
            conn.commit()
            logger.info(f"Добавлен ответ пользователя {user_id} на вопрос {question_id}")

    def insert_user_result(self, user_id: int, first_name: str, last_name: str, test_id: int, best_score: int, total: int, attempts_left: int) -> None:
        """Добавляет результат теста пользователя."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_results (user_id, first_name, last_name, test_id, best_score, total, attempts_left)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, first_name, last_name, test_id, best_score, total, attempts_left))
            conn.commit()
            logger.info(f"Добавлен результат теста {test_id} для пользователя {user_id}")

    def update_user_result(self, user_id: int, test_id: int, best_score: int, total: int) -> None:
        """Обновляет результат теста пользователя."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_results
                SET best_score = ?, total = ?, completed_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND test_id = ?
            """, (best_score, total, user_id, test_id))
            cursor.execute("""
                            UPDATE user_results
                            SET attempts_left = attempts_left - 1
                            WHERE user_id = ? AND test_id = ? AND attempts_left > 0
                        """, (user_id, test_id))
            conn.commit()
            logger.info(f"Обновлён результат теста {test_id} для пользователя {user_id}")


    def get_user_result(self, user_id: int, test_id: int) -> Optional[Tuple[int]]:
        """Возвращает результат пользователя для теста (attempts_left)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT attempts_left FROM user_results WHERE user_id = ? AND test_id = ?", (user_id, test_id))
            return cursor.fetchone()

    def get_user_attempts(self, user_id: int, test_id: int) -> int:
        """Возвращает количество попыток пользователя для теста."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM user_results WHERE user_id = ? AND test_id = ?", (user_id, test_id))
            return cursor.fetchone()[0]

    def get_test_users(self, test_id: int) -> List[Tuple[int, str, str]]:
        """Возвращает пользователей, проходивших тест."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT u.user_id, s.first_name, s.last_name
                FROM user_answers u
                JOIN students s ON u.user_id = s.telegram_id
                WHERE u.test_id = ?
            """, (test_id,))
            return cursor.fetchall()

    def get_user_attempt_numbers(self, user_id: int, test_id: int) -> List[Tuple[int]]:
        """Возвращает номера попыток пользователя для теста."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT attempt_number
                FROM user_answers
                WHERE user_id = ? AND test_id = ?
                ORDER BY attempt_number
            """, (user_id, test_id))
            return cursor.fetchall()

    def get_attempt_details(self, user_id: int, test_id: int, attempt_number: int) -> List[Tuple[str, str, str, str]]:
        """Возвращает детали попытки пользователя."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT q.text, o.text, ua.text_answer,
                    CASE WHEN o.is_correct = 1 OR LOWER(ua.text_answer) = LOWER(q.correct_text)
                        THEN '✅' ELSE '❌' END as is_correct
                FROM user_answers ua
                JOIN questions q ON ua.question_id = q.id
                LEFT JOIN options o ON ua.answer_id = o.id
                WHERE ua.user_id = ? AND ua.test_id = ? AND ua.attempt_number = ?
                ORDER BY ua.answer_time
            """, (user_id, test_id, attempt_number))
            return cursor.fetchall()