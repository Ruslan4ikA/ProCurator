"""Flask-сервер AI-ассистента куратора."""
import os, sys, threading
from pathlib import Path
from flask import Flask, request, jsonify, render_template

sys.path.insert(0, str(Path(__file__).parent))
from logger import logger, get_recent_logs
import config as cfg
import scheduler

app = Flask(__name__)
_last_reports: list = []
_last_df = None
_last_group = None


def _collect_data():
    """Сбор данных с портала через ProCurator-код."""
    global _last_df, _last_group
    from modules.scraper import login_and_get_html_from_config
    from modules.analytics import parse_grade_data
    html = login_and_get_html_from_config()
    _last_df, _last_group = parse_grade_data(html)
    return _last_df, _last_group


def _execute_command(intent: dict) -> str:
    global _last_reports, _last_df, _last_group
    func = intent.get("function", "unknown")
    params = intent.get("params", {})

    if func == "get_stats":
        if _last_df is None:
            return "⚠️ Данные ещё не загружены. Сначала сформируйте любой отчёт."
        from modules.analytics import get_summary_stats
        s = get_summary_stats(_last_df)
        return (f"📊 Группа **{_last_group}**:\n"
                f"• Студентов: {s['total_students']}\n"
                f"• Семестров: {s['semesters_count']}\n"
                f"• Последний семестр: {s['last_semester']}\n"
                f"• Должников (посл. сем.): {s['debtors_count']}\n"
                f"• Средний балл: {s['avg_score']}")

    if func == "send_reports":
        from modules.sender import send_reports
        if not _last_reports:
            return "⚠️ Нет готовых отчётов. Сначала сформируйте отчёт."
        r = send_reports(_last_reports)
        return f"✅ {r['message']}" if r["success"] else f"❌ {r['message']}"

    logger.info("Сбор данных с образовательного портала...")
    try:
        df, group_name = _collect_data()
    except RuntimeError as e:
        return f"❌ {e}"
    except Exception as e:
        logger.error(f"Не удалось собрать данные: {e}")
        return ("❌ Не удалось подключиться к порталу.\n"
                "Проверьте:\n"
                "• Логин и пароль в Настройках\n"
                "• Установлен ли Google Chrome\n"
                "• Доступность портала (интернет)")

    if func == "report_debtors":
        from modules.reports import report_debtors
        n = params.get("num_sem") or params.get("semester_number")
        files = report_debtors(df, group_name, num_sem=int(n) if n else None)
        _last_reports = files
        if not files:
            return f"✅ Данные получены. Должников не найдено."
        return (f"✅ Отчёт по должникам для **{group_name}** готов.\n"
                f"Файлов: {len(files)}. Нажмите «Отправить» для рассылки.")

    elif func == "report_full_period":
        from modules.reports import report_full_period
        files = report_full_period(df, group_name, individual=bool(params.get("individual",False)))
        _last_reports = files
        return (f"✅ Полный отчёт для **{group_name}** готов.\n"
                f"Файлов: {len(files)}. Нажмите «Отправить» для рассылки.")

    elif func == "report_by_semester":
        from modules.reports import report_by_semester
        n = int(params.get("semester_number", 1))
        files = report_by_semester(df, group_name, n)
        _last_reports = files
        return (f"✅ Отчёт за {n} семестр для **{group_name}** готов.\n"
                f"Файлов: {len(files)}. Нажмите «Отправить» для рассылки.")

    return ("❓ Не могу распознать запрос. Попробуйте:\n"
            "• «отчёт по должникам за 6 семестр»\n"
            "• «полный отчёт за весь период»\n"
            "• «отчёт за 5 семестр»\n"
            "• «статистика»\n"
            "• «отправить отчёты»")


# ── Маршруты ──────────────────────────────────────────────

@app.route("/")
def index(): return render_template("index.html")

@app.route("/settings")
def settings_page(): return render_template("settings.html")

@app.route("/logs")
def logs_page(): return render_template("logs.html")

