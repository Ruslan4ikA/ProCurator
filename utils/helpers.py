"""
Вспомогательные функции
"""
from datetime import datetime
import re


def grade_to_score(grade: str) -> int:
    """Преобразует текстовую оценку в числовой балл (2–5)"""
    g = str(grade).strip().lower()
    mapping = {
        'отл.': 5, 'отлично': 5, 'зач.': 5,
        'хор.': 4, 'хорошо': 4,
        'уд.': 3, 'удовл.': 3,
        'н/з': 2, 'неуд.': 2, 'н/а': 2, '': 2
    }
    return mapping.get(g, 2)


def is_debtor(grade: str) -> bool:
    """Проверка, является ли оценка долгом"""
    return str(grade).lower() in {'н/з', 'неуд.', 'н/а', ''}


def is_success(grade: str) -> bool:
    """Абсолютная успеваемость: оценка ≥ 3 (включая зачёты)"""
    return grade_to_score(grade) >= 3


def is_quality(grade: str, assessment_type: str) -> bool:
    """Качественная успеваемость: '4' или '5', НЕ включая зачёты"""
    g = str(grade).strip().lower()
    # Только экзамены и зачёты с оценкой
    if 'зачет с оценкой' in assessment_type.lower():
        return g in {'отл.', 'хор.', 'отлично', 'хорошо'}
    elif 'зачет' in assessment_type.lower() or 'зач.' in g:
        return False
    return g in {'отл.', 'хор.', 'отлично', 'хорошо'}


def extract_semester_number(semester_str: str) -> int:
    """Извлекает номер семестра из строки вида '1 семестр'"""
    match = re.search(r'(\d+)', str(semester_str))
    return int(match.group(1)) if match else None


def get_current_date() -> str:
    """Возвращает текущую дату в формате DD_MM_YYYY"""
    return datetime.now().strftime("%d_%m_%Y")


def sanitize_filename(filename: str) -> str:
    """Очищает имя файла от недопустимых символов"""
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


def get_student_columns(df) -> list:
    """Возвращает список столбцов со студентами (исключая служебные)"""
    from config import INFO_COLUMNS
    return [col for col in df.columns if col not in INFO_COLUMNS]