"""
AI-Ассистент для кураторов учебных групп
Точка входа в приложение
"""
import logging
from pathlib import Path
from config import LOGS_DIR, LOG_FORMAT, LOG_LEVEL

# Настройка логирования
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOGS_DIR / 'app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Основная функция приложения"""
    logger.info("=" * 60)
    logger.info("Запуск AI-Ассистента для кураторов")
    logger.info("=" * 60)
    
    try:
        # Импорт модулей
        from modules.auth import PortalAuth
        from modules.parser import GradeParser
        from modules.analyzer import GradeAnalyzer
        from modules.report_generator import ReportGenerator
        from modules.email_sender import EmailSender
        from config import DATA_DIR
        
        # 1. Авторизация в портале
        logger.info("Шаг 1: Авторизация в образовательном портале")
        auth = PortalAuth()
        
        # Загрузка учетных данных (создайте файл с учетными данными)
        credentials_file = DATA_DIR / 'credentials.enc'
        
        if not credentials_file.exists():
            logger.error("Файл с учетными данными не найден!")
            logger.info("Создайте файл с учетными данными с помощью:")
            logger.info("from modules.security import SecurityManager")
            logger.info("sm = SecurityManager()")
            logger.info("sm.save_credentials('username', 'password', Path('data/credentials.enc'))")
            return
        
        username, password = auth.load_credentials(credentials_file)
        
        if auth.login(username, password):
            logger.info("Авторизация успешна")
            
            # 2. Переход в кабинет куратора
            group_name = "АПИб-22-3"  # Укажите вашу группу
            if auth.navigate_to_curator_cabinet(group_name):
                
                # 3. Парсинг данных
                logger.info("Шаг 2: Парсинг данных об успеваемости")
                html_content = auth.get_page_source()
                parser = GradeParser()
                df, parsed_group_name = parser.parse_grade_data(html_content)
                
                logger.info(f"Данные получены: {df.shape[0]} дисциплин, {len(df.columns) - 3} студентов")
                
                # 4. Анализ успеваемости
                logger.info("Шаг 3: Анализ успеваемости")
                analyzer = GradeAnalyzer()
                
                # Общий отчет по группе
                logger.info("Генерация общего отчета по группе")
                generator = ReportGenerator()
                group_report = generator.generate_group_report(df, parsed_group_name)
                
                # Индивидуальные отчеты
                logger.info("Генерация индивидуальных отчетов")
                individual_reports = generator.generate_individual_reports(df, parsed_group_name)
                
                # Отчет по должникам
                logger.info("Генерация отчета по должникам")
                debtors = analyzer.find_debtors(df)
                if debtors:
                    debtors_report = generator.generate_debtors_report(debtors, parsed_group_name)
                    
                    # 5. Рассылка писем (опционально)
                    logger.info("Шаг 4: Рассылка писем родителям")
                    contacts_file = DATA_DIR / 'contacts' / 'родители_контакты.xlsx'
                    
                    if contacts_file.exists():
                        email_sender = EmailSender()
                        result = email_sender.send_mass_email(
                            contacts_file=contacts_file,
                            reports_dir=Path(group_report).parent,
                            is_debtor_report=True
                        )
                        logger.info(f"Результат рассылки: {result}")
                    else:
                        logger.warning(f"Файл контактов не найден: {contacts_file}")
                else:
                    logger.info("Должников не обнаружено")
                
                # Закрытие браузера
                auth.close()
                
                logger.info("=" * 60)
                logger.info("Работа завершена успешно!")
                logger.info("=" * 60)
            else:
                logger.error("Не удалось перейти в кабинет куратора")
                auth.close()
        else:
            logger.error("Ошибка авторизации")
            auth.close()
            
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()