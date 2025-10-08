"""
Обработчики команд Telegram бота
"""

import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from typing import Dict, Any, Optional

from database import Database
from keyboards import Keyboards
from time_utils import TimeParser
from user_data import get_user_data, set_user_data
from analytics import activity_tracker
from handlers.notes import NotesHandlers
from handlers.reminders import ReminderHandlers
from handlers.search import SearchHandlers
from handlers.files import FileHandlers
from handlers.settings import SettingsHandlers
from states import NoteStates, ReminderStates, CategoryStates
import html

# Импорт глобального экземпляра базы данных
try:
    from bot_modular import db
except ImportError:
    # Fallback для случаев когда bot_modular недоступен
    db = None

logger = logging.getLogger(__name__)
router = Router()


def check_database():
    """Проверка доступности базы данных"""
    if db is None:
        logger.error("База данных недоступна")
        return False
    return True

# Глобальные экземпляры обработчиков
notes_handlers = None
reminders_handlers = None
search_handlers = None
file_handlers = None
settings_handlers = None

def init_handlers(db: Database, bot: Bot) -> None:
    """Инициализация обработчиков"""
    global notes_handlers, reminders_handlers, search_handlers, file_handlers, settings_handlers

    notes_handlers = NotesHandlers(db, bot)
    reminders_handlers = ReminderHandlers(db, bot)
    search_handlers = SearchHandlers(db, bot)
    file_handlers = FileHandlers(db, bot)
    settings_handlers = SettingsHandlers(db, bot)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Обработчик команды /start"""
    if not check_database():
        await message.answer("❌ Ошибка: база данных недоступна")
        return

    user_id = message.from_user.id

    # Регистрируем пользователя
    await db.add_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code
    )

    # Логируем активность
    activity_tracker.log_activity(user_id, "start_command")

    welcome_text = (
        "🤖 <b>Добро пожаловать в NotesBot Professional!</b>\n\n"
        "Я помогу вам организовать заметки, напоминания и файлы.\n\n"
        "<b>Основные возможности:</b>\n"
        "📝 Управление заметками\n"
        "⏰ Гибкие напоминания\n"
        "📁 Работа с файлами\n"
        "🔍 Поиск и категории\n"
        "📊 Аналитика продуктивности\n\n"
        "Используйте кнопки ниже или команды:\n"
        "/help - подробная справка\n"
        "/new - быстро создать заметку"
    )

    await message.answer(welcome_text, reply_markup=Keyboards.main_menu(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "📚 <b>NotesBot Professional - Справка</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start - Запуск бота\n"
        "/help - Эта справка\n"
        "/new <текст> - Быстро создать заметку\n"
        "/notes - Управление заметками\n"
        "/reminders - Напоминания\n"
        "/search <запрос> - Поиск по заметкам\n"
        "/files - Управление файлами\n"
        "/settings - Настройки\n"
        "/timezone - Настройка часового пояса\n"
        "/export - Экспорт заметок\n"
        "/today - Планы на сегодня\n"
        "/stats - Статистика продуктивности\n\n"
        "<b>Интерактивные меню:</b>\n"
        "📋 Мои заметки - управление заметками\n"
        "⏰ Напоминания - управление напоминаниями\n"
        "🔍 Поиск - поиск по заметкам\n"
        "📁 Категории - управление категориями\n"
        "⚙️ Настройки - настройки бота\n\n"
        "<b>Быстрые действия:</b>\n"
        "• Создавайте заметки командой /new\n"
        "• Используйте кнопки для навигации\n"
        "• Настраивайте напоминания с временем\n"
        "• Организуйте файлы по категориям"
    )

    await message.answer(help_text, reply_markup=Keyboards.main_menu(), parse_mode="HTML")


@router.message(Command("new"))
async def cmd_new_note(message: Message, state: FSMContext):
    """Быстрое создание заметки"""
    if not check_database():
        await message.answer("❌ Ошибка: база данных недоступна")
        return

    try:
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            # Пытаемся извлечь время из текста
            text = args[1]
            reminder_time, remaining_text = TimeParser().parse_time_input(text)

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


@router.message(Command("notes"))
async def cmd_notes(message: Message):
    """Обработка команды /notes"""
    await notes_handlers.show_notes_menu(message, message.from_user.id, edit=False)


@router.message(Command("reminders"))
async def cmd_reminders(message: Message):
    """Обработчик команды /reminders"""
    await reminders_handlers.show_reminders_menu(message, edit=False)


@router.message(Command("search"))
async def cmd_search(message: Message):
    """Обработчик команды /search"""
    await search_handlers.start_search(message, message.from_user.id, edit=False)


@router.message(Command("files"))
async def cmd_files(message: Message):
    """Обработчик команды /files"""
    await file_handlers.show_files_menu(message, message.from_user.id, edit=False)


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Обработчик команды /settings"""
    await settings_handlers.show_settings_menu(message, message.from_user.id, edit=False)


