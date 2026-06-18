"""
modules/curator_report.py
Генерация план-отчёта куратора в формате .docx на основе шаблона.
"""
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from logger import logger

# Шаблон должен лежать в data/curator_report_template.docx
TEMPLATE_PATH = Path(__file__).parent.parent / "data" / "curator_report_template.docx"

GRADE_MAP = {
    "отл.": 5, "хор.": 4, "уд.": 3,
    "неуд.": 2, "н/з": 2, "незач.": 2,
    "зач.": 3,  # зачёт считаем как 3 (сдано, но не "высокое")
}


def _get_last_semester(df):
    if "Семестр" not in df.columns:
        return None, df
    semesters = df["Семестр"].dropna().unique()

    def sem_num(s):
        m = re.search(r'\d+', str(s))
        return int(m.group()) if m else 0

    last = max(semesters, key=sem_num)
    return last, df[df["Семестр"] == last]


def calc_stats(df) -> dict:
    """
    Рассчитывает абсолютную и качественную успеваемость.

    Абсолютная: доля студентов без задолженностей (все оценки >= 3).
    Качественная: доля студентов, у которых все экзаменационные оценки 4 или 5.

    Возвращает dict: absolute, quality, total, semester.
    """
    from modules.analytics import get_student_cols

    student_cols = get_student_cols(df)
    N = len(student_cols)
    if N == 0:
        return {"absolute": 0.0, "quality": 0.0, "total": 0, "semester": ""}

    last_sem, df_sem = _get_last_semester(df)

    count_abs = 0
    count_qual = 0

    for col in student_cols:
        grades_raw = df_sem[col].dropna().tolist()
        has_fail = False
        numeric = []

        for g in grades_raw:
            g_str = str(g).strip().lower()
            val = GRADE_MAP.get(g_str)
            if val is not None:
                numeric.append(val)
                if val <= 2:
                    has_fail = True

        if not has_fail:
            count_abs += 1
            # Качественная: только 4 и 5 среди ненулевых оценок
            rated = [v for v in numeric if v in (3, 4, 5)]
            if rated and all(v >= 4 for v in rated):
                count_qual += 1

    absolute = round(count_abs / N * 100, 1)
    quality  = round(count_qual / N * 100, 1)

    logger.info(f"Успеваемость [{last_sem}]: абс={absolute}%, кач={quality}%, N={N}")
    return {
        "absolute": absolute,
        "quality":  quality,
        "total":    N,
        "semester": str(last_sem) if last_sem else "",
    }


def generate_curator_report(df, group_name: str) -> bytes:
    """
    Заполняет шаблон план-отчёта и возвращает bytes готового .docx.

    Заполняется:
      - учебная группа → group_name
      - Абсолютная успеваемость → рассчитанное значение
      - Качественная успеваемость → рассчитанное значение
    """
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError("Установите python-docx: pip install python-docx")

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Шаблон не найден: {TEMPLATE_PATH}\n"
            f"Скопируйте файл шаблона (СМК-О-РИ-УМУ-01-22) в папку data/ проекта "
            f"и переименуйте в curator_report_template.docx"
        )

    stats = calc_stats(df)
    abs_str  = str(stats["absolute"])
    qual_str = str(stats["quality"])

    doc = Document(str(TEMPLATE_PATH))

    for para in doc.paragraphs:
        text = para.text

        # ── Учебная группа ───────────────────────────────────────────────────
        if "учебная группа" in text.lower():
            for run in para.runs:
                if run.text == "\t":
                    run.text = " " + group_name
                    break

        # ── Абсолютная / качественная успеваемость ───────────────────────────
        # Структура параграфа (индексы runs):
        #  [0] '5.Абсолютная успеваемость'  [1] '\t'  [2] '% '
        #  [3] '6.Качественная'  [4] ' успеваемость '
        #  [5] '\t'  [6] '\t'  [7] '%'
        elif "абсолютная успеваемость" in text.lower():
            runs = para.runs
            if len(runs) > 1 and runs[1].text == "\t":
                runs[1].text = f" {abs_str}%"
            if len(runs) > 2 and "%" in runs[2].text:
                runs[2].text = " "         # убираем оригинальный "%"
            if len(runs) > 5 and runs[5].text == "\t":
                runs[5].text = f" {qual_str}%"
            if len(runs) > 6 and runs[6].text == "\t":
                runs[6].text = ""
            if len(runs) > 7 and runs[7].text == "%":
                runs[7].text = ""

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    logger.info(f"Отчёт куратора сформирован: группа={group_name}")
    return buf.read()
