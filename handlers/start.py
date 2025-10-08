from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from keyboards import Keyboards

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, db, activity_tracker):
    """Обработчик команды /start"""
    user = message.from_user
    
    try:
        # Добавляем пользователя в базу данных
        await db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code
        )
        
        # Логируем активность
        activity_tracker.log_activity(user.id, "start")
        await db.log_user_activity(user.id, "start")
        
        welcome_text = f"""
🎉 Добро пожаловать в NotesBot Professional, {user.first_name}!

Этот бот поможет вам:
📝 Создавать и управлять заметками
⏰ Устанавливать напоминания
🔍 Быстро находить нужную информацию
📁 Организовывать заметки по категориям
📊 Анализировать продуктивность
🎯 Отслеживать цели
📋 Управлять повторяющимися задачами

🚀 Начните работу с главного меню ниже!
"""

        await message.answer(
            welcome_text,
            reply_markup=Keyboards.main_inline_menu()
        )
        
    except Exception as e:
        # logger.error(f"Error in start command: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = """
📘 <b>Как пользоваться NotesBot Professional:</b>

<b>📝 Заметки:</b>
/new - добавить заметку
/notes - список заметок
/search [запрос] - поиск заметок
/export - экспорт заметок

<b>⏰ Напоминания:</b>
/remind - создать напоминание
/reminders - активные напоминания
/today - план на сегодня
/schedule [дата] - расписание на день

<b>🎯 Цели и задачи:</b>
/goals - ваши цели
/tasks - повторяющиеся задачи

<b>📊 Аналитика:</b>
/report - подробный отчет
/stats [дней] - быстрая статистика

<b>📁 Файлы и настройки:</b>
/files - загруженные файлы
/settings - профиль и параметры

<b>Примеры:</b>
/new Купить подарки в 10:00
/remind Позвонить заказчику 15.01.2024 в 14:00
/search проект

Используйте меню, чтобы открыть основные разделы! 🙂
"""
    await message.answer(help_text, parse_mode="HTML")
