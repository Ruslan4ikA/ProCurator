"""
Модуль безопасности — шифрование учётных данных.
Взят из ProCurator (github.com/Ruslan4ikA/ProCurator/modules/security.py).
"""
from cryptography.fernet import Fernet
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

KEY_FILE = Path(__file__).parent.parent / '.secret_key'


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
        """Шифрует строку"""
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Расшифровывает строку"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()

    def save_credentials(self, username: str, password: str, filepath: Path):
        """Сохраняет учётные данные в зашифрованном виде"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        encrypted_username = self.encrypt(username)
        encrypted_password = self.encrypt(password)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"username:{encrypted_username}\n")
            f.write(f"password:{encrypted_password}\n")

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
