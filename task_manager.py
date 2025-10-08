"""
Модуль управления задачами и временными блоками для NotesBot
"""

import asyncio
import json
from datetime import datetime, timedelta, time
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TaskManager:
    """Менеджер задач"""
    
    def __init__(self, db):
        self.db = db
    
    async def create_recurring_task(self, user_id: int, title: str, description: str,
                                  repeat_type: str, repeat_interval: int = 1,
                                  start_date: datetime = None, end_date: datetime = None,
                                  priority: str = "medium") -> Dict[str, Any]:
        """Создание повторяющейся задачи"""
        try:
            if start_date is None:
                start_date = datetime.now()
            
            # Вычисляем следующую дату выполнения
            next_due = self._calculate_next_due(start_date, repeat_type, repeat_interval)
            
            # Создаем задачу
            task_id = await self.db.add_recurring_task(
                user_id=user_id,
                title=title,
                description=description,
                repeat_type=repeat_type,
                repeat_interval=repeat_interval,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat() if end_date else None,
                next_due=next_due.isoformat(),
                priority=priority,
                metadata=json.dumps({})
            )
            
            return {
                'success': True,
                'task_id': task_id,
                'next_due': next_due.isoformat(),
                'message': 'Повторяющаяся задача создана'
            }
            
        except Exception as e:
            logger.error(f"Error creating recurring task: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_daily_schedule(self, user_id: int, date: datetime = None) -> Dict[str, Any]:
        """Получение расписания на день"""
        try:
            if date is None:
                date = datetime.now().date()
            
            start_of_day = datetime.combine(date, time.min).isoformat()
            end_of_day = datetime.combine(date, time.max).isoformat()
            
            # Получаем временные блоки
            time_blocks = await self.db.get_time_blocks(user_id, start_of_day, end_of_day)
            
            # Получаем задачи на день
            tasks = await self.db.get_recurring_tasks(user_id, status="pending")
            
            # Анализируем занятость
            total_scheduled_time = 0
            for block in time_blocks:
                try:
                    start = datetime.fromisoformat(block['start_time'])
                    end = datetime.fromisoformat(block['end_time'])
                    total_scheduled_time += (end - start).total_seconds() / 3600
                except:
                    continue
            
            free_time = max(0, 24 - total_scheduled_time)
            
            return {
                'date': date.isoformat(),
                'time_blocks': time_blocks,
                'tasks': tasks,
                'total_scheduled_hours': total_scheduled_time,
                'free_hours': free_time,
                'schedule_density': min(100, (total_scheduled_time / 24) * 100)
            }
            
        except Exception as e:
            logger.error(f"Error getting daily schedule: {e}")
            return {
                'date': datetime.now().date().isoformat(),
                'time_blocks': [],
                'tasks': [],
                'total_scheduled_hours': 0,
                'free_hours': 24,
                'schedule_density': 0
            }
    
    def _calculate_next_due(self, current_date: datetime, repeat_type: str, 
                          repeat_interval: int) -> datetime:
        """Вычисление следующей даты выполнения"""
        if repeat_type == 'daily':
            return current_date + timedelta(days=repeat_interval)
        elif repeat_type == 'weekly':
            return current_date + timedelta(weeks=repeat_interval)
        elif repeat_type == 'monthly':
            return current_date + timedelta(days=30 * repeat_interval)
        elif repeat_type == 'yearly':
            return current_date + timedelta(days=365 * repeat_interval)
        else:
            return current_date + timedelta(days=1)


class ProgressTracker:
    """Трекер прогресса выполнения целей"""
    
    def __init__(self, db):
        self.db = db
    
    async def create_goal(self, user_id: int, title: str, description: str,
                         target_value: float, current_value: float = 0.0,
                         unit: str = "штук", deadline: datetime = None,
                         category: str = "general") -> Dict[str, Any]:
        """Создание цели"""
        try:
            goal_id = await self.db.add_goal(
                user_id=user_id,
                title=title,
                description=description,
                target_value=target_value,
                current_value=current_value,
                unit=unit,
                deadline=deadline.isoformat() if deadline else None,
                category=category
            )
            
            return {
                'success': True,
                'goal_id': goal_id,
                'progress_percentage': (current_value / target_value * 100) if target_value > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error creating goal: {e}")
            return {'success': False, 'error': str(e)}
    
    async def update_progress(self, goal_id: int, user_id: int, 
                            value_change: float, note: str = "") -> Dict[str, Any]:
        """Обновление прогресса по цели"""
        try:
            goals = await self.db.get_goals(user_id, status="all")
            goal = next((g for g in goals if g['id'] == goal_id), None)
            
            if not goal:
                return {'success': False, 'error': 'Цель не найдена'}
            
            new_value = goal['current_value'] + value_change
            progress_percentage = (new_value / goal['target_value'] * 100) if goal['target_value'] > 0 else 0
            
            # Обновляем цель
            await self.db.update_goal_progress(goal_id, user_id, new_value)
            
            # Логируем изменение прогресса
            await self.db.log_progress_change(goal_id, value_change, note)
            
            # Проверяем достижение цели
            is_completed = new_value >= goal['target_value']
            
            return {
                'success': True,
                'new_value': new_value,
                'progress_percentage': progress_percentage,
                'is_completed': is_completed,
                'remaining': max(0, goal['target_value'] - new_value)
            }
            
        except Exception as e:
            logger.error(f"Error updating progress: {e}")
            return {'success': False, 'error': str(e)}