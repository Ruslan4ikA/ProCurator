"""Модуль аналитики — парсинг HTML портала и расчёт показателей успеваемости."""
import os, sys, re
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from logger import logger
import config as cfg

GRADE_MAP = {"отл.": 5, "хор.": 4, "уд.": 3, "зач.": 5,
             "н/з": 2, "неуд.": 2, "н/а": 2, "": 2}

def grade_to_score(g: str) -> float:
    return GRADE_MAP.get(str(g).strip().lower(), 2.0)

def is_debtor(g: str) -> bool:
    return str(g).strip().lower() in {"н/з", "неуд.", "н/а", ""}

def get_student_cols(df: pd.DataFrame) -> list:
    return [c for c in df.columns if c not in {"Дисциплина", "Тип", "Семестр"}]

def get_report_dir(group_name: str, report_type: str) -> str:
    base = cfg.get("report_dir", "reports")
    path = os.path.join(base, group_name, report_type)
    os.makedirs(path, exist_ok=True)
    return path

def today_str() -> str:
    return datetime.now().strftime("%d_%m_%Y")


def parse_grade_data(html_content: str) -> tuple:
    """
    Парсинг HTML страницы кабинета куратора портала МГТУ.
    Возвращает: (DataFrame с данными, название группы)
    Источник: ProCurator/modules/parser.py -> GradeParser.parse_grade_data
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Название группы
    group_match = re.search(r'Сводная ведомость для группы:\s*<b>(.*?)</b>', str(soup))
    group_name = group_match.group(1).strip() if group_match else "Неизвестная группа"
    logger.info(f"Группа: {group_name}")

    # Студенты (шапка)
    header_table = soup.find('table', {'id': 'cabinet_for_curator_table_top'})
    students = []
    if header_table:
        for cell in header_table.find_all('th'):
            name = cell.get_text(strip=True)
            if name and name != '-':
                students.append(name)
    logger.info(f"Найдено студентов: {len(students)}")

    # Дисциплины (левая колонка)
    left_table = soup.find('table', {'id': 'cabinet_for_curator_table_left'})
    subjects = []
    current_semester = ""

    if left_table:
        for row in left_table.find_all('tr'):
            semester_cell = row.find('td', class_='semester')
            if semester_cell:
                current_semester = semester_cell.get_text(strip=True)
                continue

            cells = row.find_all('td')
            if len(cells) >= 2:
                subject_id = cells[0].get_text(strip=True)
                subject_name_full = cells[1].get_text(strip=True)
                if subject_id.isdigit() and subject_name_full:
                    subject_type = ""
                    subject_name_clean = subject_name_full

                    # Тип аттестации — в последних скобках
                    if '(' in subject_name_full and ')' in subject_name_full:
                        lo = subject_name_full.rfind('(')
                        lc = subject_name_full.rfind(')')
                        if lo != -1 and lc != -1 and lc > lo:
                            subject_type = subject_name_full[lo + 1:lc].strip()
                            subject_name_clean = subject_name_full[:lo].strip()

                    subjects.append({
                        'id': int(subject_id),
                        'name': subject_name_clean,
                        'type': subject_type,
                        'semester': current_semester
                    })
    logger.info(f"Найдено дисциплин: {len(subjects)}")

    # Оценки (центральная таблица)
    grades_data = {}
    table = soup.find('table', {'id': 'cabinet_for_curator_table'})

    if table:
        for row in table.find_all('tr'):
            row_id = row.get('id')
            if row_id and row_id.startswith('row_'):
                row_num = int(row_id.split('_')[1])
                grade_cells = row.find_all('td')

                for col_num, cell in enumerate(grade_cells):
                    if col_num < len(students):
                        grade = cell.get_text(strip=True)
                        student = students[col_num]
                        if student not in grades_data:
                            grades_data[student] = {}
                        grades_data[student][row_num] = grade

    # Сборка DataFrame
    data = []
    for subject in subjects:
        row_data = {
            'Дисциплина': subject['name'],
            'Тип': subject['type'],
            'Семестр': subject['semester']
        }
        for student in students:
            row_data[student] = grades_data.get(student, {}).get(subject['id'], '')
        data.append(row_data)

    df = pd.DataFrame(data)
    logger.info(f"DataFrame: {len(df)} дисциплин × {len(students)} студентов")
    return df, group_name


def get_summary_stats(df: pd.DataFrame) -> dict:
    student_cols = get_student_cols(df)
    semesters = df["Семестр"].unique().tolist()
    last_sem = semesters[-1] if semesters else ""
    sem_df = df[df["Семестр"] == last_sem] if last_sem else df
    debtors = set()
    for _, row in sem_df.iterrows():
        for s in student_cols:
            if is_debtor(row[s]):
                debtors.add(s)
    all_scores = [grade_to_score(v) for s in student_cols for v in df[s]]
    avg = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0
    return {
        "total_students": len(student_cols),
        "debtors_count": len(debtors),
        "avg_score": avg,
        "last_semester": last_sem,
        "semesters_count": len(semesters),
    }