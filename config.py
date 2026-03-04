"""
Конфигурация системы
"""
import os
from pathlib import Path

# Базовые пути
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
REPORTS_DIR = DATA_DIR / 'reports'
CONTACTS_DIR = DATA_DIR / 'contacts'
LOGS_DIR = BASE_DIR / 'logs'
TEMPLATES_DIR = BASE_DIR / 'templates'

# Создание директорий
for directory in [DATA_DIR, REPORTS_DIR, CONTACTS_DIR, LOGS_DIR, TEMPLATES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Настройки образовательного портала
PORTAL_URL = "https://portal.mgstu.ru"  # URL портала
HEADLESS_MODE = True  # Режим без отображения браузера

# Настройки SMTP
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.yandex.ru')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SENDER_EMAIL = os.getenv('SENDER_EMAIL', '')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD', '')

# Настройки форматов оценок
GRADE_MAPPING = {
    'отл.': 5,
    'хор.': 4,
    'уд.': 3,
    'н/з': 2,
    'неуд.': 2,
    'н/а': 2,
    'зач.': 5,
    '': 2
}

# Столбцы с информацией о дисциплине
INFO_COLUMNS = ['Дисциплина', 'Тип', 'Семестр']

# Настройки логирования
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'

# Настройки безопасности
KEY_FILE = BASE_DIR / '.secret_key'