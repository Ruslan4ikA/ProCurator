import os
import smtplib
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import time
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_log.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class EmailSender:
    """Модуль рассылки писем родителям студентов"""
    
    def __init__(self, smtp_server, smtp_port, sender_email, sender_password):
        """
        Инициализация отправителя писем
        
        Параметры:
            smtp_server: SMTP-сервер (например, 'smtp.yandex.ru')
            smtp_port: Порт (587 для TLS, 465 для SSL)
            sender_email: Email отправителя
            sender_password: Пароль/токен для авторизации
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.sent_log = []  # Журнал отправленных писем
        
    def create_email_template(self, parent_name, student_name):
        """
        Создание шаблона письма для родителя
        
        Параметры:
            parent_name: ФИО родителя
            student_name: ФИО студента
            
        Возвращает:
            Строка с текстом письма в формате HTML
        """
        template = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <div style="max-width: 800px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Уважаемый(ая) {parent_name}!</h2>
                
                <p>Направляю вам отчет об успеваемости вашего ребенка <strong>{student_name}</strong>.</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Что включено в отчет:</h3>
                    <ul>
                        <li>Текущие оценки по всем дисциплинам</li>
                        <li>Данные по семестрам</li>
                        <li>Информация об академических задолженностях (если есть)</li>
                    </ul>
                </div>
                
                <p><strong>Важно:</strong> Если у вашего ребенка есть академические задолженности, 
                просим обратить на это внимание и помочь студенту в их ликвидации.</p>
                
                <p>При возникновении вопросов вы можете связаться со мной по указанному адресу электронной почты.</p>
                
                <hr style="margin: 30px 0;">
                
                <div style="background-color: #e8f4fd; padding: 15px; border-radius: 5px;">
                    <p style="margin: 0; font-size: 12px; color: #666;">
                        <strong>Куратор учебной группы</strong><br>
                        {self.sender_email}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        return template
    
    def create_debtor_email_template(self, parent_name, student_name, debts_info):
        """
        Создание шаблона письма для родителей должников
        
        Параметры:
            parent_name: ФИО родителя
            student_name: ФИО студента
            debts_info: Информация о долгах (список дисциплин)
            
        Возвращает:
            Строка с текстом письма в формате HTML
        """
        debts_list = '<ul>' + ''.join([f'<li>{debt}</li>' for debt in debts_info]) + '</ul>'
        
        template = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <div style="max-width: 800px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #dc3545;">Уважаемый(ая) {parent_name}!</h2>
                
                <div style="background-color: #fff3cd; border: 2px solid #ffc107; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #856404; margin-top: 0;">⚠️ ВНИМАНИЕ: Академические задолженности</h3>
                    <p style="color: #856404; margin-bottom: 0;">
                        У вашего ребенка <strong>{student_name}</strong> обнаружены следующие академические задолженности:
                    </p>
                    {debts_list}
                </div>
                
                <p><strong>Рекомендуется:</strong></p>
                <ol>
                    <li>Обсудить с ребенком причины возникновения задолженностей</li>
                    <li>Помочь организовать дополнительную подготовку</li>
                    <li>Связаться с преподавателями для уточнения условий ликвидации долгов</li>
                </ol>
                
                <p>В приложении вы найдете подробный отчет об успеваемости вашего ребенка.</p>
                
                <p>При возникновении вопросов вы можете связаться со мной по указанному адресу электронной почты.</p>
                
                <hr style="margin: 30px 0;">
                
                <div style="background-color: #e8f4fd; padding: 15px; border-radius: 5px;">
                    <p style="margin: 0; font-size: 12px; color: #666;">
                        <strong>Куратор учебной группы</strong><br>
                        {self.sender_email}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        return template
    
    def send_email(self, recipient_email, subject, body_html, attachments=None, max_retries=3):
        """
        Отправка одного письма с вложениями
        
        Параметры:
            recipient_email: Email получателя
            subject: Тема письма
            body_html: Тело письма в HTML
            attachments: Список путей к файлам-вложениям
            max_retries: Максимальное количество попыток отправки
            
        Возвращает:
            dict с результатом отправки
        """
        for attempt in range(max_retries):
            try:
                # Создание сообщения
                msg = MIMEMultipart('alternative')
                msg['From'] = self.sender_email
                msg['To'] = recipient_email
                msg['Subject'] = subject
                msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
                
                # Добавление HTML-тела
                html_part = MIMEText(body_html, 'html', 'utf-8')
                msg.attach(html_part)
                
                # Добавление вложений
                if attachments:
                    for filepath in attachments:
                        if os.path.exists(filepath):
                            with open(filepath, 'rb') as file:
                                part = MIMEBase('application', 'octet-stream')
                                part.set_payload(file.read())
                            
                            encoders.encode_base64(part)
                            filename = os.path.basename(filepath)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename="{filename}"'
                            )
                            msg.attach(part)
                
                # Отправка письма
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.sender_email, self.sender_password)
                    server.send_message(msg)
                
                # Запись в журнал
                log_entry = {
                    'recipient': recipient_email,
                    'subject': subject,
                    'sent_time': datetime.now(),
                    'status': 'успешно',
                    'attempt': attempt + 1,
                    'attachments': attachments if attachments else []
                }
                self.sent_log.append(log_entry)
                logging.info(f"Письмо успешно отправлено на {recipient_email} (попытка {attempt + 1})")
                
                return {'success': True, 'attempt': attempt + 1}
                
            except Exception as e:
                logging.error(f"Ошибка при отправке на {recipient_email} (попытка {attempt + 1}): {str(e)}")
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Экспоненциальная задержка
                    logging.info(f"Повторная попытка через {wait_time} секунд...")
                    time.sleep(wait_time)
                else:
                    log_entry = {
                        'recipient': recipient_email,
                        'subject': subject,
                        'sent_time': datetime.now(),
                        'status': f'ошибка: {str(e)}',
                        'attempt': attempt + 1,
                        'attachments': attachments if attachments else []
                    }
                    self.sent_log.append(log_entry)
                    return {'success': False, 'error': str(e), 'attempt': attempt + 1}
    
    def send_mass_email(self, contacts_file, reports_dir, is_debtor_report=False):
        """
        Массовая рассылка писем родителям
        
        Параметры:
            contacts_file: Путь к Excel-файлу с контактами родителей
            reports_dir: Директория с отчетами студентов
            is_debtor_report: Флаг для отправки специального письма должникам
            
        Структура contacts_file:
            - ФИО_родителя
            - email
            - ребенок (ФИО студента)
        """
        try:
            # Чтение таблицы контактов
            contacts_df = pd.read_excel(contacts_file)
            
            required_columns = ['ФИО_родителя', 'email', 'ребенок']
            if not all(col in contacts_df.columns for col in required_columns):
                raise ValueError(f"В файле должны быть столбцы: {', '.join(required_columns)}")
            
            total_sent = 0
            total_failed = 0
            
            print(f"Начинаю рассылку {len(contacts_df)} писем...")
            print("=" * 60)
            
            for idx, row in contacts_df.iterrows():
                parent_name = str(row['ФИО_родителя']).strip()
                recipient_email = str(row['email']).strip()
                student_name = str(row['ребенок']).strip()
                
                print(f"\n[{idx + 1}/{len(contacts_df)}] Обрабатываю: {parent_name} ({recipient_email})")
                
                # Поиск отчетов для студента
                student_reports = []
                
                # Поиск файлов в формате: ФИО_студента_*.xlsx и ФИО_студента_*.pdf
                for ext in ['xlsx', 'pdf']:
                    # Простой поиск по имени
                    search_pattern = f"{student_name}*.{ext}"
                    import glob
                    found_files = glob.glob(os.path.join(reports_dir, search_pattern))
                    
                    # Если не нашли, пробуем другие варианты имени
                    if not found_files:
                        # Убираем инициалы, оставляем только фамилию
                        surname = student_name.split()[0] if student_name.split() else student_name
                        search_pattern = f"{surname}*.{ext}"
                        found_files = glob.glob(os.path.join(reports_dir, search_pattern))
                    
                    student_reports.extend(found_files)
                
                if not student_reports:
                    logging.warning(f"Не найдены отчеты для студента: {student_name}")
                    print(f"  ⚠️  Отчеты не найдены для {student_name}")
                    continue
                
                print(f"  ✓ Найдено {len(student_reports)} файлов для прикрепления")
                
                # Создание темы письма
                if is_debtor_report:
                    subject = f"⚠️ Академические задолженности - {student_name}"
                else:
                    subject = f"Отчет об успеваемости - {student_name}"
                
                # Создание тела письма
                if is_debtor_report:
                    # Для должников - специальный шаблон
                    # Здесь можно добавить информацию о долгах из отчета
                    body = self.create_debtor_email_template(
                        parent_name, 
                        student_name, 
                        ["Необходимо уточнить информацию в приложенном отчете"]
                    )
                else:
                    body = self.create_email_template(parent_name, student_name)
                
                # Отправка письма
                result = self.send_email(
                    recipient_email=recipient_email,
                    subject=subject,
                    body_html=body,
                    attachments=student_reports
                )
                
                if result['success']:
                    total_sent += 1
                    print(f"  ✓ Отправлено успешно (попытка {result['attempt']})")
                else:
                    total_failed += 1
                    print(f"  ✗ Ошибка: {result['error']}")
                
                # Задержка между отправками для избежания блокировки
                time.sleep(2)
            
            print("\n" + "=" * 60)
            print(f"Рассылка завершена!")
            print(f"Успешно отправлено: {total_sent}")
            print(f"Не удалось отправить: {total_failed}")
            
            # Сохранение журнала отправки
            self.save_sent_log(reports_dir)
            
            return {'total_sent': total_sent, 'total_failed': total_failed}
            
        except Exception as e:
            logging.error(f"Ошибка при массовой рассылке: {str(e)}")
            raise
    
    def save_sent_log(self, output_dir):
        """
        Сохранение журнала отправленных писем в Excel
        
        Параметры:
            output_dir: Директория для сохранения журнала
        """
        try:
            if not self.sent_log:
                logging.info("Журнал отправки пуст")
                return
            
            log_df = pd.DataFrame(self.sent_log)
            
            # Форматирование даты для имени файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(output_dir, f"журнал_отправки_{timestamp}.xlsx")
            
            log_df.to_excel(log_file, index=False, engine='openpyxl')
            
            # Автоформатирование ширины столбцов
            from openpyxl import load_workbook
            wb = load_workbook(log_file)
            ws = wb.active
            
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            wb.save(log_file)
            
            logging.info(f"Журнал отправки сохранен: {log_file}")
            print(f"\nЖурнал отправки сохранен: {log_file}")
            
        except Exception as e:
            logging.error(f"Ошибка при сохранении журнала: {str(e)}")
            raise
    
    def get_statistics(self):
        """
        Получение статистики по отправленным письмам
        
        Возвращает:
            dict со статистикой
        """
        total = len(self.sent_log)
        successful = sum(1 for entry in self.sent_log if entry['status'] == 'успешно')
        failed = total - successful
        
        return {
            'total_sent': total,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / total * 100) if total > 0 else 0
        }


# Пример использования модуля
def example_usage():
    """Пример использования модуля рассылки"""
    
    # Настройки SMTP (пример для Яндекса)
    SMTP_SERVER = 'smtp.yandex.ru'
    SMTP_PORT = 587
    SENDER_EMAIL = 'your_email@yandex.ru'
    SENDER_PASSWORD = 'your_app_password'  # Использовать пароль приложения!
    
    # Инициализация отправителя
    email_sender = EmailSender(
        smtp_server=SMTP_SERVER,
        smtp_port=SMTP_PORT,
        sender_email=SENDER_EMAIL,
        sender_password=SENDER_PASSWORD
    )
    
    # Файл с контактами родителей
    contacts_file = 'родители_контакты.xlsx'
    
    # Директория с отчетами
    reports_dir = 'Report/АПИб-22-3/Весь период'
    
    # Массовая рассылка
    result = email_sender.send_mass_email(
        contacts_file=contacts_file,
        reports_dir=reports_dir,
        is_debtor_report=False  # True для должников
    )
    
    # Получение статистики
    stats = email_sender.get_statistics()
    print(f"\nСтатистика отправки:")
    print(f"  Всего отправлено: {stats['total_sent']}")
    print(f"  Успешно: {stats['successful']}")
    print(f"  Неудачно: {stats['failed']}")
    print(f"  Процент успеха: {stats['success_rate']:.1f}%")


# Создание примера файла с контактами родителей
def create_sample_contacts_file(filename='родители_контакты.xlsx'):
    """Создание примера файла с контактами родителей"""
    
    sample_data = {
        'ФИО_родителя': [
            'Иванов Иван Иванович',
            'Петрова Мария Сергеевна',
            'Сидоров Алексей Владимирович',
            'Козлова Елена Петровна',
            'Смирнов Дмитрий Андреевич'
        ],
        'email': [
            'ivanov.parent@example.com',
            'petrova.m@example.com',
            'sidorov.a@example.com',
            'kozlova.e@example.com',
            'smirnov.d@example.com'
        ],
        'ребенок': [
            'Иванов Иван Иванович',
            'Петрова Дарья Викторовна',
            'Сидоров Алексей Алексеевич',
            'Козлов Дмитрий Афанасьевич',
            'Смирнов Костян Дмитриевич'
        ]
    }
    
    df = pd.DataFrame(sample_data)
    df.to_excel(filename, index=False, engine='openpyxl')
    
    print(f"Пример файла контактов создан: {filename}")
    print("\nСтруктура файла:")
    print(df.to_string(index=False))


if __name__ == "__main__":
    # Создание примера файла контактов
    create_sample_contacts_file()
    
    print("\n" + "=" * 60)
    print("Модуль рассылки готов к использованию!")
    print("=" * 60)
    print("\nДля использования модуля:")
    print("1. Заполните файл 'родители_контакты.xlsx' актуальными данными")
    print("2. Настройте параметры SMTP в функции example_usage()")
    print("3. Укажите правильный путь к директории с отчетами")
    print("4. Запустите рассылку")