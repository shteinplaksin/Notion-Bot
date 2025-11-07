"""
Модульный бот для NotesBot Professional с улучшенной архитектурой
"""

import asyncio
import logging
import json
import html
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram_sqlite_storage.sqlitestore import SQLStorage
from aiogram.types import Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from database import Database
from keyboards import Keyboards
from time_utils import TimeParser, parse_time_input, calculate_next_reminder_time
from states import NoteStates, ReminderStates, CategoryStates, FileStates, TaskStates, GoalStates
from user_data import get_user_data, set_user_data, clear_user_data
from security import security_manager
from file_manager import file_manager, voice_converter, document_processor
from analytics import activity_tracker, ProductivityAnalyzer, ReportGenerator
from task_manager import TaskManager, ProgressTracker
from monitoring import start_monitoring_server

# Импорт новых модулей обработчиков
from handlers.notes import NotesHandlers
from handlers.reminders import ReminderHandlers
from handlers.files import FileHandlers
from handlers.search import SearchHandlers
from handlers.settings import SettingsHandlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from config import BOT_TOKEN, DATABASE_PATH

# Инициализация бота
bot = Bot(token=BOT_TOKEN)

# Инициализация бота и диспетчера
BASE_DIR = Path(__file__).resolve().parent
db_path = Path(DATABASE_PATH)
if not db_path.is_absolute():
    db_path = BASE_DIR / db_path

fsm_storage_path = BASE_DIR / "data" / "notes_bot_fsm.db"
storage = SQLStorage(db_path=str(fsm_storage_path))
dp = Dispatcher(storage=storage)

# Инициализация базы данных
db = Database(db_path=str(db_path))

# Инициализация обработчиков
notes_handlers = NotesHandlers(db, bot)
reminder_handlers = ReminderHandlers(db, bot)
file_handlers = FileHandlers(db, bot)
search_handlers = SearchHandlers(db, bot)
settings_handlers = SettingsHandlers(db, bot)

# Инициализация командных обработчиков
from handlers.commands import init_handlers as init_command_handlers
init_command_handlers(db, bot)

# Регистрация роутеров
from handlers.commands import router as commands_router
from handlers.notes import router as notes_router
from handlers.reminders import router as reminders_router
from handlers.files import router as files_router
from handlers.search import router as search_router
from handlers.settings import router as settings_router

dp.include_router(commands_router)
dp.include_router(notes_router)
dp.include_router(reminders_router)
dp.include_router(files_router)
dp.include_router(search_router)
dp.include_router(settings_router)

# Инициализация других компонентов
productivity_analyzer = ProductivityAnalyzer(db)
report_generator = ReportGenerator(db)
task_manager = TaskManager(db)
progress_tracker = ProgressTracker(db)


# === СПЕЦИФИЧНЫЕ ОБРАБОТЧИКИ ДЛЯ bot_modular.py ===

# Обработчик инлайн-запросов
@dp.inline_query()
async def inline_query_handler(inline_query: InlineQuery):
    """Обработка инлайн-запросов"""
    try:
        query = inline_query.query.strip()
        user_id = inline_query.from_user.id

        if not query:
            # Показываем популярные заметки
            notes = await db.get_notes(user_id, limit=10)
            results = []

            for note in notes:
                title = note.get("title", "Без названия")[:50]
                content = note.get("content", "")[:100]

                results.append(
                    InlineQueryResultArticle(
                        id=str(note['id']),
                        title=title,
                        description=content,
                        input_message_content=InputTextMessageContent(
                            message_text=f"📝 {title}\n{content}",
                            parse_mode="HTML"
                        )
                    )
                )

            await inline_query.answer(results[:10], cache_time=30)
            return

        # Поиск заметок
        search_results = await search_handlers.search_notes(query, user_id, limit=10)

        if search_results:
            results = []
            for note in search_results:
                title = note.get("title", "Без названия")[:50]
                content = note.get("content", "")[:100]

                results.append(
                    InlineQueryResultArticle(
                        id=str(note['id']),
                        title=title,
                        description=content,
                        input_message_content=InputTextMessageContent(
                            message_text=f"📝 {title}\n{content}",
                            parse_mode="HTML"
                        )
                    )
                )

            await inline_query.answer(results[:10], cache_time=30)
        else:
            # Нет результатов
            await inline_query.answer([
                InlineQueryResultArticle(
                    id="no_results",
                    title="Ничего не найдено",
                    description=f"По запросу '{query}' ничего не найдено",
                    input_message_content=InputTextMessageContent(
                        message_text=f"❌ По запросу '{query}' ничего не найдено"
                    )
                )
            ], cache_time=30)

    except Exception as e:
        logger.error(f"Error in inline query: {e}")


# === ПЛАНИРОВЩИК НАПОМИНАНИЙ ===

async def reminder_scheduler():
    """Планировщик отправки напоминаний"""
    while True:
        try:
            await asyncio.sleep(60)  # Проверяем каждую минуту

            # Получаем активные напоминания
            active_reminders = await db.get_active_reminders()

            for reminder in active_reminders:
                try:
                    reminder_time = reminder.get('reminder_time')
                    if isinstance(reminder_time, str):
                        reminder_datetime = datetime.fromisoformat(reminder_time.replace('Z', '+00:00'))
                    else:
                        reminder_datetime = reminder_time

                    # Проверяем, пора ли отправлять напоминание
                    if reminder_datetime <= datetime.now():
                        user_id = reminder['user_id']
                        title = reminder.get('title', 'Напоминание')
                        content = reminder.get('content', '')

                        # Отправляем напоминание пользователю
                        try:
                            await bot.send_message(
                                user_id,
                                f"⏰ <b>Напоминание:</b>\n\n{title}\n{content}",
                                parse_mode="HTML"
                            )

                            # Деактивируем напоминание
                            await db.update_reminder(reminder['id'], user_id, is_active=False)

                            logger.info(f"Reminder sent to user {user_id}: {title}")

                        except Exception as e:
                            logger.error(f"Failed to send reminder to user {user_id}: {e}")

                except Exception as e:
                    logger.error(f"Error processing reminder {reminder.get('id')}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in reminder scheduler: {e}")
            await asyncio.sleep(60)


# === ОСНОВНАЯ ФУНКЦИЯ ===

async def main():
    """Основная функция запуска бота"""
    try:
        # Создаем директорию для данных, если её нет
        data_dir = BASE_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        await db.init_db()
        logger.info("База данных подготовлена")

        # Запускаем планировщик напоминаний
        asyncio.create_task(reminder_scheduler())
        logger.info("Планировщик напоминаний запущен")

        # Запускаем сервер мониторинга в фоне
        monitoring_port = int(os.getenv('MONITORING_PORT', '8080'))
        asyncio.create_task(start_monitoring_server(db, port=monitoring_port))
        logger.info(f"Сервер мониторинга запущен на порту {monitoring_port}")

        logger.info("🎉 NotesBot Professional стартует!")
        logger.info("📝 Заметки и напоминания готовы")
        logger.info("📁 Файлы под контролем")
        logger.info("📊 Аналитика подключена")
        logger.info("🔍 Мониторинг активен")
        logger.info("🤖 Приятной работы!")

        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запуске бота: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка по запросу пользователя")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
