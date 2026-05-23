"""Модуль рассылки — SMTP с поддержкой Excel-файла получателей."""
import os
import sys
import smtplib
import mimetypes
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

# ─────────────────────────────────────────────────────────────────
#  Работа с Excel-файлом получателей
# ─────────────────────────────────────────────────────────────────

def load_recipients_from_excel(filepath: str) -> list[dict]:
    """
    Читает Excel-файл с получателями.

    Ожидаемые колонки (регистр не важен, порядок важен):
      1. ФИО родителя
      2. ФИО ученика
      3. Почта родителя

    Возвращает список словарей:
      [{"parent_name": "...", "student_name": "...", "email": "..."}, ...]
    """
    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas не установлен — установите: pip install pandas openpyxl")
        return []

    if not os.path.isfile(filepath):
        logger.warning(f"Файл получателей не найден: {filepath}")
        return []

    try:
        df = pd.read_excel(filepath, header=0, engine="openpyxl")
        df.columns = df.columns.str.strip()

        # Берём первые три столбца независимо от названия
        if df.shape[1] < 3:
            logger.error(f"Файл получателей: нужно минимум 3 столбца, найдено {df.shape[1]}")
            return []

        col_parent, col_student, col_email = df.columns[0], df.columns[1], df.columns[2]

        recipients = []
        for _, row in df.iterrows():
            parent = str(row[col_parent]).strip()
            student = str(row[col_student]).strip()
            email = str(row[col_email]).strip()

            # Пропускаем пустые строки и заголовки
            if not email or "@" not in email or parent.lower() in ("nan", "фио родителя", ""):
                continue

            recipients.append({
                "parent_name": parent,
                "student_name": student,
                "email": email,
            })

        logger.info(f"Загружено получателей: {len(recipients)} из {filepath}")
        return recipients

    except Exception as e:
        logger.error(f"Ошибка чтения файла получателей: {e}")
        return []


def _match_student(recipient_student: str, file_path: str) -> bool:
    """
    Проверяет — относится ли файл к данному студенту.
    Ищет фамилию студента-получателя в имени файла.
    Сравнение по первому слову (фамилии) из ФИО студента.
    """
    if not recipient_student:
        return True  # если студент не указан — отправляем всем

    filename = os.path.basename(file_path).lower()

    # Берём слова из ФИО — пробуем каждое
    words = [w.strip() for w in recipient_student.replace("_", " ").split() if len(w) > 2]

    for word in words:
        if word.lower() in filename:
            return True

    return False


def _find_files_for_student(all_files: list[str], student_name: str) -> list[str]:
    """
    Из общего списка файлов отбирает те, что относятся к конкретному студенту.
    Если совпадений нет — возвращает все файлы (сводный отчёт).
    """
    matched = [f for f in all_files if _match_student(student_name, f)]
    return matched if matched else all_files


# ─────────────────────────────────────────────────────────────────
#  SMTP — отправка одного письма
# ─────────────────────────────────────────────────────────────────

def _build_attachment(filepath: str) -> MIMEBase:
    """Создаёт MIME-вложение с корректным именем файла (RFC 2231)."""
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


def _send_one(to_email: str, to_name: str, subject: str,
              body: str, file_paths: list[str],
              smtp_conf: dict) -> bool:
    """Отправляет одно письмо. Возвращает True при успехе."""
    host = smtp_conf["host"]
    port = int(smtp_conf["port"])
    login = smtp_conf["login"]
    password = smtp_conf["password"]
    from_addr = smtp_conf.get("from_addr") or login
    from_name = smtp_conf.get("from_name", "AI-ассистент куратора")

    msg = MIMEMultipart("mixed")
    msg["From"] = formataddr((str(Header(from_name, "utf-8")), from_addr))
    msg["To"] = formataddr((str(Header(to_name, "utf-8")), to_email))
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(body, "plain", "utf-8"))

    attached = 0
    for path in file_paths:
        if not os.path.isfile(path):
            logger.warning(f"Файл не найден, пропуск: {path}")
            continue
        msg.attach(_build_attachment(path))
        attached += 1

    if attached == 0:
        logger.warning(f"Нет файлов для отправки {to_email}")
        return False

    try:
        with smtplib.SMTP(host, port, timeout=30) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(login, password)
            srv.send_message(msg)
        logger.info(f"✓ Письмо отправлено → {to_email} ({attached} вложений)")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(f"SMTP: ошибка аутентификации для {to_email}")
        return False
    except Exception as e:
        logger.error(f"SMTP ошибка при отправке на {to_email}: {e}")
        return False


