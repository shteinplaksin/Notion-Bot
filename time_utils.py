import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import pytz
from dateutil import parser
from dateutil.relativedelta import relativedelta


class TimeParser:
    """Класс для парсинга времени и даты из текста"""
    
    def __init__(self):
        self.timezone = pytz.timezone('Europe/Moscow')  # Московское время по умолчанию
        
    def parse_time(self, text: str, base_time: datetime = None) -> Optional[datetime]:
        """
        Парсинг времени из текста
        Поддерживает различные форматы:
        - "через 5 минут"
        - "завтра в 15:30"
        - "25.12.2024 в 10:00"
        - "в понедельник"
        - "через час"
        """
        if base_time is None:
            base_time = datetime.now(self.timezone)
        
        text = text.lower().strip()
        
        # Убираем лишние пробелы
        text = re.sub(r'\s+', ' ', text)
        
        # Парсинг относительного времени
        relative_time = self._parse_relative_time(text, base_time)
        if relative_time:
            return relative_time
        
        # Парсинг абсолютного времени
        absolute_time = self._parse_absolute_time(text, base_time)
        if absolute_time:
            return absolute_time
        
        # Парсинг дней недели
        weekday_time = self._parse_weekday(text, base_time)
        if weekday_time:
            return weekday_time
        
        return None
    
    def _parse_relative_time(self, text: str, base_time: datetime) -> Optional[datetime]:
        """Парсинг относительного времени"""
        patterns = [
            # Через N минут/часов/дней
            (r'через\s+(\d+)\s+(минут|минуту|минуты|час|часа|часов|день|дня|дней|неделю|недели|недель)', self._parse_relative_units),
            # Через N минут/часов/дней (без "через")
            (r'(\d+)\s+(минут|минуту|минуты|час|часа|часов|день|дня|дней|неделю|недели|недель)', self._parse_relative_units),
            # Завтра/послезавтра
            (r'завтра', lambda m, bt: bt + timedelta(days=1)),
            (r'послезавтра', lambda m, bt: bt + timedelta(days=2)),
            # Сегодня
            (r'сегодня', lambda m, bt: bt.replace(hour=9, minute=0, second=0, microsecond=0)),
        ]
        
        for pattern, handler in patterns:
            match = re.search(pattern, text)
            if match:
                return handler(match, base_time)
        
        return None
    
    def _parse_relative_units(self, match, base_time: datetime) -> datetime:
        """Парсинг единиц времени"""
        amount = int(match.group(1))
        unit = match.group(2)
        
        if unit in ['минут', 'минуту', 'минуты']:
            return base_time + timedelta(minutes=amount)
        elif unit in ['час', 'часа', 'часов']:
            return base_time + timedelta(hours=amount)
        elif unit in ['день', 'дня', 'дней']:
            return base_time + timedelta(days=amount)
        elif unit in ['неделю', 'недели', 'недель']:
            return base_time + timedelta(weeks=amount)
        
        return base_time
    
    def _parse_absolute_time(self, text: str, base_time: datetime) -> Optional[datetime]:
        """Парсинг абсолютного времени"""
        # Паттерны для даты и времени
        patterns = [
            # DD.MM.YYYY HH:MM
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(?:в\s+)?(\d{1,2}):(\d{2})',
            # DD.MM HH:MM (текущий год)
            r'(\d{1,2})\.(\d{1,2})\s+(?:в\s+)?(\d{1,2}):(\d{2})',
            # HH:MM
            r'(\d{1,2}):(\d{2})',
            # DD.MM.YYYY
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
            # DD.MM (текущий год)
            r'(\d{1,2})\.(\d{1,2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                
                if len(groups) == 5:  # DD.MM.YYYY HH:MM
                    day, month, year, hour, minute = map(int, groups)
                    return self.timezone.localize(datetime(year, month, day, hour, minute))
                
                elif len(groups) == 4:  # DD.MM HH:MM
                    day, month, hour, minute = map(int, groups)
                    year = base_time.year
                    return self.timezone.localize(datetime(year, month, day, hour, minute))
                
                elif len(groups) == 2 and ':' in text:  # HH:MM
                    hour, minute = map(int, groups)
                    target_date = base_time.date()
                    if hour < base_time.hour or (hour == base_time.hour and minute <= base_time.minute):
                        target_date += timedelta(days=1)
                    return self.timezone.localize(datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute)))
                
                elif len(groups) == 3:  # DD.MM.YYYY
                    day, month, year = map(int, groups)
                    return self.timezone.localize(datetime(year, month, day, 9, 0))
                
                elif len(groups) == 2:  # DD.MM
                    day, month = map(int, groups)
                    year = base_time.year
                    target_date = self.timezone.localize(datetime(year, month, day, 9, 0))
                    if target_date < base_time:
                        target_date = self.timezone.localize(datetime(year + 1, month, day, 9, 0))
                    return target_date
        
        return None
    
    def _parse_weekday(self, text: str, base_time: datetime) -> Optional[datetime]:
        """Парсинг дней недели"""
        weekdays = {
            'понедельник': 0, 'вторник': 1, 'среда': 2, 'четверг': 3,
            'пятница': 4, 'суббота': 5, 'воскресенье': 6
        }
        
        for weekday_name, weekday_num in weekdays.items():
            if weekday_name in text:
                days_ahead = weekday_num - base_time.weekday()
                if days_ahead <= 0:  # Если день уже прошел на этой неделе
                    days_ahead += 7
                
                target_date = base_time + timedelta(days=days_ahead)
                return target_date.replace(hour=9, minute=0, second=0, microsecond=0)
        
        return None
    
    def format_datetime(self, dt: datetime, format_type: str = "full") -> str:
        """Форматирование даты и времени для отображения"""
        if format_type == "full":
            return dt.strftime("%d.%m.%Y в %H:%M")
        elif format_type == "date":
            return dt.strftime("%d.%m.%Y")
        elif format_type == "time":
            return dt.strftime("%H:%M")
        elif format_type == "relative":
            now = datetime.now(self.timezone)
            diff = dt - now
            
            if diff.days > 0:
                return f"через {diff.days} дн."
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"через {hours} ч."
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"через {minutes} мин."
            else:
                return "сейчас"
        
        return dt.strftime("%d.%m.%Y %H:%M")
    
    def get_time_until(self, target_time: datetime) -> str:
        """Получение времени до указанной даты"""
        now = datetime.now(self.timezone)
        diff = target_time - now
        
        if diff.total_seconds() < 0:
            return "время истекло"
        
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days} дн.")
        if hours > 0:
            parts.append(f"{hours} ч.")
        if minutes > 0:
            parts.append(f"{minutes} мин.")
        
        if not parts:
            return "менее минуты"
        
        return " ".join(parts)


