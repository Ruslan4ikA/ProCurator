"""Модуль рассылки — SMTP с Excel-файлом получателей и умным сопоставлением."""
import os, sys, smtplib, mimetypes, re
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from email import encoders

sys.path.insert(0, str(Path(__file__).parent.parent))
from logger import logger
import config as cfg


# ─── Загрузка получателей ───────────────────────────────────────

def load_recipients_from_excel(filepath: str) -> list:
    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas не установлен")
        return []

    if not os.path.isfile(filepath):
        logger.warning(f"Файл получателей не найден: {filepath}")
        return []

    try:
        df = pd.read_excel(filepath, header=0, engine="openpyxl")
        if df.shape[1] < 3:
            logger.error(f"Нужно минимум 3 столбца, найдено {df.shape[1]}")
            return []

        col_parent = df.columns[0]
        col_student = df.columns[1]
        col_email = df.columns[2]

        result = []
        for _, row in df.iterrows():
            parent  = str(row[col_parent]).strip()
            student = str(row[col_student]).strip()
            email   = str(row[col_email]).strip()
            if not email or "@" not in email or parent.lower() in ("nan", ""):
                continue
            result.append({"parent_name": parent,
                            "student_name": student,
                            "email": email})

        logger.info(f"Загружено получателей: {len(result)}")
        return result
    except Exception as e:
        logger.error(f"Ошибка чтения файла получателей: {e}")
        return []


# ─── Сопоставление файл ↔ студент ──────────────────────────────

def _surname(full_name: str) -> str:
    """Возвращает первое слово (фамилию) из ФИО."""
    parts = full_name.strip().split()
    return parts[0].lower() if parts else ""


def _find_files_for_student(all_files: list, student_name: str) -> list:
    """
    Ищет файлы относящиеся к студенту ТОЛЬКО по фамилии (первое слово ФИО).
    Это исключает ложные совпадения по отчеству.
    """
    surname = _surname(student_name)
    if not surname:
        return []

    matched = []
    for f in all_files:
        fname = os.path.basename(f).lower()
        # Фамилия должна присутствовать как отдельный токен в имени файла
        # Имя файла содержит подчёркивания: Кардаш_Михаил_Михайлович_5сем_...
        # Разбиваем по подчёркиванию, точке, пробелу
        tokens = re.split(r'[_\.\s\-]', fname)
        if surname in tokens:
            matched.append(f)

    return matched


def _is_group_report(file_paths: list) -> bool:
    """
    Проверяет — является ли набор файлов групповым отчётом
    (не привязанным к конкретному студенту).
    Если ни один файл не содержит имён из DataFrame — это групповой отчёт.
    """
    # Групповые отчёты содержат слова: весь_период, должники, сем_
    # но НЕ содержат фамилию конкретного студента в начале имени
    group_markers = ["весь_период", "должники", "отчёт_", "группа", "свод"]
    for f in file_paths:
        fname = os.path.basename(f).lower()
        if any(m in fname for m in group_markers):
            return True
    return False


def preview_send(file_paths: list, recipients_excel: str = "") -> list:
    """
    Возвращает превью рассылки — список словарей:
    [{"parent": "...", "student": "...", "email": "...", "files": [...], "warning": "..."}]
    Используется для показа модального окна подтверждения.
    """
    result = []

    if recipients_excel and os.path.isfile(recipients_excel):
        recipients = load_recipients_from_excel(recipients_excel)
        for rec in recipients:
            files_for = _find_files_for_student(file_paths, rec["student_name"])
            warning = ""
            if not files_for:
                warning = "⚠️ Файл для этого студента не найден"
            result.append({
                "parent":  rec["parent_name"],
                "student": rec["student_name"],
                "email":   rec["email"],
                "files":   [os.path.basename(f) for f in files_for],
                "warning": warning,
            })
    else:
        # Простые адреса
        conf = cfg.load()
        raw = conf.get("email_recipients", "")
        for email in [e.strip() for e in raw.split(",") if "@" in e.strip()]:
            result.append({
                "parent":  email,
                "student": "",
                "email":   email,
                "files":   [os.path.basename(f) for f in file_paths],
                "warning": "ℹ️ Excel-файл не задан, отправка всем получателям",
            })

    return result


# ─── SMTP ───────────────────────────────────────────────────────

def _build_attachment(filepath: str) -> MIMEBase:
    filename = os.path.basename(filepath)
    ctype, encoding = mimetypes.guess_type(filepath)
    if ctype is None or encoding is not None:
        ctype = "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)
    with open(filepath, "rb") as f:
        part = MIMEBase(maintype, subtype)
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment",
                    filename=("utf-8", "", filename))
    part.set_param("name", filename, header="Content-Type", charset="utf-8")
    return part