@router.message(Command("timezone"))
async def cmd_timezone(message: Message):
    """Обработчик команды /timezone"""
    await settings_handlers.show_timezone_settings(message, edit=False)


@router.message(Command("export"))
async def cmd_export(message: Message):
    """Экспорт последних заметок в чат."""
    if not check_database():
        await message.answer("❌ Ошибка: база данных недоступна")
        return

    try:
        user_id = message.from_user.id
        notes = await db.get_notes(user_id, limit=10)

        if not notes:
            await message.answer("📭 У вас пока нет заметок для экспорта.")
            return

        export_text = "📤 <b>Экспорт последних заметок</b>\n\n"

        for note in notes:
            title = note.get("title", "Без названия")
            content = note.get("content", "")
            created_at = note.get("created_at", "")

            export_text += f"📝 <b>{title}</b>\n"
            if content:
                export_text += f"{content[:200]}...\n"
            export_text += f"📅 {created_at}\n\n"

        await message.answer(export_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in export command: {e}")
        await message.answer("❌ Ошибка при экспорте заметок.")


@router.message(Command("today"))
async def cmd_today(message: Message):
    """Краткое резюме задач и напоминаний на текущий день."""
    if not check_database():
        await message.answer("❌ Ошибка: база данных недоступна")
        return

    try:
        user_id = message.from_user.id

        # Получаем активные напоминания на сегодня
        reminders = await db.get_active_reminders(user_id)

        # Фильтруем напоминания на сегодня
        from datetime import datetime, date
        today = date.today()
        today_reminders = []

        for reminder in reminders:
            try:
                reminder_date = datetime.fromisoformat(reminder['reminder_time'].replace('Z', '+00:00')).date()
                if reminder_date == today:
                    today_reminders.append(reminder)
            except (ValueError, AttributeError):
                continue

        # Получаем заметки
        notes = await db.get_notes(user_id, limit=5)

        response = "📅 <b>Планы на сегодня</b>\n\n"

        if today_reminders:
            response += f"⏰ <b>Напоминания ({len(today_reminders)}):</b>\n"
            for reminder in today_reminders[:3]:
                title = reminder.get("title", "Без названия")
                time_str = reminder.get("reminder_time", "")
                response += f"• {title}\n"
            if len(today_reminders) > 3:
                response += f"... и еще {len(today_reminders) - 3}\n"
        else:
            response += "⏰ Напоминаний на сегодня нет\n"

        response += "\n📝 <b>Недавние заметки:</b>\n"
        if notes:
            for note in notes[:3]:
                title = note.get("title", "Без названия")
                response += f"• {title}\n"
        else:
            response += "Заметок пока нет"

        await message.answer(response, parse_mode="HTML", reply_markup=Keyboards.main_menu())

    except Exception as e:
        logger.error(f"Error in today command: {e}")
        await message.answer("❌ Ошибка при получении данных на сегодня.")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика продуктивности пользователя."""
    if not check_database():
        await message.answer("❌ Ошибка: база данных недоступна")
        return

    try:
        user_id = message.from_user.id

        # Получаем статистику
        stats = await activity_tracker.get_user_stats(user_id)

        # Получаем количество заметок, напоминаний и файлов
        notes_count = await db.get_notes_count(user_id)
        reminders_count = len(await db.get_active_reminders(user_id))
        files_count = await db.get_files_count(user_id)

        response = (
            "📊 <b>Статистика продуктивности</b>\n\n"
            f"📝 Заметок: {notes_count}\n"
            f"⏰ Активных напоминаний: {reminders_count}\n"
            f"📁 Файлов: {files_count}\n"
            f"📈 Действий за неделю: {stats.get('weekly_actions', 0)}\n"
            f"📅 Действий за месяц: {stats.get('monthly_actions', 0)}\n"
            f"🎯 Средняя продуктивность: {stats.get('avg_productivity', 0):.1f}/день"
        )

        await message.answer(response, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await message.answer("❌ Ошибка при получении статистики.")


# === ОБРАБОТЧИКИ КНОПОК ГЛАВНОГО МЕНЮ ===

@router.message(F.text == "📋 Мои заметки")
async def handle_notes_button(message: Message):
    """Обработчик кнопки 'Мои заметки'"""
    await notes_handlers.show_notes_menu(message, message.from_user.id, edit=False)


@router.message(F.text == "⏰ Напоминания")
async def handle_reminders_button(message: Message):
    """Обработчик кнопки 'Напоминания'"""
    await reminders_handlers.show_reminders_menu(message, edit=False)


@router.message(F.text == "🔍 Поиск")
async def handle_search_button(message: Message):
    """Обработчик кнопки 'Поиск'"""
    await search_handlers.start_search(message, message.from_user.id, edit=False)


@router.message(F.text == "📁 Категории")
async def handle_categories_button(message: Message):
    """Обработчик кнопки 'Категории'"""
    await notes_handlers.show_categories_menu(message, message.from_user.id, edit=False)


@router.message(F.text == "⚙️ Настройки")
async def handle_settings_button(message: Message):
    """Обработчик кнопки 'Настройки'"""
    await settings_handlers.show_settings_overview(message, message.from_user.id, edit=False)


# === ОБРАБОТЧИКИ INLINE CALLBACK ===

@router.callback_query(F.data == "main_notes")
async def handle_main_notes_callback(callback: CallbackQuery):
    """Обработчик callback кнопки 'Заметки'"""
    await callback.message.edit_text(
        "📝 <b>Управление заметками</b>\n\nВыберите действие:",
        reply_markup=Keyboards.notes_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "main_reminders")
async def handle_main_reminders_callback(callback: CallbackQuery):
    """Обработчик callback кнопки 'Напоминания'"""
    await callback.message.edit_text(
        "⏰ <b>Управление напоминаниями</b>\n\nВыберите действие:",
        reply_markup=Keyboards.reminders_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "main_search")
async def handle_main_search_callback(callback: CallbackQuery):
    """Обработчик callback кнопки 'Поиск'"""
    await callback.message.edit_text(
        "🔍 <b>Поиск по заметкам</b>\n\nОтправьте запрос для поиска:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "main_categories")
async def handle_main_categories_callback(callback: CallbackQuery):
    """Обработчик callback кнопки 'Категории'"""
    # Получаем категории пользователя
    categories = await db.get_categories(callback.from_user.id)
    await callback.message.edit_text(
        "📁 <b>Управление категориями</b>",
        reply_markup=Keyboards.categories_list(categories),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "main_settings")
async def handle_main_settings_callback(callback: CallbackQuery):
    """Обработчик callback кнопки 'Настройки'"""
    await settings_handlers.show_settings_overview(callback.message, callback.from_user.id, edit=True)
    await callback.answer()


# === ОБРАБОТЧИКИ FSM СОСТОЯНИЙ ===

@router.message(NoteStates.waiting_for_title)
async def process_note_title(message: Message, state: FSMContext):
    """Обработать ввод заголовка заметки"""
    title = message.text.strip()

    if not title:
        await message.answer("❌ Заголовок не может быть пустым. Попробуйте еще раз:")
        return

    await state.update_data(note_title=title)
    await state.set_state(NoteStates.waiting_for_content)

    await message.answer(
        f"📝 <b>Заголовок сохранен:</b> {html.escape(title)}\n\n"
        "Теперь введите содержание заметки (или отправьте пустое сообщение для завершения):",
        parse_mode="HTML"
    )


@router.message(NoteStates.waiting_for_content)
async def process_note_content(message: Message, state: FSMContext):
    """Обработать ввод содержания заметки"""
    content = message.text.strip()
    user_data = await state.get_data()

    title = user_data.get("note_title", "")
    note_id = await db.add_note(
        user_id=message.from_user.id,
        title=title,
        content=content,
        category="general"
    )

    await state.clear()

    await message.answer(
        "✅ <b>Заметка создана!</b>\n\n"
        f"<b>ID:</b> {note_id}\n"
        f"<b>Заголовок:</b> {html.escape(title)}\n"
        f"<b>Содержание:</b> {html.escape(content[:100]) if content else 'Без содержания'}",
        reply_markup=Keyboards.notes_menu(),
        parse_mode="HTML"
    )


@router.message(NoteStates.editing_note)
async def process_edit_note_title(message: Message, state: FSMContext):
    """Обработать редактирование заголовка заметки"""
    new_title = message.text.strip()

    if not new_title:
        await message.answer("❌ Заголовок не может быть пустым. Попробуйте еще раз:")
        return

    user_data = await state.get_data()
    note_id = user_data.get("note_id")

    if note_id:
        await db.update_note(note_id, message.from_user.id, title=new_title)
        await state.update_data(edit_title=new_title)

        await message.answer(
            f"✏️ <b>Заголовок обновлен:</b> {html.escape(new_title)}\n\n"
            "Теперь введите новое содержание заметки:",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка: не найдена заметка для редактирования")


@router.message(NoteStates.editing_content)
async def process_edit_note_content(message: Message, state: FSMContext):
    """Обработать редактирование содержания заметки"""
    new_content = message.text.strip()
    user_data = await state.get_data()

    note_id = user_data.get("note_id")
    title = user_data.get("edit_title", "")

    if note_id:
        await db.update_note(note_id, message.from_user.id, title=title, content=new_content)
        await state.clear()

        await message.answer(
            "✅ <b>Заметка обновлена!</b>\n\n"
            f"<b>Заголовок:</b> {html.escape(title)}\n"
            f"<b>Содержание:</b> {html.escape(new_content[:100]) if new_content else 'Без содержания'}",
            reply_markup=Keyboards.notes_menu(),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка: не найдена заметка для редактирования")


# === ОБРАБОТЧИКИ СОСТОЯНИЙ НАПОМИНАНИЙ ===

@router.message(ReminderStates.waiting_for_reminder_title)
async def process_reminder_title(message: Message, state: FSMContext):
    """Обработать ввод заголовка напоминания"""
    title = message.text.strip()

    if not title:
        await message.answer("❌ Заголовок напоминания не может быть пустым. Попробуйте еще раз:")
        return

    await state.update_data(reminder_title=title)
    await state.set_state(ReminderStates.waiting_for_reminder_text)

    await message.answer(
        f"⏰ <b>Заголовок напоминания:</b> {html.escape(title)}\n\n"
        "Теперь введите текст напоминания:",
        parse_mode="HTML"
    )


@router.message(ReminderStates.waiting_for_reminder_text)
async def process_reminder_text(message: Message, state: FSMContext):
    """Обработать ввод текста напоминания"""
    text = message.text.strip()

    if not text:
        await message.answer("❌ Текст напоминания не может быть пустым. Попробуйте еще раз:")
        return

    await state.update_data(reminder_text=text)
    await state.set_state(ReminderStates.waiting_for_reminder_time)

    await message.answer(
        f"⏰ <b>Текст напоминания:</b> {html.escape(text)}\n\n"
        "Теперь введите время напоминания (например: 'завтра в 15:00' или 'через 2 часа'):",
        parse_mode="HTML"
    )


@router.message(ReminderStates.waiting_for_reminder_time)
async def process_reminder_time(message: Message, state: FSMContext):
    """Обработать ввод времени напоминания"""
    time_input = message.text.strip()
    user_data = await state.get_data()

    title = user_data.get("reminder_title", "")
    text = user_data.get("reminder_text", "")

    # Парсим время
    reminder_time, remaining_text = TimeParser().parse_time_input(time_input)

    if not reminder_time:
        await message.answer(
            "❌ Не удалось распознать время. Попробуйте формат:\n"
            "• 'завтра в 15:00'\n"
            "• 'через 2 часа'\n"
            "• '15.01.2024 10:30'\n\n"
            "Попробуйте еще раз:"
        )
        return

    # Создаем напоминание
    reminder_id = await db.add_reminder(
        user_id=message.from_user.id,
        title=title,
        content=text,
        reminder_time=reminder_time
    )

    await state.clear()

    await message.answer(
        "✅ <b>Напоминание создано!</b>\n\n"
        f"<b>Заголовок:</b> {html.escape(title)}\n"
        f"<b>Текст:</b> {html.escape(text)}\n"
        f"<b>Время:</b> {TimeParser().format_datetime(reminder_time)}\n"
        f"<b>ID:</b> {reminder_id}",
        reply_markup=Keyboards.reminders_menu(),
        parse_mode="HTML"
    )


# === ОБРАБОТЧИКИ СОСТОЯНИЙ КАТЕГОРИЙ ===

@router.message(CategoryStates.waiting_for_name)
async def process_category_name(message: Message, state: FSMContext):
    """Обработать ввод названия категории"""
    category_name = message.text.strip()

    if not category_name:
        await message.answer("❌ Название категории не может быть пустым. Попробуйте еще раз:")
        return

    if len(category_name) < 2:
        await message.answer("❌ Название категории должно содержать минимум 2 символа. Попробуйте еще раз:")
        return

    if len(category_name) > 50:
        await message.answer("❌ Название категории не может превышать 50 символов. Попробуйте еще раз:")
        return

    # Создаем категорию
    category_id = await db.add_category(
        user_id=message.from_user.id,
        name=category_name,
        color="#3498db"  # Синий цвет по умолчанию
    )

    await state.clear()

    await message.answer(
        "✅ <b>Категория создана!</b>\n\n"
        f"<b>Название:</b> {html.escape(category_name)}\n"
        f"<b>ID:</b> {category_id}",
        reply_markup=Keyboards.notes_menu(),
        parse_mode="HTML"
    )


# === ОБРАБОТЧИКИ ФАЙЛОВ ===

@router.message(F.photo)
async def handle_photo(message: Message):
    """Обработчик фото"""
    if not check_database():
        await message.answer("❌ Ошибка: база данных недоступна")
        return

    try:
        user_id = message.from_user.id
        photo = message.photo[-1]  # Берем фото максимального качества

        # Получаем информацию о файле
        file_info = await message.bot.get_file(photo.file_id)
        file_path = file_info.file_path

        # Скачиваем файл
        await message.bot.download_file(file_path, f"files/images/{photo.file_id}.jpg")

        # Сохраняем информацию в базу данных
        file_id = await db.add_file(
            user_id=user_id,
            file_name=f"photo_{photo.file_id}.jpg",
            file_type="image",
            file_size=photo.file_size,
            mime_type="image/jpeg",
            file_path=f"files/images/{photo.file_id}.jpg"
        )

        # Получаем caption если есть
        caption = message.caption or "Фото без описания"

        await message.answer(
            "📸 <b>Фото сохранено!</b>\n\n"
            f"<b>ID файла:</b> {file_id}\n"
            f"<b>Размер:</b> {photo.file_size} байт\n"
            f"<b>Описание:</b> {html.escape(caption)}",
            reply_markup=Keyboards.files_menu(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        await message.answer("❌ Ошибка при сохранении фото.")


@router.message(F.document)
async def handle_document(message: Message):
    """Обработчик документов"""
    if not check_database():
        await message.answer("❌ Ошибка: база данных недоступна")
        return

    try:
        user_id = message.from_user.id
        document = message.document

        # Получаем информацию о файле
        file_info = await message.bot.get_file(document.file_id)
        file_path = file_info.file_path

        # Скачиваем файл
        await message.bot.download_file(file_path, f"files/documents/{document.file_id}_{document.file_name}")

        # Определяем категорию файла
        file_extension = document.file_name.split('.')[-1].lower() if '.' in document.file_name else 'unknown'

        category_map = {
            'pdf': 'document', 'doc': 'document', 'docx': 'document',
            'txt': 'document', 'rtf': 'document', 'odt': 'document',
            'xls': 'document', 'xlsx': 'document', 'csv': 'document',
            'ppt': 'document', 'pptx': 'document',
            'zip': 'archive', 'rar': 'archive', '7z': 'archive', 'tar': 'archive', 'gz': 'archive'
        }

        file_category = category_map.get(file_extension, 'document')

        # Сохраняем информацию в базу данных
        file_id = await db.add_file(
            user_id=user_id,
            file_name=document.file_name,
            file_type=file_category,
            file_size=document.file_size,
            mime_type=document.mime_type,
            file_path=f"files/documents/{document.file_id}_{document.file_name}"
        )

        # Получаем caption если есть
        caption = message.caption or "Документ без описания"

        await message.answer(
            "📄 <b>Документ сохранен!</b>\n\n"
            f"<b>Название:</b> {html.escape(document.file_name)}\n"
            f"<b>ID файла:</b> {file_id}\n"
            f"<b>Размер:</b> {document.file_size} байт\n"
            f"<b>Тип:</b> {file_category}\n"
            f"<b>Описание:</b> {html.escape(caption)}",
            reply_markup=Keyboards.files_menu(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error handling document: {e}")
        await message.answer("❌ Ошибка при сохранении документа.")


@router.message(F.voice)
async def handle_voice(message: Message):
    """Обработчик голосовых сообщений"""
    if not check_database():
        await message.answer("❌ Ошибка: база данных недоступна")
        return

    try:
        user_id = message.from_user.id
        voice = message.voice

        # Получаем информацию о файле
        file_info = await message.bot.get_file(voice.file_id)
        file_path = file_info.file_path

        # Скачиваем файл
        await message.bot.download_file(file_path, f"files/audio/{voice.file_id}.ogg")

        # Конвертируем в текст если возможно
        text_content = ""
        try:
            # Здесь можно добавить конвертацию речи в текст
            text_content = "Голосовое сообщение (распознавание не настроено)"
        except:
            text_content = "Голосовое сообщение"

        # Создаем заметку с аудио
        note_id = await db.add_note(
            user_id=user_id,
            title="Голосовая заметка",
            content=text_content,
            category="audio"
        )

        # Сохраняем информацию о файле
        file_id = await db.add_file(
            user_id=user_id,
            file_name=f"voice_{voice.file_id}.ogg",
            file_type="audio",
            file_size=voice.file_size,
            mime_type="audio/ogg",
            file_path=f"files/audio/{voice.file_id}.ogg",
            note_id=note_id
        )

        duration = voice.duration
        duration_str = f"{duration//60}:{duration%60:02d}" if duration else "неизвестно"

        await message.answer(
            "🎵 <b>Голосовое сообщение сохранено!</b>\n\n"
            f"<b>ID заметки:</b> {note_id}\n"
            f"<b>ID файла:</b> {file_id}\n"
            f"<b>Длительность:</b> {duration_str}\n"
            f"<b>Размер:</b> {voice.file_size} байт\n"
            f"<b>Содержание:</b> {html.escape(text_content)}",
            reply_markup=Keyboards.files_menu(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error handling voice: {e}")
        await message.answer("❌ Ошибка при сохранении голосового сообщения.")