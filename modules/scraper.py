"""
Модуль сбора данных — авторизация на образовательном портале МГТУ.
Скопирован напрямую из ProCurator (github.com/Ruslan4ikA/ProCurator/modules/auth.py)
с минимальной адаптацией: вместо config.py константы берутся из cfg.load().
"""
import time
import sys
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.path.insert(0, str(Path(__file__).parent.parent))
from logger import logger
import config as cfg
from modules.security import SecurityManager

CREDENTIALS_FILE = Path(__file__).parent.parent / 'data' / 'credentials' / 'credentials.enc'
DEBUG_DIR = Path(__file__).parent.parent  # debug html сохраняются в корень проекта


class PortalAuth:
    """Авторизация в образовательном портале МГТУ — точная копия ProCurator/modules/auth.py"""

    def __init__(self):
        self.driver = None
        self.security = SecurityManager()

    def setup_driver(self):
        """Настройка веб-драйвера с несколькими стратегиями запуска"""
        chrome_options = Options()

        conf = cfg.load()
        headless = conf.get('headless_mode', True)

        if headless:
            chrome_options.add_argument('--headless')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--no-default-browser-check')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')

        # Маскировка Selenium — добавляем только если НЕ используем undetected-chromedriver
        # (для обычного Chrome эти опции работают нормально)
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        e1 = e2 = e3 = None

        # Попытка 1: undetected-chromedriver с собственными опциями (без experimental)
        try:
            logger.info("Попытка запуска через undetected-chromedriver...")
            import undetected_chromedriver as uc
            uc_options = uc.ChromeOptions()
            if headless:
                uc_options.add_argument('--headless')
            uc_options.add_argument('--no-sandbox')
            uc_options.add_argument('--disable-dev-shm-usage')
            uc_options.add_argument('--disable-gpu')
            uc_options.add_argument('--window-size=1920,1080')
            uc_options.add_argument('--disable-blink-features=AutomationControlled')
            self.driver = uc.Chrome(options=uc_options)
            logger.info("✓ WebDriver успешно запущен через undetected-chromedriver")
            return
        except Exception as ex1:
            e1 = ex1
            logger.warning(f"undetected-chromedriver не установлен или не работает: {ex1}")

        # Попытка 2: webdriver-manager (без experimental опций — они для Chrome>=115)
        try:
            logger.info("Попытка запуска через webdriver-manager...")
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service

            # Создаём опции без experimental для webdriver-manager
            opts2 = Options()
            if headless:
                opts2.add_argument('--headless')
            opts2.add_argument('--no-sandbox')
            opts2.add_argument('--disable-dev-shm-usage')
            opts2.add_argument('--disable-gpu')
            opts2.add_argument('--window-size=1920,1080')
            opts2.add_argument('--disable-blink-features=AutomationControlled')

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=opts2)
            logger.info("✓ WebDriver успешно запущен через webdriver-manager")
            return
        except Exception as ex2:
            e2 = ex2
            logger.warning(f"webdriver-manager не смог запустить драйвер: {ex2}")

        # Попытка 3: прямой запуск (без experimental опций)
        try:
            logger.info("Попытка прямого запуска ChromeDriver...")
            opts3 = Options()
            if headless:
                opts3.add_argument('--headless')
            opts3.add_argument('--no-sandbox')
            opts3.add_argument('--disable-dev-shm-usage')
            opts3.add_argument('--disable-gpu')
            opts3.add_argument('--window-size=1920,1080')
            opts3.add_argument('--disable-blink-features=AutomationControlled')
            self.driver = webdriver.Chrome(options=opts3)
            logger.info("✓ WebDriver успешно запущен напрямую")
            return
        except Exception as ex3:
            e3 = ex3

        logger.error(
            f"Все способы запуска драйвера неудачны:\n"
            f"  1. undetected-chromedriver: {e1}\n"
            f"  2. webdriver-manager: {e2}\n"
            f"  3. Прямой запуск: {e3}"
        )
        raise RuntimeError(
            "Не удалось запустить Chrome WebDriver.\n"
            "Установите зависимости: pip install webdriver-manager undetected-chromedriver"
        )

    def login(self, username: str, password: str) -> bool:
        """Выполнение входа в портал МГТУ"""
        try:
            if not self.driver:
                self.setup_driver()

            conf = cfg.load()
            # ВАЖНО: используем прямую ссылку на страницу входа, не главную страницу
            portal_url = conf.get('portal_url', 'https://newlms.magtu.ru/login/index.php')

            logger.info(f"Переход на портал: {portal_url}")
            self.driver.get(portal_url)
            time.sleep(2)

            # Сохраняем страницу для отладки если нужно
            if 'login' not in self.driver.current_url.lower():
                logger.warning(f"Не на странице входа. Текущий URL: {self.driver.current_url}")
                _save_debug_page(self.driver, 'debug_login_page.html')

            # Ожидание поля логина
            try:
                username_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, 'username'))
                )
            except Exception:
                username_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, 'username'))
                )

            password_field = self.driver.find_element(By.ID, 'password')

            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)

            try:
                login_button = self.driver.find_element(By.ID, 'loginbtn')
            except Exception:
                login_button = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')

            login_button.click()

            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'usermenu'))
                )
                logger.info("✓ Успешный вход в портал МГТУ")
                return True
            except Exception:
                error_elements = self.driver.find_elements(By.CLASS_NAME, 'error')
                if error_elements:
                    logger.error(f"Ошибка авторизации: {error_elements[0].text}")
                else:
                    logger.error("Не удалось определить статус входа")
                _save_debug_page(self.driver, 'debug_after_login.html')
                return False

        except Exception as e:
            logger.error(f"Ошибка при входе в портал: {str(e)}", exc_info=True)
            if self.driver:
                logger.error(f"Текущий URL: {self.driver.current_url}")
                logger.error(f"Заголовок: {self.driver.title}")
                _save_debug_page(self.driver, 'debug_error_page.html')
            return False

    def navigate_to_curator_cabinet(self, group_id: str = '') -> bool:
        """Переход в кабинет куратора"""
        try:
            conf = cfg.load()
            if not group_id:
                group_id = conf.get('group_id', '4618')

            curator_url = (
                f"https://newlms.magtu.ru/report/magtu_cabinet_for_curator"
                f"/index.php?gradebook={group_id}"
            )
            # Если задан явный URL — используем его
            grades_url = conf.get('portal_grades_url', '')
            if grades_url:
                curator_url = grades_url

            logger.info(f"Переход в кабинет куратора: {curator_url}")
            self.driver.get(curator_url)
            time.sleep(3)

            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, 'cabinet_for_curator_table_top'))
                )
                logger.info("✓ Успешный переход в кабинет куратора")
                return True
            except Exception:
                logger.error("Таблица куратора не найдена на странице")
                _save_debug_page(self.driver, 'debug_curator_page.html')
                return False

        except Exception as e:
            logger.error(f"Ошибка при переходе в кабинет куратора: {str(e)}", exc_info=True)
            return False

    def prepare_tables_for_scraping(self):
        """Подготовка таблиц куратора к парсингу (удаление overflow:hidden)"""
        try:
            logger.info("Подготовка таблиц куратора к парсингу...")

            for elem_id, name in [('id3', 'студентов'), ('id1', 'дисциплин'), ('id2', 'оценок')]:
                try:
                    element = self.driver.find_element(By.ID, elem_id)
                    self.driver.execute_script(
                        "arguments[0].style.overflow = 'visible';", element
                    )
                    logger.info(f"✓ Таблица {name} ({elem_id}) подготовлена")
                except Exception as e:
                    logger.warning(f"Не удалось подготовить таблицу {name} ({elem_id}): {e}")
                time.sleep(0.5)

            time.sleep(1)
            logger.info("✓ Все таблицы подготовлены к парсингу")
            return True

        except Exception as e:
            logger.error(f"Ошибка при подготовке таблиц: {str(e)}", exc_info=True)
            return False

    def get_page_source(self) -> str:
        return self.driver.page_source if self.driver else ""

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Браузер закрыт")
            except Exception:
                logger.warning("Ошибка при закрытии браузера")