def calculate_next_reminder_time(current_time: datetime, repeat_type: str, repeat_interval: int) -> datetime:
    """Compute the next run for a repeating reminder."""
    if repeat_interval is None or repeat_interval < 1:
        repeat_interval = 1
    repeat_type = (repeat_type or 'none').lower()

    if repeat_type in ('hourly', 'hours'):
        delta = timedelta(hours=repeat_interval)
    elif repeat_type in ('daily', 'day', 'days'):
        delta = timedelta(days=repeat_interval)
    elif repeat_type in ('weekly', 'week', 'weeks'):
        delta = timedelta(weeks=repeat_interval)
    elif repeat_type in ('monthly', 'month', 'months'):
        delta = relativedelta(months=repeat_interval)
    elif repeat_type in ('yearly', 'year', 'years', 'annually'):
        delta = relativedelta(years=repeat_interval)
    else:
        delta = timedelta(days=repeat_interval)

    try:
        return current_time + delta
    except Exception:
        base = current_time.replace(tzinfo=None)
        if isinstance(delta, timedelta):
            return base + delta
        return base + relativedelta(months=repeat_interval)



def parse_time_input(text: str) -> Tuple[Optional[datetime], str]:
    """
    Парсинг времени из пользовательского ввода
    Возвращает (datetime, оставшийся_текст)
    """
    parser_instance = TimeParser()
    
    # Попробуем найти время в тексте
    time_patterns = [
        r'(\d{1,2}:\d{2})',
        r'(\d{1,2}\.\d{1,2}(?:\.\d{4})?)',
        r'(через\s+\d+\s+(?:минут|час|день|неделю))',
        r'(завтра|послезавтра|сегодня)',
        r'(в\s+(?:понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье))',
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            time_text = match.group(1)
            parsed_time = parser_instance.parse_time(time_text)
            if parsed_time:
                remaining_text = text.replace(match.group(0), '').strip()
                return parsed_time, remaining_text
    
    return None, text