# ─────────────────────────────────────────────────────────────────
#  Публичные функции
# ─────────────────────────────────────────────────────────────────

def send_reports(file_paths: list[str], text: str | None = None,
                 subject: str | None = None) -> dict:
    """
    Отправляет отчёты получателям.

    Если задан Excel-файл получателей:
      - читает список родителей/студентов
      - сопоставляет файлы с нужным студентом
      - отправляет каждому родителю только его файл(ы)

    Если Excel не задан — отправляет всем из поля email_recipients.
    """
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

    default_subject = subject or "Отчёт по успеваемости"
    default_text = text or (
        "Здравствуйте!\n\n"
        "Во вложении — отчёт по успеваемости.\n\n"
        "С уважением,\nКуратор учебной группы"
    )

    recipients_file = conf.get("recipients_excel_path", "").strip()
    sent_ok = 0
    sent_fail = 0
    errors = []

    # ── Режим 1: Excel-файл получателей ──────────────────────────
    if recipients_file and os.path.isfile(recipients_file):
        recipients = load_recipients_from_excel(recipients_file)

        if not recipients:
            return {"success": False,
                    "message": "Файл получателей пуст или не удалось прочитать"}

        for rec in recipients:
            to_email = rec["email"]
            parent_name = rec["parent_name"]
            student_name = rec["student_name"]

            # Подбираем файлы для этого студента
            files_for_student = _find_files_for_student(file_paths, student_name)

            # Персонализируем тело письма
            body = (
                f"Здравствуйте, {parent_name}!\n\n"
                f"Во вложении — отчёт об успеваемости вашего ребёнка "
                f"({student_name}).\n\n"
                f"С уважением,\nКуратор учебной группы"
            )
            subj = f"{default_subject} — {student_name}"

            ok = _send_one(to_email, parent_name, subj, body,
                           files_for_student, smtp_conf)
            if ok:
                sent_ok += 1
            else:
                sent_fail += 1
                errors.append(to_email)

        total = len(recipients)
        if sent_fail == 0:
            return {"success": True,
                    "message": f"Отправлено {sent_ok} из {total} писем"}
        return {"success": sent_ok > 0,
                "message": f"Отправлено {sent_ok} из {total}. "
                           f"Ошибки: {', '.join(errors)}"}

    # ── Режим 2: список email из настроек ────────────────────────
    raw = conf.get("email_recipients", "")
    simple_recipients = [r.strip() for r in raw.split(",") if r.strip() and "@" in r]

    if not simple_recipients:
        return {"success": False,
                "message": "Не указаны получатели. Загрузите Excel-файл "
                           "или заполните поле «Адреса получателей» в Настройках."}

    for email in simple_recipients:
        ok = _send_one(email, email, default_subject, default_text,
                       file_paths, smtp_conf)
        if ok:
            sent_ok += 1
        else:
            sent_fail += 1
            errors.append(email)

    total = len(simple_recipients)
    if sent_fail == 0:
        return {"success": True,
                "message": f"Отправлено {sent_ok} из {total} писем"}
    return {"success": sent_ok > 0,
            "message": f"Отправлено {sent_ok} из {total}. "
                       f"Ошибки: {', '.join(errors)}"}


def test_email_connection(host: str, port, login: str, password: str) -> dict:
    """Проверяет SMTP-подключение без отправки письма."""
    try:
        with smtplib.SMTP(host, int(port), timeout=10) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(login, password)
        return {"success": True, "message": "SMTP подключение успешно"}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "message": "Неверный логин или пароль"}
    except Exception as e:
        return {"success": False, "message": str(e)}