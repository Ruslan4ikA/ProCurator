"""
Модуль безопасности - шифрование данных
"""
from cryptography.fernet import Fernet
from pathlib import Path
import os
from config import KEY_FILE


class SecurityManager:
    """Менеджер безопасности для шифрования данных"""
    
    def __init__(self):
        self.key_file = KEY_FILE
        self.cipher = self._load_or_create_key()
    
    def _load_or_create_key(self):
        """Загружает существующий ключ или создает новый"""
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
        """Сохраняет учетные данные в зашифрованном виде"""
        encrypted_username = self.encrypt(username)
        encrypted_password = self.encrypt(password)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"username:{encrypted_username}\n")
            f.write(f"password:{encrypted_password}\n")
    
    def load_credentials(self, filepath: Path) -> tuple:
        """Загружает учетные данные из зашифрованного файла"""
        if not filepath.exists():
            raise FileNotFoundError(f"Файл с учетными данными не найден: {filepath}")
        
        credentials = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    key, value = line.strip().split(':', 1)
                    credentials[key] = value
        
        username = self.decrypt(credentials['username'])
        password = self.decrypt(credentials['password'])
        
        return username, password