def _send_one(to_email, to_name, subject, body, file_paths, smtp_conf) -> bool:
    msg = MIMEMultipart("mixed")
    from_addr = smtp_conf.get("from_addr") or smtp_conf["login"]
    from_name = smtp_conf.get("from_name", "AI-ассистент куратора")
    msg["From"]    = formataddr((str(Header(from_name, "utf-8")), from_addr))
    msg["To"]      = formataddr((str(Header(to_name,   "utf-8")), to_email))
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(body, "plain", "utf-8"))

    attached = 0
    for path in file_paths:
        if os.path.isfile(path):
            msg.attach(_build_attachment(path))
            attached += 1

    if attached == 0:
        logger.warning(f"Нет файлов для {to_email}")
        return False

    try:
        with smtplib.SMTP(smtp_conf["host"], int(smtp_conf["port"]), timeout=30) as srv:
            srv.ehlo(); srv.starttls(); srv.ehlo()
            srv.login(smtp_conf["login"], smtp_conf["password"])
            srv.send_message(msg)
        logger.info(f"✓ → {to_email} ({attached} вложений)")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(f"SMTP: ошибка аутентификации для {to_email}")
        return False
    except Exception as e:
        logger.error(f"SMTP ошибка ({to_email}): {e}")
        return False


def send_reports(file_paths: list, text: str = None, subject: str = None) -> dict:
    conf = cfg.load()
    smtp_conf = {
        "host":      conf.get("smtp_host", ""),
        "port":      conf.get("smtp_port", 587),
        "login":     conf.get("smtp_login", ""),
        "password":  conf.get("smtp_password", ""),
        "from_addr": conf.get("smtp_from", conf.get("smtp_login", "")),
        "from_name": conf.get("smtp_from_name", "AI-ассистент куратора"),
    }

    if not smtp_conf["host"] or not smtp_conf["login"] or not smtp_conf["password"]:
        return {"success": False, "message": "Не заполнены настройки SMTP"}

    default_subj = subject or "Отчёт по успеваемости"
    default_text = text or ("Здравствуйте!\n\nВо вложении — отчёт по успеваемости.\n\n"
                            "С уважением,\nКуратор учебной группы")

    recipients_file = conf.get("recipients_excel_path", "").strip()
    sent_ok = sent_fail = 0
    errors = []

    # ── Режим 1: Excel-файл ──────────────────────────────────────
    if recipients_file and os.path.isfile(recipients_file):
        recipients = load_recipients_from_excel(recipients_file)
        if not recipients:
            return {"success": False, "message": "Файл получателей пуст или не читается"}

        group_report = _is_group_report(file_paths)

        for rec in recipients:
            if group_report:
                # Групповой отчёт — НЕ отправляем родителям, только предупреждение
                logger.warning(
                    f"Групповой отчёт не отправляется родителям. "
                    f"Используйте «отчёт по {rec['student_name'].split()[0]}» "
                    f"для персональной рассылки."
                )
                return {
                    "success": False,
                    "message": (
                        "⚠️ Это групповой отчёт — он содержит данные всех студентов.\n"
                        "Родителям нельзя отправлять данные о чужих детях.\n\n"
                        "Сначала сформируйте индивидуальный отчёт:\n"
                        "• «индивидуальные отчёты за весь период» — создаст файл для каждого студента\n"
                        "• «отчёт по [Фамилия] за N семестр» — отчёт по одному студенту\n\n"
                        "Затем нажмите «Отправить»."
                    )
                }

            # Ищем файлы только по фамилии студента
            files_for = _find_files_for_student(file_paths, rec["student_name"])

            if not files_for:
                logger.warning(
                    f"Файл для {rec['student_name']} не найден "
                    f"среди: {[os.path.basename(f) for f in file_paths]}"
                )
                sent_fail += 1
                errors.append(f"{rec['student_name']} (файл не найден)")
                continue

            body = (
                f"Здравствуйте, {rec['parent_name']}!\n\n"
                f"Во вложении — отчёт об успеваемости вашего ребёнка "
                f"({rec['student_name']}).\n\n"
                f"С уважением,\nКуратор учебной группы"
            )
            subj = f"{default_subj} — {rec['student_name']}"

            ok = _send_one(rec["email"], rec["parent_name"], subj, body,
                           files_for, smtp_conf)
            if ok:
                sent_ok += 1
            else:
                sent_fail += 1
                errors.append(rec["email"])

        total = len(recipients)
        if errors:
            return {"success": sent_ok > 0,
                    "message": f"Отправлено {sent_ok}/{total}. Проблемы: {', '.join(errors)}"}
        return {"success": True, "message": f"✅ Отправлено {sent_ok} из {total} писем"}

    # ── Режим 2: простые адреса ──────────────────────────────────
    raw = conf.get("email_recipients", "")
    simple = [e.strip() for e in raw.split(",") if "@" in e.strip()]
    if not simple:
        return {"success": False,
                "message": "Не указаны получатели. Загрузите Excel-файл или заполните "
                           "поле «Адреса получателей» в Настройках."}

    for email in simple:
        ok = _send_one(email, email, default_subj, default_text, file_paths, smtp_conf)
        if ok: sent_ok += 1
        else:  sent_fail += 1; errors.append(email)

    total = len(simple)
    if errors:
        return {"success": sent_ok > 0,
                "message": f"Отправлено {sent_ok}/{total}. Ошибки: {', '.join(errors)}"}
    return {"success": True, "message": f"✅ Отправлено {sent_ok} из {total} писем"}


def test_email_connection(host, port, login, password) -> dict:
    try:
        with smtplib.SMTP(host, int(port), timeout=10) as srv:
            srv.ehlo(); srv.starttls(); srv.ehlo()
            srv.login(login, password)
        return {"success": True, "message": "SMTP подключение успешно"}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "message": "Неверный логин или пароль"}
    except Exception as e:
        return {"success": False, "message": str(e)}