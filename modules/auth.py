"""
Модуль авторизации в образовательный портал
"""
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from config import HEADLESS_MODE, PORTAL_URL
from modules.security import SecurityManager
import logging
import time

logger = logging.getLogger(__name__)


class PortalAuth:
    """Авторизация в образовательном портале"""
    
    def __init__(self):
        self.driver = None
        self.security = SecurityManager()
        self.credentials_file = None
    
    def setup_driver(self):
        """Настройка веб-драйвера для Chromium в Docker"""
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        chrome_options = Options()
        
        if HEADLESS_MODE:
            chrome_options.add_argument('--headless=new')  # Новый режим headless
        
        # Обязательные аргументы для работы в Docker
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--no-default-browser-check')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        # Маскировка Selenium
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Указываем путь к бинарнику Chromium (стандартный для Debian)
        chrome_options.binary_location = '/usr/bin/chromium'
        
        # Используем системный chromedriver
        service = Service(executable_path='/usr/bin/chromedriver')
        
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Дополнительная маскировка от детектирования
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        logger.info("WebDriver настроен для Chromium в Docker")
    
    def load_credentials(self, credentials_file):
        """Загрузка учетных данных"""
        self.credentials_file = credentials_file
        username, password = self.security.load_credentials(credentials_file)
        logger.info("Учетные данные загружены")
        return username, password
    
    def login(self, username: str, password: str) -> bool:
        """
        Выполнение входа в портал
        
        Возвращает:
            True если вход успешен, иначе False
        """
        try:
            if not self.driver:
                self.setup_driver()
            
            logger.info(f"Переход на портал: {PORTAL_URL}")
            self.driver.get(PORTAL_URL)
            time.sleep(2)
            
            # Ожидание и заполнение формы входа
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, 'username'))
            )
            password_field = self.driver.find_element(By.ID, 'password')
            
            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            
            # Нажатие кнопки входа
            login_button = self.driver.find_element(By.ID, 'loginbtn')
            login_button.click()
            
            # Ожидание успешного входа
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'usermenu'))
            )
            
            logger.info("Успешный вход в портал")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при входе в портал: {str(e)}")
            return False
    
    def get_page_source(self) -> str:
        """Получение HTML-кода текущей страницы"""
        if self.driver:
            return self.driver.page_source
        return ""
    
    def navigate_to_curator_cabinet(self, group_name: str) -> bool:
        """Переход в кабинет куратора для выбранной группы"""
        try:
            # Логика навигации к кабинету куратора
            # Это зависит от структуры вашего портала
            logger.info(f"Переход в кабинет куратора группы: {group_name}")
            
            # Пример (адаптировать под ваш портал):
            # curator_link = self.driver.find_element(By.LINK_TEXT, 'Кабинет куратора')
            # curator_link.click()
            
            time.sleep(2)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при переходе в кабинет куратора: {str(e)}")
            return False
    
    def close(self):
        """Закрытие браузера"""
        if self.driver:
            self.driver.quit()
            logger.info("Браузер закрыт")