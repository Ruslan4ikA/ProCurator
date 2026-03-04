"""
Модуль анализа успеваемости
"""
import pandas as pd
import logging
from utils.helpers import (
    grade_to_score, is_debtor, is_success, is_quality,
    extract_semester_number, get_student_columns
)

logger = logging.getLogger(__name__)


class GradeAnalyzer:
    """Анализатор успеваемости студентов"""
    
    @staticmethod
    def calculate_average_score(df: pd.DataFrame) -> pd.DataFrame:
        """
        Добавляет строку со средним баллом по каждому студенту
        
        Возвращает:
            DataFrame с дополнительной строкой среднего балла
        """
        df_with_avg = df.copy()
        student_cols = get_student_columns(df)
        
        # Считаем средний балл по каждому студенту
        avg_row = {'Дисциплина': 'Средний балл', 'Тип': '', 'Семестр': ''}
        
        for student in student_cols:
            scores = df[student].apply(grade_to_score)
            avg_score = scores.mean()
            avg_row[student] = round(avg_score, 2)
        
        # Добавляем строку в конец
        df_with_avg = pd.concat([df_with_avg, pd.DataFrame([avg_row])], ignore_index=True)
        
        return df_with_avg
    
    @staticmethod
    def find_debtors(df: pd.DataFrame, semester_filter=None) -> list:
        """
        Выявляет студентов с академическими задолженностями
        
        Параметры:
            df: DataFrame с данными
            semester_filter: номер семестра для фильтрации (опционально)
        
        Возвращает:
            Список словарей с информацией о долгах
        """
        debt_data = []
        student_cols = get_student_columns(df)
        
        # Фильтрация по семестру
        if semester_filter:
            df = df[df['Семестр'].str.contains(f"{semester_filter} семестр", na=False)]
        
        for _, row in df.iterrows():
            for student in student_cols:
                grade = str(row[student]).lower()
                if grade in ['неуд', 'н/а', 'н/з', '']:
                    debt_data.append({
                        'Студент': student,
                        'Дисциплина': row['Дисциплина'],
                        'Тип': row['Тип'],
                        'Семестр': row['Семестр'],
                        'Оценка': row[student]
                    })
        
        logger.info(f"Найдено {len(debt_data)} долгов")
        return debt_data
    
    @staticmethod
    def calculate_performance_metrics(df: pd.DataFrame) -> dict:
        """
        Рассчитывает показатели успеваемости по семестрам
        
        Возвращает:
            Словарь с метриками по каждому семестру
        """
        metrics = {}
        student_cols = get_student_columns(df)
        
        # Группировка по семестрам
        for semester in df['Семестр'].unique():
            semester_df = df[df['Семестр'] == semester]
            
            total_grades = len(student_cols) * len(semester_df)
            
            # Абсолютная успеваемость
            success_count = sum(
                is_success(semester_df[student].iloc[i])
                for i in range(len(semester_df))
                for student in student_cols
            )
            absolute_performance = (success_count / total_grades * 100) if total_grades > 0 else 0
            
            # Качественная успеваемость
            quality_count = sum(
                is_quality(semester_df[student].iloc[i], semester_df['Тип'].iloc[i])
                for i in range(len(semester_df))
                for student in student_cols
            )
            quality_performance = (quality_count / total_grades * 100) if total_grades > 0 else 0
            
            # Количество долгов
            debt_count = sum(
                is_debtor(semester_df[student].iloc[i])
                for i in range(len(semester_df))
                for student in student_cols
            )
            
            metrics[semester] = {
                'absolute_performance': round(absolute_performance, 2),
                'quality_performance': round(quality_performance, 2),
                'debt_count': debt_count,
                'total_grades': total_grades
            }
        
        return metrics