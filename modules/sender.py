"""Модуль рассылки — отправка отчётов по email через SMTP."""
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


def _build_attachment(filepath: str) -> MIMEBase:
    """
    Создаёт MIME-вложение с корректным MIME-типом и именем файла,
    поддерживающим кириллицу.
    """
    filename = os.path.basename(filepath)

    # Определяем MIME-тип по расширению
    ctype, encoding = mimetypes.guess_type(filepath)
    if ctype is None or encoding is not None:
        ctype = 'application/octet-stream'

    maintype, subtype = ctype.split('/', 1)

    with open(filepath, 'rb') as f:
        part = MIMEBase(maintype, subtype)
        part.set_payload(f.read())

    encoders.encode_base64(part)

    # КРИТИЧЕСКИ ВАЖНО для кириллицы:
    # 1. Content-Disposition с RFC 2231 кодированием через add_header(filename=(...))
    # 2. Content-Type с тем же кодированным именем (для совместимости с разными клиентами)
    part.add_header(
        'Content-Disposition',
        'attachment',
        filename=('utf-8', '', filename)
    )
    # Дополнительный параметр name для Content-Type (нужно для некоторых клиентов)
    part.set_param('name', filename, header='Content-Type', charset='utf-8')

    return part


def send_via_email(file_paths, text, recipients=None, subject=None):
    conf = cfg.load()
    host = conf.get("smtp_host", "")
    port = int(conf.get("smtp_port", 587))
    login = conf.get("smtp_login", "")
    password = conf.get("smtp_password", "")
    from_addr = conf.get("smtp_from", login) or login
    from_name = conf.get("smtp_from_name", "AI-ассистент куратора")

    if recipients is None:
        recipients = [r.strip() for r in conf.get("email_recipients", "").split(",") if r.strip()]

    if not host or not login or not password:
        return {"success": False, "message": "Не заполнены настройки SMTP"}
    if not recipients:
        return {"success": False, "message": "Не указаны получатели"}

    if subject is None:
        subject = "Отчёт по успеваемости группы"

    try:
        # MIMEMultipart('mixed') — для писем с вложениями (а не 'alternative')
        msg = MIMEMultipart('mixed')

        # Заголовки с поддержкой кириллицы через formataddr + Header
        msg['From'] = formataddr((str(Header(from_name, 'utf-8')), from_addr))
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = Header(subject, 'utf-8')

        # Тело письма
        msg.attach(MIMEText(text, 'plain', 'utf-8'))

        # Вложения
        attached_count = 0
        for path in file_paths:
            if not os.path.exists(path):
                logger.warning(f"Файл не найден, пропуск: {path}")
                continue
            try:
                part = _build_attachment(path)
                msg.attach(part)
                attached_count += 1
                logger.info(f"Прикреплён файл: {os.path.basename(path)}")
            except Exception as e:
                logger.error(f"Не удалось прикрепить файл {path}: {e}")

        if attached_count == 0:
            return {"success": False, "message": "Нет файлов для прикрепления"}

        # Отправка через send_message (корректно кодирует все заголовки автоматически)
        with smtplib.SMTP(host, port, timeout=30) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(login, password)
            srv.send_message(msg)

        logger.info(f"Письмо отправлено: {', '.join(recipients)} ({attached_count} вложений)")
        return {
            "success": True,
            "message": f"Отправлено на {', '.join(recipients)} ({attached_count} вложений)"
        }

    except smtplib.SMTPAuthenticationError:
        return {"success": False, "message": "Ошибка SMTP: неверный логин или пароль приложения"}
    except smtplib.SMTPException as e:
        logger.error(f"SMTP ошибка: {e}")
        return {"success": False, "message": f"SMTP ошибка: {e}"}
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}", exc_info=True)
        return {"success": False, "message": str(e)}


def send_reports(file_paths, text=None, subject=None):
    if text is None:
        text = ("Здравствуйте!\n\n"
                "Во вложении — отчёт по успеваемости группы, сформированный AI-ассистентом куратора.\n\n"
                "С уважением,\nКуратор учебной группы")
    return send_via_email(file_paths, text, subject=subject)


def test_email_connection(host, port, login, password):
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