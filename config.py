"""Модуль конфигурации — загрузка и сохранение настроек из JSON."""
import json, os
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "settings.json"

DEFAULT_CONFIG = {
    "portal_url": "https://newlms.magtu.ru/login/index.php",
    "portal_grades_url": "https://newlms.magtu.ru/report/magtu_cabinet_for_curator/index.php?gradebook=4618",
    "portal_login": "",
    "portal_password": "",   # хранится в зашифрованном виде (Fernet)
    "headless_mode": True,
    "group_id": "4618",

    # Тестовый режим — читать HTML с диска вместо захода на портал
    "test_mode": False,
    "test_html_path": "",
    "smtp_host": "smtp.mail.ru",
    "smtp_port": 587,
    "smtp_login": "",
    "smtp_password": "",
    "smtp_from": "",
    "email_recipients": "",
    "ollama_url": "http://localhost:11434/api/chat",
    "ollama_model": "llama3",
    "schedule_enabled": False,
    "schedule_day": "monday",
    "schedule_time": "08:00",
    "report_dir": "reports",
}

def load() -> dict:
    if not CONFIG_FILE.exists():
        save(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            stored = json.load(f)
        merged = DEFAULT_CONFIG.copy()
        merged.update(stored)
        return merged
    except Exception:
        return DEFAULT_CONFIG.copy()

def save(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get(key: str, default=None):
    return load().get(key, default)