def _save_debug_page(driver, filename: str):
    """Сохраняет HTML страницы для отладки (как в оригинальном ProCurator)"""
    try:
        path = DEBUG_DIR / filename
        with open(path, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.info(f"Debug-страница сохранена: {path}")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
#  Публичные функции для Flask-контроллера
# ──────────────────────────────────────────────────────────────

def login_and_get_html_from_config() -> str:
    """Точка входа для Flask-контроллера."""
    conf = cfg.load()

    # ─── ТЕСТОВЫЙ РЕЖИМ ───
    # Если включён test_mode и указан test_html_path — читаем HTML с диска,
    # пропуская Selenium и портал. Удобно для отладки парсинга и генерации.
    if conf.get('test_mode', False):
        test_path = conf.get('test_html_path', '')
        if not test_path:
            raise RuntimeError(
                "Включён тестовый режим, но путь к HTML-файлу не указан.\n"
                "Откройте Настройки и заполните поле 'Путь к тестовому HTML'."
            )
        test_file = Path(test_path)
        if not test_file.exists():
            raise RuntimeError(
                f"Тестовый HTML-файл не найден:\n{test_path}\n"
                "Проверьте путь в Настройках."
            )
        try:
            html = test_file.read_text(encoding='utf-8')
            logger.info(f"[ТЕСТОВЫЙ РЕЖИМ] HTML загружен с диска: {test_path}")
            logger.info(f"[ТЕСТОВЫЙ РЕЖИМ] Размер HTML: {len(html)} символов")
            return html
        except UnicodeDecodeError:
            # На случай если файл сохранён не в UTF-8
            html = test_file.read_text(encoding='cp1251')
            logger.info(f"[ТЕСТОВЫЙ РЕЖИМ] HTML загружен (cp1251): {test_path}")
            return html

    # ─── БОЕВОЙ РЕЖИМ — заход на портал ───
    security = SecurityManager()

    login = conf.get('portal_login', '')
    password_raw = conf.get('portal_password', '')

    # Приоритет — зашифрованный файл credentials.enc
    if CREDENTIALS_FILE.exists():
        try:
            login, password_raw = security.load_credentials(CREDENTIALS_FILE)
            logger.info("Учётные данные из credentials.enc")
        except Exception as e:
            logger.warning(f"credentials.enc: {e}. Используем настройки.")

    password = security.decrypt_password(password_raw)

    if not login or not password:
        raise RuntimeError(
            "Логин или пароль не заполнены.\n"
            "Откройте Настройки и введите данные для входа на портал."
        )

    auth = PortalAuth()
    try:
        if not auth.login(login, password):
            raise RuntimeError(
                "Ошибка авторизации на портале.\n"
                "Проверьте логин и пароль в Настройках."
            )
        if not auth.navigate_to_curator_cabinet():
            raise RuntimeError(
                "Не удалось открыть кабинет куратора.\n"
                "Проверьте URL кабинета в Настройках."
            )
        auth.prepare_tables_for_scraping()
        html = auth.get_page_source()
        logger.info(f"HTML получен ({len(html)} символов)")
        return html
    finally:
        auth.close()


def save_credentials_from_settings(username: str, password: str):
    """Сохраняет учётные данные в зашифрованный файл."""
    security = SecurityManager()
    security.save_credentials(username, password, CREDENTIALS_FILE)
    logger.info(f"Учётные данные сохранены: {CREDENTIALS_FILE}")
