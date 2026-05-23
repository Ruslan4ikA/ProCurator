"""AI-модуль — Intent Detection через Ollama или rule-based парсер."""
import json, re, sys, requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from logger import logger
import config as cfg


def parse_intent(user_message: str) -> dict:
    conf = cfg.load()
    base_url = conf.get("ollama_url", "http://localhost:11434")
    base_url = base_url.replace("/api/chat", "").replace("/api/generate", "").rstrip("/")
    model = conf.get("ollama_model", "llama3")

    logger.info(f"AI: обработка запроса: '{user_message}'")

    try:
        prompt = (
            'Ты диспетчер команд куратора. Верни ТОЛЬКО JSON, без пояснений.\n'
            'Команды:\n'
            '  report_debtors     — должники, params: {"num_sem": <число>}\n'
            '  report_full_period — весь период группы, params: {"individual": true/false}\n'
            '  report_by_semester — за семестр по группе, params: {"semester_number": <число>, "individual": true/false}\n'
            '  report_student     — отчёт по конкретному студенту, params: {"student_name": "<фамилия или имя>", "num_sem": <число или null>}\n'
            '  send_reports       — отправить отчёты, params: {}\n'
            '  get_stats          — статистика по группе, params: {}\n\n'
            f'Запрос: "{user_message}"\n\n'
            'Примеры:\n'
            '"должники за 6 семестр" → {"function":"report_debtors","params":{"num_sem":6}}\n'
            '"отчёт по Иванову за 5 семестр" → {"function":"report_student","params":{"student_name":"Иванов","num_sem":5}}\n'
            '"отчёт по Петрову" → {"function":"report_student","params":{"student_name":"Петров","num_sem":null}}\n'
            '"индивидуальные отчёты" → {"function":"report_full_period","params":{"individual":true}}\n'
            '"полный отчёт" → {"function":"report_full_period","params":{"individual":false}}\n\n'
            'JSON:'
        )

        resp = requests.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.1, "num_predict": 80}},
            timeout=30
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        m = re.search(r"\{.*?\}", raw, re.DOTALL)
        if m:
            result = json.loads(m.group())
            if "function" in result:
                logger.info(f"AI (Ollama): {result}")
                return result

    except requests.ConnectionError:
        logger.warning("Ollama недоступна, используется rule-based парсинг")
    except Exception as e:
        logger.error(f"Ошибка AI: {e}")

    return _rule_based(user_message)


# Предлоги и слова перед фамилией, которые не являются именем студента
_STOP_WORDS = {
    "отчет", "отчёт", "ведомость", "напиши", "сделай", "покажи",
    "дай", "хочу", "нужен", "нужно", "мне", "по", "для", "за",
    "студента", "студенту", "студент", "обучающегося", "академическ",
    "весь", "период", "полный", "общий", "сводный", "индивидуальный",
    "семестр", "семестра", "группе", "группу", "группа",
}


def _extract_student_name(text: str) -> str | None:
    """Извлекает фамилию/имя студента из запроса."""
    # Ищем слова с заглавной буквы, которые не являются стоп-словами
    words = text.split()
    candidates = []
    for w in words:
        clean = re.sub(r"[^а-яёА-ЯЁ\-]", "", w)
        if clean and clean[0].isupper() and clean.lower() not in _STOP_WORDS and len(clean) > 2:
            candidates.append(clean)
    return candidates[0] if candidates else None


def _rule_based(text: str) -> dict:
    t = text.lower()

    # Индивидуальный флаг
    individual = any(w in t for w in [
        "индивид", "каждого", "каждому", "каждый",
        "по студент", "отдельно", "персональн"
    ])

    # Номер семестра
    m = re.search(r"(\d+)\s*сем", t)
    num = int(m.group(1)) if m else None

    # Имя студента (с заглавной буквы в оригинальном тексте)
    student_name = _extract_student_name(text)

    # Отправка
    if any(w in t for w in ["отправ", "разосл", "рассыл", "выслать", "послать"]):
        return {"function": "send_reports", "params": {}}

    # Статистика
    if any(w in t for w in ["статистик", "сводк", "картин", "как дела", "итог", "средний балл"]):
        return {"function": "get_stats", "params": {}}

    # Должники
    if any(w in t for w in ["должн", "задолж", "задолженн", "не сдал", "завалил"]):
        return {"function": "report_debtors",
                "params": {"num_sem": num if num else 6}}

    # Отчёт по конкретному студенту — если есть имя с заглавной буквы
    if student_name:
        return {"function": "report_student",
                "params": {"student_name": student_name, "num_sem": num}}

    # Отчёт за конкретный семестр (если указан номер)
    if num and any(w in t for w in ["отчёт", "отчет", "ведомость", "успевае", "семестр", "за"]):
        return {"function": "report_by_semester",
                "params": {"semester_number": num, "individual": individual}}

    # Индивидуальные отчёты без семестра
    if individual:
        return {"function": "report_full_period", "params": {"individual": True}}

    # Полный отчёт
    if any(w in t for w in ["весь", "период", "полн", "сводн", "общ", "все"]):
        return {"function": "report_full_period", "params": {"individual": False}}

    if any(w in t for w in ["отчёт", "отчет", "ведомость"]):
        return {"function": "report_full_period", "params": {"individual": False}}

    return {"function": "unknown", "params": {}}


def check_ollama_status() -> dict:
    conf = cfg.load()
    base = conf.get("ollama_url", "http://localhost:11434")
    base = base.replace("/api/chat", "").replace("/api/generate", "").rstrip("/")
    try:
        r = requests.get(f"{base}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return {"available": True, "models": models}
    except Exception:
        pass
    return {"available": False, "models": []}