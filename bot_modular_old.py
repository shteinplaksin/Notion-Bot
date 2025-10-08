"""
Модульный бот для NotesBot Professional с улучшенной архитектурой
"""

import asyncio
import logging
import json
import html
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

# Инициализация бота и диспетчера
BASE_DIR = Path(__file__).resolve().parent
db_path = Path(DATABASE_PATH)
if not db_path.is_absolute():
    db_path = BASE_DIR / db_path

fsm_storage_path = db_path.parent / f"{db_path.stem}_fsm.db"

bot = Bot(token=BOT_TOKEN)
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


# Универсальная функция для безопасного редактирования/отправки сообщений
async def safe_edit_or_send(message: Message, text: str, reply_markup=None, *, parse_mode: str = "HTML", edit: bool = True):
    """Безопасное редактирование или отправка сообщения"""
    if edit:
        try:
            await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


def parse_db_datetime(value: str) -> Optional[datetime]:
    """Parse datetime strings stored in the database."""
    if not value:
        return None
    normalized = value.replace('Z', '+00:00') if isinstance(value, str) else value
    try:
        return datetime.fromisoformat(normalized)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except Exception:
                continue
    return None


# === ОБРАБОТЧИКИ КОМАНД ===

# Обработчики команд перенесены в handlers/commands.py

