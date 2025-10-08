"""
Модуль аналитики и отчетов для NotesBot
"""

import json
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, Counter
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ActivityRecord:
    """Запись активности пользователя"""
    user_id: int
    action_type: str
    timestamp: datetime
    metadata: Dict[str, Any] = None


class ActivityTracker:
    """Трекер активности пользователей"""
    
    def __init__(self):
        self.activities = []
        self.daily_stats = defaultdict(lambda: defaultdict(int))
    
    def log_activity(self, user_id: int, action_type: str, metadata: Dict[str, Any] = None):
        """Логирование активности"""
        activity = ActivityRecord(
            user_id=user_id,
            action_type=action_type,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self.activities.append(activity)
        
        # Обновляем дневную статистику
        date_key = activity.timestamp.date().isoformat()
        self.daily_stats[date_key][action_type] += 1
        self.daily_stats[date_key]['total'] += 1
    
    def get_user_activity(self, user_id: int, days: int = 30) -> List[ActivityRecord]:
        """Получение активности пользователя за период"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return [
            activity for activity in self.activities
            if activity.user_id == user_id and activity.timestamp >= cutoff_date
        ]


class ProductivityAnalyzer:
    """Анализатор продуктивности"""
    
    def __init__(self, db):
        self.db = db
        self.activity_tracker = ActivityTracker()
    
    async def analyze_user_productivity(self, user_id: int, period_days: int = 30) -> Dict[str, Any]:
        """Анализ продуктивности пользователя"""
        try:
            # Получаем данные из БД
            notes = await self.db.get_notes(user_id, limit=1000)
            reminders = await self.db.get_active_reminders(user_id)
            categories = await self.db.get_categories(user_id)
            
            # Фильтруем по периоду
            cutoff_date = datetime.now() - timedelta(days=period_days)
            recent_notes = [
                note for note in notes
                if datetime.fromisoformat(note['created_at']) >= cutoff_date
            ]
            
            # Анализируем активность
            activity = self.activity_tracker.get_user_activity(user_id, period_days)
            
            # Подсчитываем метрики
            metrics = {
                'period_days': period_days,
                'total_notes': len(notes),
                'recent_notes': len(recent_notes),
                'total_reminders': len(reminders),
                'categories_count': len(categories),
                'notes_per_day': len(recent_notes) / period_days if period_days > 0 else 0,
                'activity_score': self._calculate_activity_score(activity),
                'category_distribution': self._analyze_category_distribution(notes),
                'time_patterns': self._analyze_time_patterns(recent_notes),
                'completion_rate': await self._calculate_completion_rate(user_id, period_days)
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing productivity: {e}")
            return {}
    
    async def generate_productivity_report(self, user_id: int, period_days: int = 30) -> Dict[str, Any]:
        """Генерация отчета о продуктивности"""
        metrics = await self.analyze_user_productivity(user_id, period_days)
        
        if not metrics:
            return {'success': False, 'error': 'Не удалось собрать данные'}
        
        # Формируем текстовый отчет
        report_text = self._format_productivity_report(metrics)
        
        return {
            'success': True,
            'metrics': metrics,
            'report_text': report_text,
            'generated_at': datetime.now().isoformat()
        }
    
    def _calculate_activity_score(self, activities: List[ActivityRecord]) -> float:
        """Расчет балла активности"""
        if not activities:
            return 0.0
        
        # Веса для разных типов активности
        weights = {
            'create_note': 3,
            'create_reminder': 2,
            'edit_note': 2,
            'search': 1,
            'view_note': 0.5,
            'complete_reminder': 3,
            'upload_file': 2,
            'voice_note': 3
        }
        
        total_score = sum(weights.get(activity.action_type, 1) for activity in activities)
        days = (datetime.now() - min(activity.timestamp for activity in activities)).days or 1
        
        return total_score / days
    
    def _analyze_category_distribution(self, notes: List[Dict]) -> Dict[str, Any]:
        """Анализ распределения по категориям"""
        categories = Counter(note['category'] for note in notes)
        total = len(notes)
        
        return {
            'categories': dict(categories),
            'percentages': {
                cat: (count / total * 100) if total > 0 else 0
                for cat, count in categories.items()
            },
            'most_used': categories.most_common(1)[0] if categories else ('general', 0)
        }
    
    def _analyze_time_patterns(self, notes: List[Dict]) -> Dict[str, Any]:
        """Анализ временных паттернов"""
        if not notes:
            return {}
        
        hours = []
        weekdays = []
        
        for note in notes:
            try:
                created_at = datetime.fromisoformat(note['created_at'])
                hours.append(created_at.hour)
                weekdays.append(created_at.weekday())
            except:
                continue
        
        hour_distribution = Counter(hours)
        weekday_distribution = Counter(weekdays)
        
        # Определяем наиболее продуктивное время
        peak_hour = hour_distribution.most_common(1)[0] if hour_distribution else (9, 0)
        peak_weekday = weekday_distribution.most_common(1)[0] if weekday_distribution else (0, 0)
        
        weekday_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        
        return {
            'peak_hour': peak_hour[0],
            'peak_weekday': weekday_names[peak_weekday[0]],
            'hour_distribution': dict(hour_distribution),
            'weekday_distribution': dict(weekday_distribution)
        }
    
    async def _calculate_completion_rate(self, user_id: int, period_days: int) -> float:
        """Расчет процента выполнения задач"""
        try:
            # Получаем все напоминания за период
            all_reminders = await self.db.get_active_reminders(user_id)
            
            if not all_reminders:
                return 0.0
            
            # Считаем выполненные (неактивные) напоминания
            completed = len([r for r in all_reminders if not r['is_active']])
            total = len(all_reminders)
            
            return (completed / total * 100) if total > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating completion rate: {e}")
            return 0.0
    
    def _format_productivity_report(self, metrics: Dict[str, Any]) -> str:
        """Форматирование текстового отчета"""
        report = f"""
📊 <b>Отчет о продуктивности</b>

📈 <b>Общая статистика ({metrics['period_days']} дней):</b>
• Всего заметок: {metrics['total_notes']}
• Создано за период: {metrics['recent_notes']}
• Активных напоминаний: {metrics['total_reminders']}
• Категорий: {metrics['categories_count']}

📋 <b>Продуктивность:</b>
• Заметок в день: {metrics['notes_per_day']:.1f}
• Балл активности: {metrics['activity_score']:.1f}
• Процент выполнения: {metrics['completion_rate']:.1f}%

📁 <b>Популярные категории:</b>
"""
        
        # Добавляем информацию о категориях
        category_dist = metrics.get('category_distribution', {})
        if category_dist.get('categories'):
            for category, count in sorted(category_dist['categories'].items(), 
                                        key=lambda x: x[1], reverse=True)[:5]:
                percentage = category_dist['percentages'].get(category, 0)
                report += f"• {category}: {count} ({percentage:.1f}%)\n"
        
        # Добавляем временные паттерны
        time_patterns = metrics.get('time_patterns', {})
        if time_patterns:
            report += f"\n⏰ <b>Временные паттерны:</b>\n"
            report += f"• Пик активности: {time_patterns.get('peak_hour', 9)}:00\n"
            report += f"• Активный день: {time_patterns.get('peak_weekday', 'Понедельник')}\n"
        
        return report


class ReportGenerator:
    """Генератор отчетов"""
    
    def __init__(self, db):
        self.db = db
        self.productivity_analyzer = ProductivityAnalyzer(db)
    
    async def generate_user_report(self, user_id: int, report_type: str = 'full', 
                                 period_days: int = 30) -> Dict[str, Any]:
        """Генерация пользовательского отчета"""
        try:
            if report_type == 'productivity':
                return await self.productivity_analyzer.generate_productivity_report(user_id, period_days)
            elif report_type == 'summary':
                return await self._generate_summary_report(user_id, period_days)
            elif report_type == 'full':
                return await self._generate_full_report(user_id, period_days)
            else:
                return {'success': False, 'error': 'Неизвестный тип отчета'}
        
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _generate_summary_report(self, user_id: int, period_days: int) -> Dict[str, Any]:
        """Генерация краткого отчета"""
        notes = await self.db.get_notes(user_id, limit=1000)
        reminders = await self.db.get_active_reminders(user_id)
        categories = await self.db.get_categories(user_id)
        
        cutoff_date = datetime.now() - timedelta(days=period_days)
        recent_notes = [
            note for note in notes
            if datetime.fromisoformat(note['created_at']) >= cutoff_date
        ]
        
        report_text = f"""
📋 <b>Краткий отчет ({period_days} дней)</b>

📊 <b>Основные показатели:</b>
• Всего заметок: {len(notes)}
• Создано за период: {len(recent_notes)}
• Активных напоминаний: {len(reminders)}
• Категорий: {len(categories)}

📈 <b>Средние показатели:</b>
• Заметок в день: {len(recent_notes) / period_days:.1f}
• Заметок на категорию: {len(notes) / max(len(categories), 1):.1f}
"""
        
        return {
            'success': True,
            'report_text': report_text,
            'type': 'summary',
            'generated_at': datetime.now().isoformat()
        }
    
    async def _generate_full_report(self, user_id: int, period_days: int) -> Dict[str, Any]:
        """Генерация полного отчета"""
        # Получаем все данные
        productivity_report = await self.productivity_analyzer.generate_productivity_report(user_id, period_days)
        summary_report = await self._generate_summary_report(user_id, period_days)
        
        if not productivity_report['success'] or not summary_report['success']:
            return {'success': False, 'error': 'Ошибка при генерации отчета'}
        
        # Объединяем отчеты
        full_report_text = summary_report['report_text'] + "\n" + productivity_report['report_text']
        
        return {
            'success': True,
            'report_text': full_report_text,
            'metrics': productivity_report.get('metrics', {}),
            'type': 'full',
            'generated_at': datetime.now().isoformat()
        }


# Глобальные экземпляры
activity_tracker = ActivityTracker()