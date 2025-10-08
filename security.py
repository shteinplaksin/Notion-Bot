"""
Модуль безопасности и валидации для NotesBot
"""

import re
import time
import hashlib
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate Limiter для ограничения количества запросов"""
    
    def __init__(self):
        self.requests = defaultdict(list)
        self.limits = {
            'message': {'count': 20, 'window': 60},  # 20 сообщений в минуту
            'command': {'count': 10, 'window': 60},  # 10 команд в минуту
            'search': {'count': 5, 'window': 60},    # 5 поисков в минуту
            'create': {'count': 15, 'window': 60},   # 15 создания в минуту
            'file': {'count': 3, 'window': 300},     # 3 файла в 5 минут
        }
    
    def is_allowed(self, user_id: int, action_type: str) -> bool:
        """Проверка разрешения на действие"""
        now = time.time()
        user_key = f"{user_id}:{action_type}"
        
        if action_type not in self.limits:
            return True
        
        limit_config = self.limits[action_type]
        window = limit_config['window']
        max_count = limit_config['count']
        
        # Очищаем старые записи
        self.requests[user_key] = [
            req_time for req_time in self.requests[user_key]
            if now - req_time < window
        ]
        
        # Проверяем лимит
        if len(self.requests[user_key]) >= max_count:
            logger.warning(f"Rate limit exceeded for user {user_id}, action {action_type}")
            return False
        
        # Добавляем текущий запрос
        self.requests[user_key].append(now)
        return True
    
    def get_remaining_time(self, user_id: int, action_type: str) -> int:
        """Получение времени до сброса лимита"""
        if action_type not in self.limits:
            return 0
        
        now = time.time()
        user_key = f"{user_id}:{action_type}"
        window = self.limits[action_type]['window']
        
        if user_key in self.requests and self.requests[user_key]:
            oldest_request = min(self.requests[user_key])
            return max(0, int(window - (now - oldest_request)))
        
        return 0


class InputValidator:
    """Валидатор входных данных"""
    
    def __init__(self):
        self.max_lengths = {
            'note_title': 200,
            'note_content': 10000,
            'reminder_title': 200,
            'reminder_content': 5000,
            'category_name': 50,
            'search_query': 100,
            'tag_name': 30
        }
        
        self.forbidden_patterns = [
            r'<script.*?>.*?</script>',  # XSS защита
            r'javascript:',
            r'vbscript:',
            r'on\w+\s*=',  # event handlers
            r'<iframe.*?>',
            r'<object.*?>',
            r'<embed.*?>'
        ]
    
    def validate_text(self, text: str, field_type: str) -> Dict[str, Any]:
        """Валидация текстового поля"""
        result = {'valid': True, 'errors': [], 'cleaned_text': text}
        
        if not text or not text.strip():
            result['valid'] = False
            result['errors'].append("Поле не может быть пустым")
            return result
        
        # Проверка длины
        max_length = self.max_lengths.get(field_type, 1000)
        if len(text) > max_length:
            result['valid'] = False
            result['errors'].append(f"Максимальная длина: {max_length} символов")
            return result
        
        # Проверка на опасные паттерны
        for pattern in self.forbidden_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                result['valid'] = False
                result['errors'].append("Обнаружен недопустимый контент")
                logger.warning(f"Suspicious content detected: {pattern}")
                break
        
        # Очистка текста
        cleaned_text = self._clean_text(text)
        result['cleaned_text'] = cleaned_text
        
        return result
    
    def validate_file(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация загружаемого файла"""
        result = {'valid': True, 'errors': []}
        
        file_name = file_info.get('file_name', '')
        file_size = file_info.get('file_size', 0)
        mime_type = file_info.get('mime_type', '')
        
        # Проверка размера файла
        max_sizes = {
            'image': 10 * 1024 * 1024,  # 10MB для изображений
            'document': 20 * 1024 * 1024,  # 20MB для документов
            'audio': 50 * 1024 * 1024,  # 50MB для аудио
            'default': 5 * 1024 * 1024   # 5MB по умолчанию
        }
        
        file_category = self._get_file_category(mime_type)
        max_size = max_sizes.get(file_category, max_sizes['default'])
        
        if file_size > max_size:
            result['valid'] = False
            result['errors'].append(f"Файл слишком большой. Максимум: {max_size // (1024*1024)}MB")
        
        # Проверка типа файла
        allowed_types = {
            'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
            'document': ['application/pdf', 'application/msword', 
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'text/plain', 'text/markdown'],
            'audio': ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp4']
        }
        
        if file_category in allowed_types:
            if mime_type not in allowed_types[file_category]:
                result['valid'] = False
                result['errors'].append(f"Неподдерживаемый тип файла: {mime_type}")
        else:
            result['valid'] = False
            result['errors'].append("Неподдерживаемый тип файла")
        
        # Проверка имени файла
        if not self._is_safe_filename(file_name):
            result['valid'] = False
            result['errors'].append("Недопустимое имя файла")
        
        return result
    
    def validate_user_limits(self, user_id: int, db_stats: Dict[str, int]) -> Dict[str, Any]:
        """Проверка лимитов пользователя"""
        result = {'valid': True, 'errors': []}
        
        limits = {
            'notes': 1000,
            'reminders': 200,
            'categories': 50,
            'files': 100
        }
        
        for resource, limit in limits.items():
            current_count = db_stats.get(resource, 0)
            if current_count >= limit:
                result['valid'] = False
                result['errors'].append(f"Достигнут лимит {resource}: {limit}")
        
        return result
    
    def _clean_text(self, text: str) -> str:
        """Очистка текста от опасного контента"""
        # Удаляем HTML теги (кроме разрешенных)
        allowed_tags = ['b', 'i', 'u', 'code', 'pre']
        
        # Простая очистка - удаляем все HTML теги кроме разрешенных
        for pattern in self.forbidden_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Обрезаем лишние пробелы
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _get_file_category(self, mime_type: str) -> str:
        """Определение категории файла по MIME типу"""
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('audio/'):
            return 'audio'
        elif mime_type in ['application/pdf', 'application/msword', 
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                          'text/plain', 'text/markdown']:
            return 'document'
        else:
            return 'unknown'
    
    def _is_safe_filename(self, filename: str) -> bool:
        """Проверка безопасности имени файла"""
        if not filename:
            return False
        
        # Проверяем на опасные символы
        dangerous_chars = ['..', '/', '\\', '<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            if char in filename:
                return False
        
        # Проверяем на системные имена файлов (Windows)
        system_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                       'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                       'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        
        name_without_ext = filename.split('.')[0].upper()
        if name_without_ext in system_names:
            return False
        
        return True


class SecurityManager:
    """Менеджер безопасности"""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.validator = InputValidator()
        self.suspicious_users = set()
        self.blocked_users = set()
    
    async def check_user_access(self, user_id: int, action_type: str) -> Dict[str, Any]:
        """Комплексная проверка доступа пользователя"""
        result = {'allowed': True, 'reason': '', 'wait_time': 0}
        
        # Проверка блокировки
        if user_id in self.blocked_users:
            result['allowed'] = False
            result['reason'] = 'Пользователь заблокирован'
            return result
        
        # Проверка rate limit
        if not self.rate_limiter.is_allowed(user_id, action_type):
            wait_time = self.rate_limiter.get_remaining_time(user_id, action_type)
            result['allowed'] = False
            result['reason'] = f'Превышен лимит запросов. Подождите {wait_time} сек.'
            result['wait_time'] = wait_time
            
            # Добавляем в подозрительные если часто превышает лимиты
            self.suspicious_users.add(user_id)
            return result
        
        return result
    
    def validate_input(self, text: str, field_type: str) -> Dict[str, Any]:
        """Валидация входных данных"""
        return self.validator.validate_text(text, field_type)
    
    def validate_file_upload(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация загрузки файла"""
        return self.validator.validate_file(file_info)
    
    def check_user_limits(self, user_id: int, db_stats: Dict[str, int]) -> Dict[str, Any]:
        """Проверка лимитов пользователя"""
        return self.validator.validate_user_limits(user_id, db_stats)
    
    def block_user(self, user_id: int, reason: str = ""):
        """Блокировка пользователя"""
        self.blocked_users.add(user_id)
        logger.warning(f"User {user_id} blocked. Reason: {reason}")
    
    def unblock_user(self, user_id: int):
        """Разблокировка пользователя"""
        self.blocked_users.discard(user_id)
        logger.info(f"User {user_id} unblocked")
    
    def is_suspicious_user(self, user_id: int) -> bool:
        """Проверка подозрительного пользователя"""
        return user_id in self.suspicious_users
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Получение статистики безопасности"""
        return {
            'blocked_users': len(self.blocked_users),
            'suspicious_users': len(self.suspicious_users),
            'rate_limits': dict(self.rate_limiter.limits)
        }


# Глобальный экземпляр менеджера безопасности
security_manager = SecurityManager()