# === ОБРАБОТЧИКИ КНОПОК ===

        await message.answer(welcome_text, reply_markup=Keyboards.main_menu(), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer("⚠️ Произошла ошибка при запуске бота.")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = """📚 <b>Справка по командам</b>

<b>Основные команды:</b>
/start - Запуск бота
/help - Эта справка
/new <текст> - Быстрое создание заметки
/notes - Управление заметками
/reminders - Напоминания
/search <запрос> - Поиск по заметкам
/files - Управление файлами
/settings - Настройки
/export - Экспорт всех заметок
/stats - Статистика продуктивности
/today - План на сегодня
/schedule - Подробное расписание

<b>Расширенные функции:</b>
/goals - Управление целями
/tasks - Повторяющиеся задачи
/report - Отчет о продуктивности
/timezone <смещение> - Установить часовой пояс

Используйте кнопки меню для удобного управления!"""

    await message.answer(help_text, parse_mode="HTML")


@dp.message(Command("new"))
async def cmd_new_note(message: Message, state: FSMContext):
    """Быстрое создание заметки"""
    try:
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            # Пытаемся извлечь время из текста
            text = args[1]
            reminder_time, remaining_text = parse_time_input(text)

            user_data_dict = get_user_data(message.from_user.id)
            user_data_dict['note_title'] = remaining_text[:50]
            user_data_dict['note_content'] = remaining_text
            user_data_dict['reminder_time'] = reminder_time

            if reminder_time:
                await message.answer(
                    f"📝 <b>Создание заметки с напоминанием</b>\n\n"
                    f"<b>Заголовок:</b> {remaining_text[:50]}\n"
                    f"<b>Напоминание:</b> {TimeParser().format_datetime(reminder_time)}\n\n"
                    f"Подтвердите создание:",
                    reply_markup=Keyboards.confirm_action("create_note_with_reminder", 0),
                    parse_mode="HTML"
                )
            else:
                # Создаем заметку сразу
                note_id = await db.add_note(
                    user_id=message.from_user.id,
                    title=remaining_text[:50],
                    content=remaining_text,
                    category="general"
                )

                activity_tracker.log_activity(message.from_user.id, "create_note")
                await db.log_user_activity(message.from_user.id, "create_note")

                await message.answer(
                    f"✅ <b>Заметка создана!</b>\n\n"
                    f"<b>ID:</b> {note_id}\n"
                    f"<b>Заголовок:</b> {remaining_text[:50]}",
                    parse_mode="HTML"
                )
        else:
            # Переходим к интерактивному созданию
            await notes_handlers.create_note_interactive(message, state)

    except Exception as e:
        logger.error(f"Error in new note command: {e}")
        await message.answer("❌ Ошибка при создании заметки.")


@dp.message(Command("notes"))
async def cmd_notes(message: Message):
    """Обработка команды /notes"""
    try:
        await notes_handlers.show_notes_menu(message, message.from_user.id, edit=False)
    except Exception as e:
        logger.error(f"Error getting notes: {e}")
        await message.answer("⚠️ Не удалось открыть раздел заметок.")


@dp.message(Command("reminders"))
async def cmd_reminders(message: Message):
    """Обработчик команды /reminders"""
    try:
        reminders = await db.get_active_reminders(message.from_user.id)

        if not reminders:
            await message.answer(
                "⏰ <b>Напоминания</b>\n\nУ вас нет активных напоминаний.",
                parse_mode="HTML"
            )
            return

        text = "⏰ <b>Активные напоминания:</b>\n\n"
        for reminder in reminders:
            text += f"<b>{reminder['title']}</b>\n"
            if reminder['content']:
                text += f"<i>{reminder['content']}</i>\n"
            text += f"🕐 {reminder['reminder_time'][:16]}\n\n"

        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error getting reminders: {e}")
        await message.answer("❌ Ошибка при получении напоминаний.")


@dp.message(Command("search"))
async def cmd_search(message: Message):
    """Обработчик команды /search"""
    try:
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            # Создаем временное сообщение для обработки поиска
            temp_message = message
            temp_message.text = args[1]
            await search_handlers.process_search_query(temp_message, message.from_user.id)
        else:
            await search_handlers.start_search(message, message.from_user.id, edit=False)
    except Exception as e:
        logger.error(f"Error in search command: {e}")
        await message.answer("❌ Ошибка при поиске.")


@dp.message(Command("files"))
async def cmd_files(message: Message):
    """Обработчик команды /files"""
    try:
        await file_handlers.show_files_menu(message, message.from_user.id, edit=False)
    except Exception as e:
        logger.error(f"Error getting files: {e}")
        await message.answer("❌ Ошибка при получении файлов.")


@dp.message(Command("settings"))
async def cmd_settings(message: Message):
    """Обработчик команды /settings"""
    try:
        await settings_handlers.show_settings_overview(message, message.from_user.id, edit=False)
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        await message.answer("❌ Ошибка при получении настроек.")


@dp.message(Command("timezone"))
async def cmd_timezone(message: Message):
    """Обработчик команды /timezone"""
    try:
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            await settings_handlers.set_timezone(message, args[1])
        else:
            await settings_handlers.show_timezone_settings(message, edit=False)
    except Exception as e:
        logger.error(f"Error in timezone command: {e}")
        await message.answer("❌ Ошибка при установке часового пояса.")


@dp.message(Command("export"))
async def cmd_export(message: Message):
    """Экспорт последних заметок в чат."""
    try:
        notes = await db.get_notes(message.from_user.id, limit=1000)
        if not notes:
            await message.answer("🗂️ У вас пока нет заметок для экспорта.")
            return

        export_text = [
            f"🗂️ <b>Экспорт заметок</b> — {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        ]
        for note in notes:
            pinned = "📌 " if note.get('is_pinned') else ''
            export_text.append(f"{pinned}<b>{note['title']}</b>")
            export_text.append(f"📁 Категория: {note['category']}")
            export_text.append(f"🕒 Создано: {note['created_at'][:16]}")
            if note.get('content'):
                export_text.append(note['content'])
            export_text.append('=' * 40)

        full_text = "\n".join(export_text)
        chunk_size = 3500
        if len(full_text) <= chunk_size:
            await message.answer(full_text, parse_mode="HTML")
        else:
            for idx in range(0, len(full_text), chunk_size):
                part = full_text[idx:idx + chunk_size]
                await message.answer(part, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in export command: {e}")
        await message.answer("⚠️ Не удалось выполнить экспорт заметок.")


@dp.message(Command("today"))
async def cmd_today(message: Message):
    """Краткое резюме задач и напоминаний на текущий день."""
    try:
        now = datetime.now()
        reminders = await db.get_active_reminders(message.from_user.id)
        todays = []
        for reminder in reminders:
            reminder_time = parse_db_datetime(reminder.get('reminder_time'))
            if reminder_time and reminder_time.date() == now.date():
                todays.append((reminder, reminder_time))

        schedule = await task_manager.get_daily_schedule(message.from_user.id, now.date())
        blocks = []
        for block in schedule.get('time_blocks', []):
            start_time = parse_db_datetime(block.get('start_time'))
            if start_time and start_time.date() == now.date():
                blocks.append((block, start_time))

        tasks = []
        for task in schedule.get('tasks', []):
            next_due = parse_db_datetime(task.get('next_due'))
            if next_due and next_due.date() == now.date():
                tasks.append((task, next_due))

        if not (todays or blocks or tasks):
            await message.answer("🗓️ На сегодня ничего не запланировано. Добавьте напоминание или блок времени!")
            return

        lines = [f"🗓️ <b>План на {now.strftime('%d.%m.%Y')}</b>\n"]
        if todays:
            lines.append("⏰ <b>Напоминания:</b>")
            for reminder, when in sorted(todays, key=lambda item: item[1]):
                lines.append(f"• {when.strftime('%H:%M')} — <b>{reminder['title']}</b>")
                if reminder.get('content'):
                    lines.append(f"  <i>{reminder['content']}</i>")
        if blocks:
            lines.append("\n🧩 <b>Блоки времени:</b>")
            for block, start_time in sorted(blocks, key=lambda item: item[1]):
                end_time = parse_db_datetime(block.get('end_time'))
                end_text = end_time.strftime('%H:%M') if end_time else '...'
                lines.append(f"• {start_time.strftime('%H:%M')}–{end_text} — <b>{block['title']}</b>")
                if block.get('description'):
                    lines.append(f"  <i>{block['description']}</i>")
        if tasks:
            lines.append("\n✅ <b>Повторяющиеся задачи:</b>")
            for task, next_due in sorted(tasks, key=lambda item: item[1]):
                priority = task.get('priority', 'medium')
                lines.append(f"• {next_due.strftime('%H:%M')} — <b>{task['title']}</b> ({priority})")
        lines.append("\nУдачного дня!")

        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in today command: {e}")
        await message.answer("⚠️ Не удалось сформировать план на сегодня.")


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика продуктивности пользователя."""
    try:
        period = 30
        args = message.text.split(maxsplit=1)
        if len(args) > 1 and args[1].isdigit():
            period = max(7, min(180, int(args[1])))
        metrics = await productivity_analyzer.analyze_user_productivity(message.from_user.id, period)
        if not metrics:
            await message.answer("📊 Пока недостаточно данных для статистики.")
            return

        category = metrics.get('category_distribution', {})
        most_used = category.get('most_used', ('general', 0))
        time_patterns = metrics.get('time_patterns', {})
        report_lines = [
            f"📊 <b>Статистика за {period} дней</b>",
            f"• Всего заметок: {metrics.get('total_notes', 0)}",
            f"• Создано за период: {metrics.get('recent_notes', 0)}",
            f"• Активных напоминаний: {metrics.get('total_reminders', 0)}",
            f"• Среднее в день: {metrics.get('notes_per_day', 0):.1f}",
            f"• Индекс активности: {metrics.get('activity_score', 0):.1f}",
            f"• Завершено напоминаний: {metrics.get('completion_rate', 0):.1f}%",
            f"• Частая категория: {most_used[0]} ({most_used[1]})"
        ]
        if time_patterns:
            report_lines.append(
                f"• Пик активности: {time_patterns.get('peak_hour', 9)}:00, {time_patterns.get('peak_weekday', 'пн')}"
            )

        await message.answer("\n".join(report_lines), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await message.answer("⚠️ Не удалось получить статистику.")


# === ОБРАБОТЧИКИ КНОПОК ===

# Кнопки основного меню
@dp.message(F.text == "📋 Мои заметки")
async def handle_my_notes(message: Message):
    """Обработка кнопки просмотра заметок."""
    await notes_handlers.show_notes_list(message, message.from_user.id, list_type="all", edit=False)


@dp.message(F.text == "⏰ Напоминания")
async def handle_reminders(message: Message):
    """Обработка выбора раздела напоминаний"""
    await reminder_handlers.show_reminders_menu(message, edit=False)


@dp.message(F.text == "🔍 Поиск")
async def handle_search(message: Message):
    """Обработчик кнопки поиска"""
    await search_handlers.start_search(message, message.from_user.id, edit=False)


@dp.message(F.text == "📁 Категории")
async def handle_categories(message: Message):
    """Обработчик кнопки категорий"""
    try:
        categories = await db.get_categories(message.from_user.id)

        if not categories:
            await message.answer(
                "📁 <b>Категории</b>\n\nУ вас пока нет категорий.\nСоздайте первую категорию!",
                parse_mode="HTML"
            )
            return

        text = "📁 <b>Ваши категории:</b>\n\n"
        for category in categories:
            # Подсчитываем количество заметок в категории
            notes = await db.get_notes(message.from_user.id, category=category['name'])
            notes_count = len(notes)

            text += f"📁 <b>{category['name']}</b>\n"
            text += f"   📝 Заметок: {notes_count}\n"
            text += f"   🎨 Цвет: {category['color']}\n\n"

        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        await message.answer("❌ Ошибка при получении категорий.")


@dp.message(F.text == "⚙️ Настройки")
async def handle_settings(message: Message):
    """Обработчик кнопки настроек"""
    await settings_handlers.show_settings_overview(message, message.from_user.id, edit=False)


# === ОБРАБОТЧИКИ CALLBACK QUERY ===

# Обработчики заметок
@dp.callback_query(F.data == "notes_menu")
async def callback_notes_menu(callback: CallbackQuery):
    await callback.answer()
    await notes_handlers.show_notes_menu(callback.message, callback.from_user.id, edit=True)


@dp.callback_query(F.data == "notes_close")
async def callback_notes_close(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_reply_markup()
        except Exception:
            pass


@dp.callback_query(F.data == "list_notes")
async def callback_list_notes(callback: CallbackQuery):
    await callback.answer()
    await notes_handlers.show_notes_list(callback.message, callback.from_user.id, list_type="all", edit=True)


@dp.callback_query(F.data == "pinned_notes")
async def callback_pinned_notes(callback: CallbackQuery):
    await callback.answer()
    await notes_handlers.show_notes_list(callback.message, callback.from_user.id, list_type="pinned", edit=True)


@dp.callback_query(F.data == "search_notes")
async def callback_search_notes(callback: CallbackQuery):
    await callback.answer()
    await search_handlers.start_search(callback.message, callback.from_user.id, edit=True)


@dp.callback_query(F.data == "create_note")
async def callback_create_note(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await notes_handlers.create_note_interactive(callback.message, state)


@dp.callback_query(F.data.startswith("create_note_start_"))
async def callback_create_note_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    origin = callback.data.replace("create_note_start_", "", 1) or "menu"
    await state.set_state(NoteStates.waiting_for_title)
    await state.update_data(note_creation_origin=origin, note_creation_list=origin)
    prompt = "📝 <b>Шаг 1.</b> Введите заголовок заметки (до 100 символов)."
    await safe_edit_or_send(
        callback.message,
        prompt,
        reply_markup=Keyboards.note_title_prompt(back_callback=f"cancel_note_creation_{origin}"),
        edit=True
    )


@dp.callback_query(F.data.startswith("cancel_note_creation_"))
async def callback_cancel_note_creation(callback: CallbackQuery, state: FSMContext):
    origin = callback.data.replace("cancel_note_creation_", "", 1) or "menu"
    await state.clear()
    await callback.answer("Создание отменено")
    if origin == "menu":
        await notes_handlers.show_notes_menu(callback.message, callback.from_user.id, edit=True)
    else:
        try:
            await callback.message.edit_reply_markup()
        except Exception:
            pass


@dp.callback_query(F.data.startswith("notes_list_"))
async def callback_notes_list_navigation(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split('_', 2)
    list_type = parts[2] if len(parts) > 2 else "all"
    await notes_handlers.show_notes_list(callback.message, callback.from_user.id, list_type=list_type, edit=True)


@dp.callback_query(F.data.startswith("notes_page_"))
async def callback_notes_pagination(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split('_', 3)
    list_type = parts[2] if len(parts) > 2 else "all"
    try:
        page = int(parts[3]) if len(parts) > 3 else 0
    except ValueError:
        page = 0
    await notes_handlers.show_notes_list(callback.message, callback.from_user.id, list_type=list_type, page=page, edit=True)


@dp.callback_query(F.data.startswith("open_note_"))
async def callback_open_note(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split('_')
    if len(parts) < 4:
        await callback.answer("Не удалось открыть заметку", show_alert=True)
        return
    list_type = parts[2]
    try:
        note_id = int(parts[3])
    except ValueError:
        await callback.answer("Некорректный идентификатор", show_alert=True)
        return
    found = await notes_handlers.show_note_detail(callback.message, callback.from_user.id, note_id, list_type=list_type, edit=True)
    if not found:
        await callback.answer("Заметка не найдена", show_alert=True)


@dp.callback_query(F.data.startswith("toggle_pin_"))
async def callback_toggle_pin(callback: CallbackQuery):
    parts = callback.data.split('_')
    try:
        note_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный идентификатор", show_alert=True)
        return
    await notes_handlers.toggle_pin_note(callback, note_id)


@dp.callback_query(F.data.startswith("edit_note_"))
async def callback_edit_note(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split('_')
    try:
        note_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный идентификатор", show_alert=True)
        return
    await notes_handlers.edit_note_start(callback, state, note_id)


@dp.callback_query(F.data.startswith("cancel_edit_note_"))
async def callback_cancel_edit_note(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    parts = callback.data.split('_')
    try:
        note_id = int(parts[-1])
    except ValueError:
        await callback.answer()
        return
    await callback.answer("Редактирование отменено")
    user_id = callback.from_user.id
    list_type = get_user_data(user_id).get("notes_last_list_type", "all")
    await notes_handlers.show_note_detail(callback.message, user_id, note_id, list_type=list_type, edit=True)


@dp.callback_query(F.data.startswith("delete_note_"))
async def callback_delete_note(callback: CallbackQuery):
    parts = callback.data.split('_')
    try:
        note_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный идентификатор", show_alert=True)
        return
    await notes_handlers.delete_note_confirm(callback, note_id)


@dp.callback_query(F.data.startswith("confirm_delete_note_"))
async def callback_confirm_delete_note(callback: CallbackQuery):
    parts = callback.data.split('_')
    try:
        note_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный идентификатор", show_alert=True)
        return
    await notes_handlers.delete_note_execute(callback, note_id)


@dp.callback_query(F.data.startswith("cancel_delete_note_"))
async def callback_cancel_delete_note(callback: CallbackQuery):
    parts = callback.data.split('_')
    try:
        note_id = int(parts[-1])
    except ValueError:
        await callback.answer()
        return
    await callback.answer("Отменено")
    user_id = callback.from_user.id
    list_type = get_user_data(user_id).get("notes_last_list_type", "all")
    await notes_handlers.show_note_detail(callback.message, user_id, note_id, list_type=list_type, edit=True)


# === ОБРАБОТЧИКИ СОСТОЯНИЙ FSM ===

@dp.message(NoteStates.waiting_for_title)
async def process_note_title(message: Message, state: FSMContext):
    """Обработка заголовка заметки"""
    await notes_handlers.process_note_title(message, state)


@dp.message(NoteStates.waiting_for_content)
async def process_note_content(message: Message, state: FSMContext):
    """Обработка содержимого заметки"""
    await notes_handlers.process_note_content(message, state)


@dp.message(NoteStates.editing_note)
async def process_edit_note_title(message: Message, state: FSMContext):
    """Обработка нового заголовка при редактировании заметки"""
    await notes_handlers.process_edit_note_title(message, state)


@dp.message(NoteStates.editing_content)
async def process_edit_note_content(message: Message, state: FSMContext):
    """Обработка обновления содержания заметки"""
    await notes_handlers.process_edit_note_content(message, state)


# === ОБРАБОТЧИКИ СОСТОЯНИЙ НАПОМИНАНИЙ ===

@dp.message(ReminderStates.waiting_for_reminder_title)
async def process_reminder_title(message: Message, state: FSMContext):
    """Обработка заголовка напоминания"""
    await state.update_data(reminder_title=message.text)
    await message.answer(
        "📝 <b>Заголовок установлен</b>\n\nТеперь введите текст напоминания или выберите действие:",
        reply_markup=Keyboards.reminder_creation_menu(),
        parse_mode="HTML"
    )


@dp.message(ReminderStates.waiting_for_reminder_text)
async def process_reminder_text(message: Message, state: FSMContext):
    """Обработка текста напоминания"""
    await state.update_data(reminder_text=message.text)
    await message.answer(
        "✅ <b>Текст установлен</b>\n\nТеперь выберите время напоминания:",
        reply_markup=Keyboards.time_presets(),
        parse_mode="HTML"
    )


@dp.message(ReminderStates.waiting_for_reminder_time)
async def process_reminder_time(message: Message, state: FSMContext):
    """Обработка времени напоминания"""
    try:
        # Пытаемся разобрать время
        time_input = message.text.strip()
        parsed_time = parse_time_input(time_input)

        if parsed_time:
            await state.update_data(reminder_time=parsed_time)
            await message.answer(
                f"⏰ <b>Время установлено</b>\n\n"
                f"<b>Напоминание:</b> {TimeParser().format_datetime(parsed_time)}\n\n"
                f"Теперь выберите тип повтора или завершите создание:",
                reply_markup=Keyboards.repeat_options(),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ <b>Неверный формат времени</b>\n\n"
                "Используйте формат:\n"
                "• <code>через 5 минут</code>\n"
                "• <code>завтра в 15:30</code>\n"
                "• <code>2024-01-15 10:00</code>\n\n"
                "Попробуйте еще раз:",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error parsing reminder time: {e}")
        await message.answer(
            "❌ <b>Ошибка обработки времени</b>\n\nПопробуйте еще раз.",
            parse_mode="HTML"
        )


@dp.message(ReminderStates.waiting_for_reminder_repeat)
async def process_reminder_repeat(message: Message, state: FSMContext):
    """Обработка типа повтора напоминания"""
    text = message.text.strip().lower()
    repeat_map = {
        "нет": ("none", 1),
        "без повтора": ("none", 1),
        "ежедневно": ("daily", 1),
        "каждый день": ("daily", 1),
        "еженедельно": ("weekly", 1),
        "каждую неделю": ("weekly", 1),
        "ежемесячно": ("monthly", 1),
        "каждый месяц": ("monthly", 1)
    }

    if text in repeat_map:
        repeat_type, repeat_interval = repeat_map[text]
        await state.update_data(repeat_type=repeat_type, repeat_interval=repeat_interval)
        await message.answer(
            f"🔁 <b>Повтор установлен</b>\n\n"
            f"<b>Тип:</b> {text.title()}\n\n"
            f"Теперь завершите создание напоминания:",
            reply_markup=Keyboards.reminder_creation_menu(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ <b>Неверный тип повтора</b>\n\n"
            "Выберите из предложенных вариантов или введите:\n"
            "• Без повтора\n"
            "• Ежедневно\n"
            "• Еженедельно\n"
            "• Ежемесячно",
            parse_mode="HTML"
        )


@dp.message(CategoryStates.waiting_for_name)
async def process_category_name(message: Message, state: FSMContext):
    """Обработка названия категории"""
    try:
        category_name = message.text.strip()
        if len(category_name) < 2:
            await message.answer(
                "❌ <b>Слишком короткое название</b>\n\nНазвание категории должно содержать минимум 2 символа.",
                parse_mode="HTML"
            )
            return

        if len(category_name) > 50:
            await message.answer(
                "❌ <b>Слишком длинное название</b>\n\nНазвание категории не должно превышать 50 символов.",
                parse_mode="HTML"
            )
            return

        # Создаем категорию
        category_id = await db.add_category(
            user_id=message.from_user.id,
            name=category_name,
            color="#3498db"  # Синий цвет по умолчанию
        )

        await state.clear()
        await message.answer(
            f"✅ <b>Категория создана!</b>\n\n"
            f"<b>Название:</b> {html.escape(category_name)}\n"
            f"<b>ID:</b> {category_id}\n\n"
            f"Теперь вы можете создавать заметки в этой категории.",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error creating category: {e}")
        await message.answer(
            "❌ <b>Ошибка при создании категории</b>\n\nПопробуйте еще раз.",
            parse_mode="HTML"
        )


# === ОБРАБОТЧИКИ ФАЙЛОВ ===

@dp.message(F.photo)
async def handle_photo(message: Message):
    """Обработка изображений"""
    await file_handlers.handle_photo_upload(message, message.from_user.id)


@dp.message(F.document)
async def handle_document(message: Message):
    """Обработка документов"""
    await file_handlers.handle_document_upload(message, message.from_user.id)


@dp.message(F.voice)
async def handle_voice(message: Message):
    """Обработка голосовых сообщений"""
    try:
        # Проверяем rate limit
        access_check = await security_manager.check_user_access(message.from_user.id, "file")
        if not access_check['allowed']:
            await message.answer(f"⚠️ {access_check['reason']}")
            return

        voice = message.voice
        file_info = await bot.get_file(voice.file_id)
        file_content = await bot.download_file(file_info.file_path)

        # Сохраняем аудио файл
        save_result = await file_manager.save_file(
            file_content.read(),
            f"voice_{voice.file_id}.ogg",
            'audio',
            message.from_user.id
        )

        if save_result['success']:
            await message.answer("🎤 Обрабатываю голосовое сообщение...")

            # Конвертируем в текст (упрощенная версия)
            text_result = await voice_converter.convert_voice_to_text(save_result['file_path'])

            if text_result['success']:
                # Создаем заметку из распознанного текста
                note_id = await db.add_note(
                    user_id=message.from_user.id,
                    title=f"Голосовая заметка {datetime.now().strftime('%d.%m %H:%M')}",
                    content=text_result['text'],
                    category="voice"
                )

                activity_tracker.log_activity(message.from_user.id, "voice_note")
                await db.log_user_activity(message.from_user.id, "voice_note")

                await message.answer(
                    f"🎤 <b>Голосовое сообщение обработано!</b>\n\n"
                    f"📝 <b>Содержимое:</b>\n<code>{text_result['text']}</code>\n\n"
                    f"✅ Создана заметка #{note_id}",
                    parse_mode="HTML"
                )
            else:
                await message.answer(f"❌ Не удалось обработать голос: {text_result['error']}")
        else:
            await message.answer(f"❌ Ошибка сохранения аудио: {save_result['error']}")

    except Exception as e:
        logger.error(f"Error handling voice: {e}")
        await message.answer("❌ Произошла ошибка при обработке голосового сообщения.")


# === ОБРАБОТЧИКИ НАПОМИНАНИЙ ===

@dp.message(Command("remind"))
async def cmd_remind(message: Message, state: FSMContext):
    """Быстрое создание напоминания"""
    try:
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            await reminder_handlers.quick_reminder_creation(message)
        else:
            await state.set_state(ReminderStates.waiting_for_reminder_title)
            await message.answer(
                "⏰ <b>Создание напоминания</b>\n\nВведите заголовок напоминания:",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error in remind command: {e}")
        await message.answer("❌ Ошибка при создании напоминания.")


@dp.callback_query(F.data == "create_reminder")
async def callback_create_reminder(callback: CallbackQuery, state: FSMContext):
    await reminder_handlers.start_reminder_creation(callback.message, state)


@dp.callback_query(F.data == "active_reminders")
async def callback_active_reminders(callback: CallbackQuery):
    await callback.answer()
    await reminder_handlers.show_active_reminders(callback.message, callback.from_user.id, edit=True)


@dp.callback_query(F.data == "today_reminders")
async def callback_today_reminders(callback: CallbackQuery):
    await callback.answer()
    await reminder_handlers.show_today_reminders(callback.message, callback.from_user.id, edit=True)


@dp.callback_query(F.data == "week_reminders")
async def callback_week_reminders(callback: CallbackQuery):
    await callback.answer()
    await reminder_handlers.show_week_reminders(callback.message, callback.from_user.id, edit=True)


@dp.callback_query(F.data == "manage_reminders")
async def callback_manage_reminders(callback: CallbackQuery):
    await callback.answer()
    text = (
        "🛠 <b>Управление напоминаниями</b>\n\n"
        "Используйте команды:\n"
        "• <code>/reminders</code> — список активных напоминаний\n"
        "• <code>/today</code> — планы на сегодня\n"
        "• <code>/remind</code> — создать новое напоминание"
    )
    await safe_edit_or_send(
        callback.message,
        text,
        reply_markup=Keyboards.reminders_menu(),
        edit=True
    )


@dp.callback_query(F.data == "reminders_close")
async def callback_reminders_close(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_reply_markup()
        except Exception:
            pass


# === ОБРАБОТЧИКИ ПОИСКА ===

@dp.message(lambda message: get_user_data(message.from_user.id).get("awaiting_note_search"))
async def handle_inline_note_search(message: Message):
    """Обработка ввода поискового запроса из инлайн-режима заметок"""
    user_data_dict = get_user_data(message.from_user.id)
    if not user_data_dict.pop("awaiting_note_search", False):
        return
    await search_handlers.process_search_query(message, message.from_user.id)


# === ОБРАБОТЧИКИ НАСТРОЕК ===

@dp.callback_query(F.data == "settings_close")
async def callback_settings_close(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_reply_markup()
        except Exception:
            pass


@dp.callback_query(F.data == "timezone_settings")
async def callback_timezone_settings(callback: CallbackQuery):
    await callback.answer()
    await settings_handlers.show_timezone_settings(callback.message, edit=True)


@dp.callback_query(F.data == "notification_settings")
async def callback_notification_settings(callback: CallbackQuery):
    await callback.answer()
    await settings_handlers.show_notification_settings(callback.message, edit=True)


@dp.callback_query(F.data == "export_data")
async def callback_export_data(callback: CallbackQuery):
    await callback.answer()
    await settings_handlers.show_export_settings(callback.message, edit=True)


@dp.callback_query(F.data == "clear_data")
async def callback_clear_data(callback: CallbackQuery):
    await callback.answer()
    await settings_handlers.show_data_management(callback.message, edit=True)


@dp.callback_query(F.data == "help")
async def callback_settings_help(callback: CallbackQuery):
    await callback.answer()
    await settings_handlers.show_help_settings(callback.message, edit=True)


@dp.callback_query(F.data == "statistics")
async def callback_statistics(callback: CallbackQuery):
    """Callback для статистики"""
    await settings_handlers.show_statistics_settings(callback.message, callback.from_user.id, edit=True)


@dp.callback_query(F.data == "export_notes")
async def callback_export_notes(callback: CallbackQuery):
    """Callback для экспорта заметок"""
    await settings_handlers.show_export_notes_settings(callback.message, callback.from_user.id, edit=True)


# === ДОПОЛНИТЕЛЬНЫЕ ОБРАБОТЧИКИ ГЛАВНОГО МЕНЮ ===

@dp.callback_query(F.data == "main_notes")
async def callback_main_notes(callback: CallbackQuery):
    await callback.answer()
    await notes_handlers.show_notes_menu(callback.message, callback.from_user.id, edit=True)


@dp.callback_query(F.data == "main_reminders")
async def callback_main_reminders(callback: CallbackQuery):
    await callback.answer()
    await reminder_handlers.show_reminders_menu(callback.message, edit=True)


@dp.callback_query(F.data == "main_files")
async def callback_main_files(callback: CallbackQuery):
    await callback.answer()
    await file_handlers.show_files_menu(callback.message, callback.from_user.id, edit=True)


@dp.callback_query(F.data == "main_settings")
async def callback_main_settings(callback: CallbackQuery):
    await callback.answer()
    await settings_handlers.show_settings_overview(callback.message, callback.from_user.id, edit=True)


@dp.callback_query(F.data == "main_search")
async def callback_main_search(callback: CallbackQuery):
    await callback.answer()
    await search_handlers.start_search(callback.message, callback.from_user.id, edit=True)


@dp.callback_query(F.data == "main_categories")
async def callback_main_categories(callback: CallbackQuery):
    await callback.answer()
    # Показываем категории заметок
    categories = await db.get_categories(callback.from_user.id)
    if not categories:
        await callback.message.edit_text(
            "📁 <b>Категории</b>\n\nУ вас пока нет категорий.\nСоздайте первую категорию!",
            parse_mode="HTML"
        )
        return

    text = "📁 <b>Ваши категории:</b>\n\n"
    for category in categories:
        notes = await db.get_notes(callback.from_user.id, category=category['name'])
        notes_count = len(notes)
        text += f"📁 <b>{category['name']}</b>\n"
        text += f"   📝 Заметок: {notes_count}\n"
        text += f"   🎨 Цвет: {category['color']}\n\n"

    await callback.message.edit_text(text, parse_mode="HTML")


# === ОБРАБОТЧИКИ КАТЕГОРИЙ ===

@dp.callback_query(F.data == "categories")
async def callback_categories(callback: CallbackQuery):
    await callback.answer()
    categories = await db.get_categories(callback.from_user.id)

    if not categories:
        await callback.message.edit_text(
            "📁 <b>Категории</b>\n\nУ вас пока нет категорий.\nСоздайте первую категорию!",
            parse_mode="HTML"
        )
        return

    text = "📁 <b>Ваши категории:</b>\n\n"
    for category in categories:
        notes = await db.get_notes(callback.from_user.id, category=category['name'])
        notes_count = len(notes)
        text += f"📁 <b>{category['name']}</b>\n"
        text += f"   📝 Заметок: {notes_count}\n"
        text += f"   🎨 Цвет: {category['color']}\n\n"

    await callback.message.edit_text(text, parse_mode="HTML")


@dp.callback_query(F.data.startswith("select_category_"))
async def callback_select_category(callback: CallbackQuery):
    await callback.answer()
    category_id = int(callback.data.replace("select_category_", ""))
    # Получаем категорию по ID
    categories = await db.get_categories(callback.from_user.id)
    selected_category = next((cat for cat in categories if cat['id'] == category_id), None)

    if not selected_category:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    # Показываем заметки в категории
    notes = await db.get_notes(callback.from_user.id, category=selected_category['name'], limit=50)
    if not notes:
        await callback.message.edit_text(
            f"📁 <b>Категория: {selected_category['name']}</b>\n\nВ этой категории пока нет заметок.",
            parse_mode="HTML"
        )
        return

    text = f"📁 <b>Категория: {selected_category['name']}</b>\n\n"
    for note in notes[:10]:
        title = (note.get("title") or "Без названия").strip() or "Без названия"
        text += f"• <b>{html.escape(title)}</b>\n"
        content = (note.get("content") or "").strip()
        if content:
            preview = content.replace("\n", " ")
            if len(preview) > 80:
                preview = preview[:77].rstrip() + "…"
            text += f"  {html.escape(preview)}\n"

    text += "\nОткройте заметку кнопкой ниже или создайте новую запись."
    markup = Keyboards.notes_list(notes[:20], list_type=f"category:{selected_category['name']}")
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@dp.callback_query(F.data == "create_category")
async def callback_create_category(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(CategoryStates.waiting_for_name)
    await callback.message.edit_text(
        "📁 <b>Создание категории</b>\n\nВведите название новой категории:",
        parse_mode="HTML"
    )


# === ОБРАБОТЧИКИ НАПОМИНАНИЙ О ЗАМЕТКАХ ===

@dp.callback_query(F.data.startswith("remind_note_"))
async def callback_remind_note(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split('_')
    try:
        note_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Некорректный идентификатор заметки", show_alert=True)
        return

    # Получаем информацию о заметке
    note = await db.get_note(note_id, callback.from_user.id)
    if not note:
        await callback.answer("Заметка не найдена", show_alert=True)
        return

    await state.set_state(ReminderStates.waiting_for_reminder_time)
    await state.update_data(note_id=note_id, reminder_title=note.get('title', 'Без названия'))

    await callback.message.edit_text(
        f"⏰ <b>Создание напоминания для заметки</b>\n\n"
        f"<b>Заметка:</b> {note.get('title', 'Без названия')}\n\n"
        f"Выберите время напоминания или введите его вручную:",
        reply_markup=Keyboards.time_presets(),
        parse_mode="HTML"
    )


# === ОБРАБОТЧИКИ СОЗДАНИЯ НАПОМИНАНИЙ ===

@dp.callback_query(F.data == "set_reminder_text")
async def callback_set_reminder_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ReminderStates.waiting_for_reminder_text)
    await callback.message.edit_text(
        "📝 <b>Текст напоминания</b>\n\nВведите текст напоминания:",
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "set_reminder_time")
async def callback_set_reminder_time(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ReminderStates.waiting_for_reminder_time)
    await callback.message.edit_text(
        "⏰ <b>Время напоминания</b>\n\nВведите время в формате:\n"
        "• <code>через 5 минут</code>\n"
        "• <code>завтра в 15:30</code>\n"
        "• <code>2024-01-15 10:00</code>\n\n"
        "Или выберите быстрый вариант:",
        reply_markup=Keyboards.time_presets(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "set_reminder_repeat")
async def callback_set_reminder_repeat(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ReminderStates.waiting_for_reminder_repeat)
    await callback.message.edit_text(
        "🔁 <b>Повтор напоминания</b>\n\nВыберите тип повтора:",
        reply_markup=Keyboards.repeat_options(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "finish_reminder_creation")
async def callback_finish_reminder_creation(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_data = await state.get_data()

    # Проверяем обязательные поля
    if not all(key in user_data for key in ['reminder_title', 'reminder_time']):
        await callback.message.edit_text(
            "❌ <b>Ошибка</b>\n\nНе все поля заполнены. Попробуйте создать напоминание заново.",
            parse_mode="HTML"
        )
        return

    try:
        # Создаем напоминание
        reminder_id = await db.add_reminder(
            user_id=callback.from_user.id,
            title=user_data['reminder_title'],
            content=user_data.get('reminder_text', ''),
            reminder_time=user_data['reminder_time'].strftime("%Y-%m-%d %H:%M:%S"),
            repeat_type=user_data.get('repeat_type', 'none'),
            repeat_interval=user_data.get('repeat_interval', 1)
        )

        await state.clear()
        await callback.message.edit_text(
            f"✅ <b>Напоминание создано!</b>\n\n"
            f"<b>Заголовок:</b> {user_data['reminder_title']}\n"
            f"<b>Время:</b> {TimeParser().format_datetime(user_data['reminder_time'])}\n"
            f"<b>ID:</b> {reminder_id}",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error creating reminder: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка при создании напоминания</b>\n\nПопробуйте еще раз.",
            parse_mode="HTML"
        )


@dp.callback_query(F.data == "cancel_reminder_creation")
async def callback_cancel_reminder_creation(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Создание отменено")
    await state.clear()
    await reminder_handlers.show_reminders_menu(callback.message, edit=True)


# === ОБРАБОТЧИКИ ВРЕМЕНИ ===

@dp.callback_query(F.data.startswith("time_"))
async def callback_time_preset(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    time_map = {
        "time_5min": timedelta(minutes=5),
        "time_15min": timedelta(minutes=15),
        "time_30min": timedelta(minutes=30),
        "time_1hour": timedelta(hours=1),
        "time_tomorrow": timedelta(days=1),
        "time_day_after": timedelta(days=2)
    }

    preset = callback.data
    if preset in time_map:
        reminder_time = datetime.now() + time_map[preset]

        # Сохраняем время в состояние
        await state.update_data(reminder_time=reminder_time)

        # Возвращаемся к созданию напоминания
        await callback.message.edit_text(
            f"⏰ <b>Время установлено</b>\n\n"
            f"<b>Напоминание:</b> {TimeParser().format_datetime(reminder_time)}\n\n"
            f"Теперь введите текст напоминания или выберите действие:",
            reply_markup=Keyboards.reminder_creation_menu(),
            parse_mode="HTML"
        )


# === ОБРАБОТЧИКИ ПОВТОРА ===

@dp.callback_query(F.data.startswith("repeat_"))
async def callback_repeat_option(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    repeat_map = {
        "repeat_none": ("none", 1),
        "repeat_daily": ("daily", 1),
        "repeat_weekly": ("weekly", 1),
        "repeat_monthly": ("monthly", 1)
    }

    option = callback.data
    if option in repeat_map:
        repeat_type, repeat_interval = repeat_map[option]
        await state.update_data(repeat_type=repeat_type, repeat_interval=repeat_interval)

        await callback.message.edit_text(
            f"🔁 <b>Повтор установлен</b>\n\n"
            f"<b>Тип:</b> {option.replace('repeat_', '').title()}\n\n"
            f"Теперь завершите создание напоминания:",
            reply_markup=Keyboards.reminder_creation_menu(),
            parse_mode="HTML"
        )


# === ОБРАБОТЧИКИ ФАЙЛОВ ===

@dp.callback_query(F.data == "files_images")
async def callback_files_images(callback: CallbackQuery):
    await callback.answer()
    await file_handlers.show_files_by_type(callback.message, callback.from_user.id, "image", edit=True)


@dp.callback_query(F.data == "files_documents")
async def callback_files_documents(callback: CallbackQuery):
    await callback.answer()
    await file_handlers.show_files_by_type(callback.message, callback.from_user.id, "document", edit=True)


@dp.callback_query(F.data == "files_audio")
async def callback_files_audio(callback: CallbackQuery):
    await callback.answer()
    await file_handlers.show_files_by_type(callback.message, callback.from_user.id, "audio", edit=True)


@dp.callback_query(F.data == "files_archives")
async def callback_files_archives(callback: CallbackQuery):
    await callback.answer()
    await file_handlers.show_files_by_type(callback.message, callback.from_user.id, "archive", edit=True)


@dp.callback_query(F.data == "upload_file")
async def callback_upload_file(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "📤 <b>Загрузка файла</b>\n\n"
        "Отправьте мне файл (изображение, документ, аудио).\n\n"
        "Поддерживаемые типы:\n"
        "• 📸 Изображения (JPEG, PNG, GIF, WebP)\n"
        "• 📄 Документы (PDF, DOC, TXT и др.)\n"
        "• 🎵 Аудио (MP3, OGG, WAV)\n"
        "• 📦 Архивы (ZIP, RAR, 7Z)",
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "files_close")
async def callback_files_close(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_reply_markup()
        except Exception:
            pass


# === ОБРАБОТЧИКИ ПОИСКА ===

@dp.callback_query(F.data.startswith("search_again_"))
async def callback_search_again(callback: CallbackQuery):
    await callback.answer()
    query = callback.data.replace("search_again_", "", 1)
    # Создаем временное сообщение для обработки поиска
    temp_message = callback.message
    temp_message.text = query
    await search_handlers.process_search_query(temp_message, callback.from_user.id)


@dp.callback_query(F.data == "advanced_search")
async def callback_advanced_search(callback: CallbackQuery):
    await callback.answer()
    await search_handlers.advanced_search(callback.message, callback.from_user.id)


# === ОБРАБОТЧИКИ ДЕЙСТВИЙ С НАПОМИНАНИЯМИ ===

@dp.callback_query(F.data.startswith("edit_reminder_"))
async def callback_edit_reminder(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split('_')
    try:
        reminder_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Некорректный идентификатор", show_alert=True)
        return

    # Показываем детали напоминания для редактирования
    await callback.message.edit_text(
        f"✏️ <b>Редактирование напоминания #{reminder_id}</b>\n\n"
        "Функция редактирования находится в разработке.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("snooze_reminder_"))
async def callback_snooze_reminder(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split('_')
    try:
        reminder_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Некорректный идентификатор", show_alert=True)
        return

    # Откладываем напоминание на час
    await callback.message.edit_text(
        f"😴 <b>Напоминание отложено</b>\n\n"
        f"Напоминание #{reminder_id} отложено на 1 час.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("complete_reminder_"))
async def callback_complete_reminder(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split('_')
    try:
        reminder_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Некорректный идентификатор", show_alert=True)
        return

    # Помечаем напоминание как выполненное
    await callback.message.edit_text(
        f"✅ <b>Напоминание выполнено</b>\n\n"
        f"Напоминание #{reminder_id} помечено как выполненное.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("delete_reminder_"))
async def callback_delete_reminder(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split('_')
    try:
        reminder_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Некорректный идентификатор", show_alert=True)
        return

    await callback.message.edit_text(
        f"🗑 <b>Подтверждение удаления</b>\n\n"
        f"Вы уверены, что хотите удалить напоминание #{reminder_id}?\n\n"
        f"Это действие нельзя отменить.",
        reply_markup=Keyboards.confirm_action("delete_reminder", reminder_id),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("confirm_delete_reminder_"))
async def callback_confirm_delete_reminder(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split('_')
    try:
        reminder_id = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("Некорректный идентификатор", show_alert=True)
        return

    # Удаляем напоминание
    await callback.message.edit_text(
        f"🗑 <b>Напоминание удалено</b>\n\n"
        f"Напоминание #{reminder_id} успешно удалено.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("cancel_delete_reminder_"))
async def callback_cancel_delete_reminder(callback: CallbackQuery):
    await callback.answer("Отменено")
    await reminder_handlers.show_reminders_menu(callback.message, edit=True)


# === ПРОЧИЕ ОБРАБОТЧИКИ ===

@dp.callback_query(F.data == "notes_empty")
async def callback_notes_empty(callback: CallbackQuery):
    await callback.answer()
    await notes_handlers.show_notes_menu(callback.message, callback.from_user.id, edit=True)


@dp.callback_query(F.data == "current_page")
async def callback_current_page(callback: CallbackQuery):
    await callback.answer("Это текущая страница")


@dp.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery):
    await callback.answer("Отменено")
    try:
        await callback.message.edit_reply_markup()
    except Exception:
        pass


# === ОБРАБОТЧИКИ INLINE QUERY ===

@dp.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    """Обработчик inline запросов для поиска заметок"""
    try:
        query = inline_query.query.strip()
        if not query:
            # Пустой запрос - показываем популярные заметки
            notes = await db.get_notes(inline_query.from_user.id, limit=10)
            results = []

            for note in notes[:5]:  # Максимум 5 результатов для пустого запроса
                title = note.get('title', 'Без названия')[:50]
                content = note.get('content', '')[:100]
                if content:
                    content = content[:97] + '...'

                results.append(
                    InlineQueryResultArticle(
                        id=str(note['id']),
                        title=f"📝 {title}",
                        description=content,
                        input_message_content=InputTextMessageContent(
                            message_text=f"📝 <b>{html.escape(title)}</b>\n\n{html.escape(content)}",
                            parse_mode="HTML"
                        ),
                        thumb_url="https://img.icons8.com/color/48/000000/note.png"
                    )
                )

            await inline_query.answer(results, cache_time=30, is_personal=True)
            return

        # Поиск по заметкам
        notes = await db.search_notes(inline_query.from_user.id, query, limit=20)
        results = []

        for note in notes[:10]:  # Максимум 10 результатов
            title = note.get('title', 'Без названия')[:50]
            content = note.get('content', '')[:150]
            if content:
                content = content[:147] + '...'

            results.append(
                InlineQueryResultArticle(
                    id=str(note['id']),
                    title=f"📝 {title}",
                    description=content,
                    input_message_content=InputTextMessageContent(
                        message_text=f"📝 <b>{html.escape(title)}</b>\n\n{html.escape(content)}",
                        parse_mode="HTML"
                    ),
                    thumb_url="https://img.icons8.com/color/48/000000/note.png"
                )
            )

        if not results:
            # Нет результатов - предлагаем создать заметку
            results.append(
                InlineQueryResultArticle(
                    id="create_note",
                    title="📝 Создать заметку",
                    description=f"Создать новую заметку: '{query}'",
                    input_message_content=InputTextMessageContent(
                        message_text=f"/new {query}"
                    ),
                    thumb_url="https://img.icons8.com/color/48/000000/plus.png"
                )
            )

        await inline_query.answer(results, cache_time=60, is_personal=True)

    except Exception as e:
        logger.error(f"Error in inline query: {e}")
        # Возвращаем пустой результат при ошибке
        await inline_query.answer([], cache_time=30)


# === ПЛАНИРОВЩИК НАПОМИНАНИЙ ===

async def reminder_scheduler():
    """Фоновый планировщик для напоминаний"""
    while True:
        try:
            reminders = await db.get_active_reminders()

            for reminder in reminders:
                try:
                    message_text = (
                        f"⏰ <b>Напоминание!</b>\n\n"
                        f"<b>{reminder['title']}</b>\n"
                        f"{reminder['content'] if reminder['content'] else ''}"
                    )
                    await bot.send_message(
                        chat_id=reminder['user_id'],
                        text=message_text,
                        parse_mode="HTML"
                    )

                    raw_time = reminder.get('reminder_time') or ''
                    reminder_time = parse_db_datetime(raw_time) or datetime.now()

                    repeat_type = (reminder.get('repeat_type') or 'none').lower()
                    repeat_interval = reminder.get('repeat_interval') or 1

                    if repeat_type != 'none':
                        next_time = calculate_next_reminder_time(reminder_time, repeat_type, repeat_interval)
                        await db.update_reminder(
                            reminder_id=reminder['id'],
                            user_id=reminder['user_id'],
                            reminder_time=next_time.strftime("%Y-%m-%d %H:%M:%S"),
                            is_active=True
                        )
                    else:
                        await db.update_reminder(
                            reminder_id=reminder['id'],
                            user_id=reminder['user_id'],
                            is_active=False
                        )

                    activity_tracker.log_activity(
                        reminder['user_id'],
                        "reminder_sent",
                        {
                            "reminder_id": reminder['id'],
                            "repeat_type": repeat_type
                        }
                    )
                    await db.log_user_activity(
                        reminder['user_id'],
                        "reminder_sent",
                        json.dumps({
                            "reminder_id": reminder['id'],
                            "repeat_type": repeat_type,
                            "scheduled_for": raw_time
                        }, ensure_ascii=False)
                    )

                except Exception as inner_error:
                    logger.error(f"Ошибка отправки напоминания {reminder['id']}: {inner_error}")

            await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Ошибка в планировщике напоминаний: {e}")
            await asyncio.sleep(60)


async def main():
    """Основная функция запуска бота"""
    try:
        await db.init_db()
        logger.info("База данных подготовлена")

        asyncio.create_task(reminder_scheduler())
        logger.info("Планировщик напоминаний запущен")

        logger.info("🎉 NotesBot Professional стартует!")
        logger.info("📝 Заметки и напоминания готовы")
        logger.info("📁 Файлы под контролем")
        logger.info("📊 Аналитика подключена")
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
