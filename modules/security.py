"""
Модуль безопасности — шифрование учётных данных и настроек.
Взят из ProCurator (github.com/Ruslan4ikA/ProCurator/modules/security.py),
расширен шифрованием отдельных полей settings.json.
"""
from cryptography.fernet import Fernet, InvalidToken
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

KEY_FILE = Path(__file__).parent.parent / '.secret_key'

# Поля settings.json которые хранятся в зашифрованном виде
# Значения этих полей в файле начинаются с префикса ENC:
ENCRYPTED_FIELDS = {
    'portal_login',
    'portal_password',
    'smtp_login',
    'smtp_password',
    'smtp_from',
    'email_recipients',
    'recipients_excel_path',
}

ENC_PREFIX = 'ENC:'


class SecurityManager:
    """Менеджер безопасности для шифрования данных"""

    def __init__(self):
        self.key_file = KEY_FILE
        self.cipher = self._load_or_create_key()

    def _load_or_create_key(self):
        """Загружает существующий ключ или создаёт новый"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
        return Fernet(key)

    def encrypt(self, data: str) -> str:
        """Шифрует строку и возвращает base64"""
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Расшифровывает строку"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()

    def encrypt_value(self, value: str) -> str:
        """Шифрует значение поля настроек. Добавляет префикс ENC:"""
        if not value:
            return value
        if value.startswith(ENC_PREFIX):
            return value  # уже зашифровано
        return ENC_PREFIX + self.encrypt(value)

    def decrypt_value(self, value: str) -> str:
        """
        Расшифровывает значение поля настроек.
        Если значение не начинается с ENC: — возвращает как есть
        (обратная совместимость со старым незашифрованным settings.json).
        """
        if not value or not isinstance(value, str):
            return value
        if not value.startswith(ENC_PREFIX):
            return value  # старое незашифрованное значение
        try:
            return self.decrypt(value[len(ENC_PREFIX):])
        except (InvalidToken, Exception):
            return value  # если не удалось расшифровать — отдаём как есть

    def encrypt_config(self, cfg: dict) -> dict:
        """
        Возвращает копию конфига с зашифрованными чувствительными полями.
        Используется перед записью в файл.
        """
        result = cfg.copy()
        for field in ENCRYPTED_FIELDS:
            if field in result and result[field]:
                result[field] = self.encrypt_value(str(result[field]))
        return result

    def decrypt_config(self, cfg: dict) -> dict:
        """
        Возвращает копию конфига с расшифрованными полями.
        Используется после чтения из файла.
        """
        result = cfg.copy()
        for field in ENCRYPTED_FIELDS:
            if field in result and result[field]:
                result[field] = self.decrypt_value(str(result[field]))
        return result

    # ── Совместимость с ProCurator (credentials.enc) ──────────────────────

    def save_credentials(self, username: str, password: str, filepath: Path):
        """Сохраняет учётные данные в зашифрованном виде"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"username:{self.encrypt(username)}\n")
            f.write(f"password:{self.encrypt(password)}\n")

    def load_credentials(self, filepath: Path) -> tuple:
        """Загружает учётные данные из зашифрованного файла"""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Файл не найден: {filepath}")
        credentials = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    key, value = line.strip().split(':', 1)
                    credentials[key] = value
        return self.decrypt(credentials['username']), self.decrypt(credentials['password'])

    def decrypt_password(self, token: str) -> str:
        """Расшифровывает пароль. Если не зашифрован — возвращает как есть."""
        try:
            return self.decrypt(token)
        except Exception:
            return token