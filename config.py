"""Модуль конфигурации — загрузка и сохранение настроек из JSON с шифрованием."""
import json, os
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "settings.json"

DEFAULT_CONFIG = {
    "portal_url": "https://newlms.magtu.ru/login/index.php",
    "portal_grades_url": "https://newlms.magtu.ru/report/magtu_cabinet_for_curator/index.php?gradebook=4618",
    "portal_login": "",
    "portal_password": "",
    "headless_mode": True,
    "group_id": "4618",
    "test_mode": False,
    "test_html_path": "",
    "smtp_host": "smtp.mail.ru",
    "smtp_port": 587,
    "smtp_login": "",
    "smtp_password": "",
    "smtp_from": "",
    "smtp_from_name": "AI-ассистент куратора",
    "email_recipients": "",
    "recipients_excel_path": "",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama3",
    "use_ollama": True,
    "schedule_enabled": False,
    "schedule_day": "monday",
    "schedule_time": "08:00",
    "report_dir": "reports",
}

def _get_sm():
    """Ленивый импорт SecurityManager — избегаем циклических зависимостей."""
    from modules.security import SecurityManager
    return SecurityManager()


def load() -> dict:
    """
    Загружает конфиг из settings.json и расшифровывает чувствительные поля.
    Возвращает словарь с ОТКРЫТЫМИ (расшифрованными) значениями.
    """
    if not CONFIG_FILE.exists():
        save(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            stored = json.load(f)
        merged = DEFAULT_CONFIG.copy()
        merged.update(stored)
        # Расшифровываем чувствительные поля
        try:
            merged = _get_sm().decrypt_config(merged)
        except Exception:
            pass  # если ключ недоступен — работаем с тем что есть
        return merged
    except Exception:
        return DEFAULT_CONFIG.copy()


def save(cfg: dict) -> None:
    """
    Сохраняет конфиг в settings.json, шифруя чувствительные поля.
    Принимает словарь с ОТКРЫТЫМИ значениями — шифрует сам.
    """
    try:
        to_save = _get_sm().encrypt_config(cfg)
    except Exception:
        to_save = cfg  # если SecurityManager недоступен — сохраняем как есть
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)


def get(key: str, default=None):
    return load().get(key, default)