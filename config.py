# -*- coding: utf-8 -*-

"""
Файл конфигурации
"""

import os
from typing import Optional

# Загружаем переменные окружения из .env файла
try:
    from dotenv import load_dotenv
    # Проверяем, существует ли .env файл
    if os.path.exists('.env'):
        load_dotenv()
except ImportError:
    # Если python-dotenv не установлен, используем обычные переменные окружения
    pass

# Токен вашего бота из переменных окружения
BOT_TOKEN: Optional[str] = os.getenv('BOT_TOKEN')

# Путь к базе данных
DATABASE_PATH = os.getenv('DATABASE_PATH', "notes_bot.db")

# Другие настройки
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Проверка наличия обязательных настроек
if not BOT_TOKEN:
    raise ValueError(
        "Не найден BOT_TOKEN! "
        "Создайте файл .env с переменной BOT_TOKEN=ваш_токен_бота"
    )
