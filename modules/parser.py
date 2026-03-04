"""
Модуль парсинга данных из образовательного портала
"""
from bs4 import BeautifulSoup
import re
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class GradeParser:
    """Парсер данных об успеваемости"""
    
    @staticmethod
    def parse_grade_data(html_content: str) -> tuple:
        """
        Сбор данных из HTML страницы
        
        Возвращает:
            tuple: (DataFrame с данными, название группы)
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Извлечение названия группы
        group_match = re.search(r'Сводная ведомость для группы:\s*<b>(.*?)</b>', str(soup))
        group_name = group_match.group(1).strip() if group_match else "Неизвестная группа"
        
        # Парсинг студентов
        header_table = soup.find('table', {'id': 'cabinet_for_curator_table_top'})
        students = []
        if header_table:
            student_cells = header_table.find_all('th')
            for cell in student_cells:
                name = cell.get_text(strip=True)
                if name and name != '-':
                    students.append(name)
        
        # Парсинг предметов
        left_table = soup.find('table', {'id': 'cabinet_for_curator_table_left'})
        subjects = []
        current_semester = ""
        
        if left_table:
            rows = left_table.find_all('tr')
            for row in rows:
                semester_cell = row.find('td', class_='semester')
                if semester_cell:
                    current_semester = semester_cell.get_text(strip=True)
                    continue
                
                cells = row.find_all('td')
                if len(cells) >= 2:
                    subject_id = cells[0].get_text(strip=True)
                    subject_name_full = cells[1].get_text(strip=True)
                    if subject_id.isdigit() and subject_name_full:
                        # Извлечение типа предмета из последних скобок
                        subject_type = ""
                        subject_name_clean = subject_name_full
                        
                        # Ищем последние скобки
                        if '(' in subject_name_full and ')' in subject_name_full:
                            last_open_bracket = subject_name_full.rfind('(')
                            last_close_bracket = subject_name_full.rfind(')')
                            
                            if (last_open_bracket != -1 and 
                                last_close_bracket != -1 and 
                                last_close_bracket > last_open_bracket):
                                subject_type = subject_name_full[last_open_bracket + 1:last_close_bracket].strip()
                                subject_name_clean = subject_name_full[:last_open_bracket].strip()
                        
                        subjects.append({
                            'id': int(subject_id),
                            'name': subject_name_clean,
                            'type': subject_type,
                            'semester': current_semester
                        })
        
        # Парсинг оценок
        grades_data = {}
        table = soup.find('table', {'id': 'cabinet_for_curator_table'})
        
        if table:
            rows = table.find_all('tr')
            for row in rows:
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
        
        # Создание DataFrame
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
        logger.info(f"Данные успешно спарсены: {len(df)} дисциплин, {len(students)} студентов")
        
        return df, group_name