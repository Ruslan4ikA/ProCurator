"""Планировщик автоматической рассылки."""
import threading, time, sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from logger import logger
import config as cfg

_thread = None
_stop = threading.Event()

def _run():
    DAYS = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6}
    last_run = None
    while not _stop.is_set():
        conf = cfg.load()
        if not conf.get("schedule_enabled", False):
            time.sleep(60); continue
        now = datetime.now()
        td = DAYS.get(conf.get("schedule_day","monday"), 0)
        tt = conf.get("schedule_time","08:00")
        try: th, tm = map(int, tt.split(":")); 
        except: th, tm = 8, 0
        today = now.strftime("%Y-%m-%d")
        if now.weekday() == td and now.hour == th and now.minute == tm and last_run != today:
            last_run = today
            logger.info("=== Плановая задача запущена ===")
            try:
                from modules.scraper import login_and_get_html_from_config, parse_grade_data
                from modules.reports import report_debtors
                from modules.sender import send_reports
                html = login_and_get_html_from_config()
                df, gn = parse_grade_data(html)
                files = report_debtors(df, gn)
                if files: send_reports(files, "📊 Плановый отчёт по должникам")
            except Exception as e:
                logger.error(f"Ошибка плановой задачи: {e}")
        time.sleep(60)

def start():
    global _thread
    if _thread and _thread.is_alive(): return
    _stop.clear()
    _thread = threading.Thread(target=_run, daemon=True, name="Scheduler")
    _thread.start()
    logger.info("Планировщик запущен")

def stop():
    _stop.set()

def get_status() -> dict:
    conf = cfg.load()
    return {"enabled": conf.get("schedule_enabled",False),
            "day": conf.get("schedule_day","monday"),
            "time": conf.get("schedule_time","08:00"),
            "running": bool(_thread and _thread.is_alive())}