@app.route("/api/chat", methods=["POST"])
def api_chat():
    msg = request.json.get("message","").strip()
    if not msg: return jsonify({"error":"Пустое сообщение"}), 400
    logger.info(f"Чат: получен запрос: '{msg}'")
    from modules.ai_agent import parse_intent
    intent = parse_intent(msg)
    resp = _execute_command(intent)
    return jsonify({"response": resp, "intent": intent, "reports_ready": len(_last_reports) > 0})

@app.route("/api/send", methods=["POST"])
def api_send():
    if not _last_reports:
        return jsonify({"success":False,"message":"Нет готовых отчётов"})
    from modules.sender import send_reports
    return jsonify(send_reports(_last_reports))

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    conf = cfg.load()  # уже расшифрован
    # Маскируем пароли перед отправкой в браузер
    safe = dict(conf)
    for field in ("portal_password", "smtp_password"):
        safe[field] = "●●●●●●" if conf.get(field) else ""
    return jsonify(safe)

@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    data = request.json
    conf = cfg.load()  # загружаем расшифрованный конфиг

    login    = data.get("portal_login", "")
    password = data.get("portal_password", "")

    for key, value in data.items():
        if value == "●●●●●●":
            continue  # не перезаписываем замаскированные поля
        conf[key] = value

    cfg.save(conf)  # сохраняет с шифрованием автоматически

    # Дополнительно обновляем credentials.enc для scraper (обратная совместимость)
    if login and password and password != "●●●●●●":
        try:
            from modules.scraper import save_credentials_from_settings
            save_credentials_from_settings(login, password)
        except Exception as e:
            logger.warning(f"Не удалось сохранить credentials.enc: {e}")

    scheduler.stop()
    scheduler.start()
    logger.info("Настройки сохранены (данные зашифрованы)")
    return jsonify({"success": True, "message": "Настройки сохранены"})

@app.route("/api/test/email", methods=["POST"])
def api_test_email():
    d = request.json
    from modules.sender import test_email_connection
    return jsonify(test_email_connection(d.get("smtp_host",""), d.get("smtp_port",587),
                                         d.get("smtp_login",""), d.get("smtp_password","")))

@app.route("/api/logs")
def api_logs():
    return jsonify(get_recent_logs(request.args.get("n",150,int)))

@app.route("/api/status")
def api_status():
    from modules.ai_agent import check_ollama_status
    conf = cfg.load()
    return jsonify({
        "portal_configured": bool(conf.get("portal_login") and conf.get("portal_password")),
        "email_configured": bool(conf.get("smtp_login") and conf.get("smtp_password")),
        "ollama": check_ollama_status(),
        "scheduler": scheduler.get_status(),
        "reports_ready": len(_last_reports),
        "test_mode": bool(conf.get("test_mode", False)),
    })

@app.route("/api/run_now", methods=["POST"])
def api_run_now():
    def task():
        try:
            global _last_reports
            df, gn = _collect_data()
            from modules.reports import report_debtors
            from modules.sender import send_reports
            files = report_debtors(df, gn)
            _last_reports = files
            if files: send_reports(files, "📊 Плановый отчёт по должникам")
        except Exception as e:
            logger.error(f"Ошибка немедленного запуска: {e}")
    threading.Thread(target=task, daemon=True).start()
    return jsonify({"success":True,"message":"Задача запущена в фоне"})


@app.route("/api/preview_send", methods=["POST"])
def api_preview_send():
    """Превью рассылки для модального окна подтверждения."""
    if not _last_reports:
        return jsonify({
            "success": False, "preview": [], "files": [],
            "message": "Нет готовых отчётов. Сначала сформируйте отчёт."
        })
    from modules.sender import preview_send
    conf = cfg.load()
    recipients_file = conf.get("recipients_excel_path", "").strip()
    preview = preview_send(_last_reports, recipients_file)
    return jsonify({
        "success": True,
        "preview": preview,
        "files": [os.path.basename(f) for f in _last_reports],
        "total": len(preview)
    })


if __name__ == "__main__":
    logger.info("="*50)
    logger.info("Запуск AI-ассистента куратора")
    logger.info("="*50)
    os.makedirs(cfg.get("report_dir","reports"), exist_ok=True)
    scheduler.start()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)