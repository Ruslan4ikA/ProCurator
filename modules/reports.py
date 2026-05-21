"""Модуль генерации отчётов — .xlsx и .pdf."""
import os, sys
from pathlib import Path
import pandas as pd
from openpyxl.styles import Alignment, PatternFill, Font, Border, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from logger import logger
from modules.analytics import get_student_cols, get_report_dir, today_str, is_debtor, grade_to_score

RED   = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
HEAD  = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
ALT   = PatternFill(start_color="EBF3FB", end_color="EBF3FB", fill_type="solid")
WRAP  = Alignment(wrap_text=True, vertical="top")
HFONT = Font(color="FFFFFF", bold=True, size=10)
THIN  = Border(left=Side(style="thin",color="CCCCCC"), right=Side(style="thin",color="CCCCCC"),
               top=Side(style="thin",color="CCCCCC"), bottom=Side(style="thin",color="CCCCCC"))

def _save_excel(df, path, highlight=True):
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Успеваемость")
        ws = w.sheets["Успеваемость"]
        for ri in range(1, ws.max_row+1):
            for ci in range(1, ws.max_column+1):
                cell = ws.cell(ri, ci)
                cell.alignment = WRAP; cell.border = THIN
                if ri == 1:
                    cell.fill = HEAD; cell.font = HFONT
                elif highlight and ci > 3 and is_debtor(str(cell.value or "")):
                    cell.fill = RED
                elif ri % 2 == 0:
                    cell.fill = ALT
        for ci, col in enumerate(df.columns, 1):
            w = min(max(df[col].astype(str).map(len).max(), len(str(col)))+2, 45)
            ws.column_dimensions[get_column_letter(ci)].width = w
        ws.freeze_panes = "A2"

def _save_pdf(df, path, title, group_name):
    doc = SimpleDocTemplate(path, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    ts = ParagraphStyle("T", parent=styles["Title"], fontSize=13, textColor=colors.HexColor("#1F4E79"), spaceAfter=4)
    ss = ParagraphStyle("S", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#666666"), spaceAfter=10)
    elems = [Paragraph(title, ts),
             Paragraph(f"Группа: {group_name} | {datetime.now().strftime('%d.%m.%Y %H:%M')}", ss),
             HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1F4E79")),
             Spacer(1, 0.3*cm)]
    headers = list(df.columns)
    data = [headers] + [list(r) for r in df.itertuples(index=False)]
    pw = landscape(A4)[0] - 3*cm
    fc = min(3, len(headers))
    fw = [4*cm, 3*cm, 2.5*cm][:fc]
    sw = [(pw-sum(fw))/max(len(headers)-fc,1)]*(len(headers)-fc)
    cw = fw + sw
    tbl = Table(data, colWidths=cw, repeatRows=1)
    st = TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1F4E79")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,0),8), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("ALIGN",(0,0),(-1,0),"CENTER"), ("BOTTOMPADDING",(0,0),(-1,0),5),
        ("FONTSIZE",(0,1),(-1,-1),7), ("ALIGN",(0,1),(-1,-1),"CENTER"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#EBF3FB")]),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#CCCCCC")),
    ])
    for ri, row in enumerate(df.itertuples(), 1):
        for ci, col in enumerate(df.columns):
            if ci >= 3 and is_debtor(str(df.iloc[ri-1, ci])):
                st.add("BACKGROUND",(ci,ri),(ci,ri),colors.HexColor("#FFCCCC"))
    tbl.setStyle(st)
    elems.append(tbl)
    doc.build(elems)

def report_debtors(df, group_name, num_sem=None):
    import re
    student_cols = get_student_cols(df)
    if num_sem is None:
        nums = [int(m.group(1)) for s in df["Семестр"].unique() if (m := re.search(r"(\d+)", str(s)))]
        num_sem = max(nums) if nums else 1
    sem_df = df[df["Семестр"].str.contains(f"{num_sem} семестр", na=False)]
    rows = []
    for _, row in sem_df.iterrows():
        for s in student_cols:
            if is_debtor(row[s]):
                rows.append({"Студент": s, "Дисциплина": row["Дисциплина"],
                             "Тип аттестации": row["Тип"], "Семестр": row["Семестр"], "Оценка": row[s]})
    if not rows:
        logger.info(f"Должников за {num_sem} семестр не найдено")
        return []
    d = pd.DataFrame(rows)
    rd = get_report_dir(group_name, "Должники"); dt = today_str()
    xp = os.path.join(rd, f"должники_{num_sem}сем_{group_name}_{dt}.xlsx")
    pp = os.path.join(rd, f"должники_{num_sem}сем_{group_name}_{dt}.pdf")
    _save_excel(d, xp, highlight=False)
    _save_pdf(d, pp, f"Отчёт по должникам — {num_sem} семестр", group_name)
    logger.info(f"Отчёт по должникам: {len(rows)} записей → {xp}")
    return [xp, pp]

def report_full_period(df, group_name, individual=False):
    student_cols = get_student_cols(df)
    rd = get_report_dir(group_name, "Весь_период"); dt = today_str(); files = []
    if individual:
        for s in student_cols:
            sd = df[["Семестр","Дисциплина","Тип",s]].rename(columns={s:"Оценка"})
            sn = s.replace(" ","_")
            xp = os.path.join(rd, f"{sn}_период_{dt}.xlsx")
            pp = os.path.join(rd, f"{sn}_период_{dt}.pdf")
            _save_excel(sd, xp); _save_pdf(sd, pp, f"Успеваемость: {s}", group_name)
            files += [xp, pp]
    else:
        dc = df.copy()
        ar = {"Дисциплина":"Средний балл","Тип":"","Семестр":""}
        for s in student_cols: ar[s] = round(df[s].apply(grade_to_score).mean(), 2)
        dc = pd.concat([dc, pd.DataFrame([ar])], ignore_index=True)
        xp = os.path.join(rd, f"весь_период_{group_name}_{dt}.xlsx")
        pp = os.path.join(rd, f"весь_период_{group_name}_{dt}.pdf")
        _save_excel(dc, xp); _save_pdf(dc, pp, "Сводная ведомость успеваемости", group_name)
        files = [xp, pp]
    logger.info(f"Отчёт за весь период: {len(files)} файлов")
    return files

def report_by_semester(df, group_name, semester_number, individual=False):
    sd = df[df["Семестр"].str.contains(f"{semester_number} семестр", na=False)].copy()
    rd = get_report_dir(group_name, "По_семестрам"); dt = today_str(); files = []
    if individual:
        for s in get_student_cols(df):
            fd = sd[["Дисциплина","Тип",s]].rename(columns={s:"Оценка"})
            xp = os.path.join(rd, f"{s.replace(' ','_')}_{semester_number}сем_{dt}.xlsx")
            _save_excel(fd, xp); files.append(xp)
    else:
        xp = os.path.join(rd, f"отчёт_{semester_number}сем_{group_name}_{dt}.xlsx")
        pp = os.path.join(rd, f"отчёт_{semester_number}сем_{group_name}_{dt}.pdf")
        _save_excel(sd, xp); _save_pdf(sd, pp, f"Успеваемость за {semester_number} семестр", group_name)
        files = [xp, pp]
    logger.info(f"Отчёт за {semester_number} семестр: {files}")
    return files
