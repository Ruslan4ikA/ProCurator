"""AI-модуль — Intent Detection через Ollama или rule-based парсер."""
import json, re, sys, requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from logger import logger
import config as cfg

FUNCTIONS = {
    "report_debtors": {"desc": "Отчёт по должникам", "examples": ["должники","задолж","задолженн"]},
    "report_full_period": {"desc": "Полный отчёт за весь период", "examples": ["весь","период","полн","сводн"]},
    "report_by_semester": {"desc": "Отчёт за конкретный семестр", "examples": ["отчёт","ведомость","семестр"]},
    "send_reports": {"desc": "Отправить отчёты", "examples": ["отправ","разосл"]},
    "get_stats": {"desc": "Статистика по группе", "examples": ["статистик","сводк","картин"]},
}

def parse_intent(user_message: str) -> dict:
    conf = cfg.load()
    url = conf.get("ollama_url","http://localhost:11434/api/chat")
    model = conf.get("ollama_model","llama3")
    logger.info(f"AI: обработка запроса: '{user_message}'")
    try:
        fdesc = json.dumps({k: v["desc"] for k,v in FUNCTIONS.items()}, ensure_ascii=False)
        prompt = (f'Ты ассистент куратора. Команды: {fdesc}\n'
                  f'Запрос: "{user_message}"\n'
                  f'Ответь ТОЛЬКО JSON: {{"function":"<имя>","params":{{<параметры>}}}}\n'
                  f'Если семестр упомянут — добавь "num_sem":<число>. Если непонятно — "unknown".')
        resp = requests.post(url, json={"model":model,"messages":[{"role":"user","content":prompt}],
                                         "stream":False,"options":{"temperature":0.1}}, timeout=30)
        resp.raise_for_status()
        raw = resp.json()["message"]["content"].strip()
        raw = re.sub(r"```(?:json)?","",raw).strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            result = json.loads(m.group())
            logger.info(f"AI: {result}")
            return result
    except requests.ConnectionError:
        logger.warning("Ollama недоступен, используется rule-based парсинг")
    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
    return _rule_based(user_message)

def _rule_based(text: str) -> dict:
    t = text.lower()
    if any(w in t for w in ["отправ","разосл","рассыл"]): return {"function":"send_reports","params":{}}
    if any(w in t for w in ["статистик","сводк","картин","как дела"]): return {"function":"get_stats","params":{}}
    m = re.search(r"(\d+)\s*сем", t)
    num = int(m.group(1)) if m else None
    if any(w in t for w in ["должн","задолж","задолженн"]):
        return {"function":"report_debtors","params":{"num_sem":num} if num else {}}
    if num and any(w in t for w in ["отчёт","отчет","ведомость","успевае"]):
        return {"function":"report_by_semester","params":{"semester_number":num}}
    if any(w in t for w in ["весь","период","полн","сводн","общ"]):
        return {"function":"report_full_period","params":{"individual":"индивидуальн" in t or "каждого" in t}}
    if any(w in t for w in ["отчёт","отчет","ведомость"]):
        return {"function":"report_full_period","params":{"individual":False}}
    return {"function":"unknown","params":{}}

def check_ollama_status() -> dict:
    conf = cfg.load()
    base = conf.get("ollama_url","http://localhost:11434/api/chat").replace("/api/chat","")
    try:
        r = requests.get(f"{base}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models",[])]
            return {"available": True, "models": models}
    except Exception:
        pass
    return {"available": False, "models": []}
