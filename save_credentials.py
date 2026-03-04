# save_credentials.py
from modules.security import SecurityManager
from pathlib import Path

sm = SecurityManager()
sm.save_credentials(
    'your_username', 
    'your_password', 
    Path('data/credentials/credentials.enc')
)
print("Учетные данные сохранены!")