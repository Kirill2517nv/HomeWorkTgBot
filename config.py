import logging
from pathlib import Path
from dotenv import load_dotenv
import os

# Загружаем переменные из .env
load_dotenv()

# Константы из .env
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
DB_NAME = Path(os.getenv("DB_NAME", "students.db"))
HOMEWORKS_DIR: Path = Path(os.getenv("HOMEWORKS_DIR", "homeworks/"))
QUESTIONS_DIR: Path = Path(os.getenv("QUESTIONS_DIR", "questions/"))
TESTS_DIR: Path = Path(os.getenv("TESTS_DIR", "tests/"))

# Проверяем, что обязательные переменные заданы
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не указан в .env")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID не указан в .env")

# Создаём директории, если их нет
HOMEWORKS_DIR.mkdir(exist_ok=True)
QUESTIONS_DIR.mkdir(exist_ok=True)
TESTS_DIR.mkdir(exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger: logging.Logger = logging.getLogger(__name__)