"""
Управление данными пользователей для NotesBot
"""

from typing import Dict, Any

# Словарь для хранения временных данных пользователей
user_data: Dict[int, Dict[str, Any]] = {}


def get_user_data(user_id: int) -> Dict[str, Any]:
    """Получение данных пользователя"""
    if user_id not in user_data:
        user_data[user_id] = {}
    return user_data[user_id]


def clear_user_data(user_id: int):
    """Очистка данных пользователя"""
    if user_id in user_data:
        del user_data[user_id]


def set_user_data(user_id: int, key: str, value: Any):
    """Установка данных пользователя"""
    user_data_dict = get_user_data(user_id)
    user_data_dict[key] = value
