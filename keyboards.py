from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import List, Optional


class Keyboards:
    """Набор фабрик для клавиатур."""

    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
        """Основное меню."""
        builder = ReplyKeyboardBuilder()
        builder.add(
            KeyboardButton(text="📋 Мои заметки"),
            KeyboardButton(text="⏰ Напоминания"),
            KeyboardButton(text="🔍 Поиск"),
            KeyboardButton(text="📁 Категории"),
            KeyboardButton(text="⚙️ Настройки")
        )
        builder.adjust(2, 2, 1)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def main_inline_menu() -> InlineKeyboardMarkup:
        """Главное меню с inline кнопками."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="📝 Заметки", callback_data="main_notes"),
            InlineKeyboardButton(text="⏰ Напоминания", callback_data="main_reminders"),
            InlineKeyboardButton(text="🎯 Цели и задачи", callback_data="main_goals"),
            InlineKeyboardButton(text="📊 Аналитика", callback_data="main_analytics"),
            InlineKeyboardButton(text="📁 Файлы", callback_data="main_files"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="main_settings"),
            InlineKeyboardButton(text="🔍 Поиск", callback_data="main_search"),
            InlineKeyboardButton(text="📋 Категории", callback_data="main_categories")
        )
        builder.adjust(2, 2, 2, 2)
        return builder.as_markup()

    @staticmethod
    def notes_menu() -> InlineKeyboardMarkup:
        """Главное меню заметок."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="➕ Новая заметка", callback_data="create_note"),
            InlineKeyboardButton(text="📋 Все заметки", callback_data="list_notes"),
            InlineKeyboardButton(text="📌 Закреплённые", callback_data="pinned_notes"),
            InlineKeyboardButton(text="🔍 Поиск", callback_data="search_notes"),
            InlineKeyboardButton(text="📁 Категории", callback_data="categories"),
            InlineKeyboardButton(text="📤 Экспорт", callback_data="export_notes")
        )
        builder.adjust(2, 2, 2)
        return builder.as_markup()

    @staticmethod
    def note_creation_options(back_callback: str = "notes_menu", start_callback: str = "create_note_start") -> InlineKeyboardMarkup:
        """Выбор действия перед созданием заметки."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback),
            InlineKeyboardButton(text="✍️ Создать", callback_data=start_callback)
        )
        builder.adjust(2)
        return builder.as_markup()

    @staticmethod
    def note_title_prompt(back_callback: str = "notes_menu") -> InlineKeyboardMarkup:
        """Клавиатура для шага с вводом заголовка."""
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))
        return builder.as_markup()

    @staticmethod
    def note_content_prompt(back_callback: str = "note_back_to_title") -> InlineKeyboardMarkup:
        """Клавиатура для шага с вводом описания."""
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))
        return builder.as_markup()

    @staticmethod
    def notes_list(notes: List[dict], list_type: str = "all") -> InlineKeyboardMarkup:
        """Список заметок для навигации."""
        builder = InlineKeyboardBuilder()

        if notes:
            for note in notes:
                title = note.get("title") or "Без названия"
                title = title.strip() or "Без названия"
                if len(title) > 40:
                    title = title[:37].rstrip() + "…"
                builder.row(
                    InlineKeyboardButton(
                        text=title,
                        callback_data=f"open_note_{list_type}_{note['id']}"
                    )
                )
        else:
            builder.row(
                InlineKeyboardButton(text="Заметок пока нет", callback_data="notes_empty")
            )

        builder.row(
            InlineKeyboardButton(text="✍️ Создать", callback_data=f"create_note_start_{list_type}")
        )
        return builder.as_markup()

    @staticmethod
    def note_actions(note_id: int, is_pinned: bool = False, list_type: str = "all") -> InlineKeyboardMarkup:
        """Действия над заметкой."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_note_{note_id}"),
            InlineKeyboardButton(
                text="📌 Закрепить" if not is_pinned else "📍 Открепить",
                callback_data=f"toggle_pin_{note_id}"
            ),
            InlineKeyboardButton(text="⏰ Напомнить", callback_data=f"remind_note_{note_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_note_{note_id}"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"notes_list_{list_type}")
        )
        builder.adjust(2, 2, 1)
        return builder.as_markup()

    @staticmethod
    def reminders_menu() -> InlineKeyboardMarkup:
        """Меню напоминаний."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="➕ Новое напоминание", callback_data="create_reminder"),
            InlineKeyboardButton(text="📋 Активные", callback_data="active_reminders"),
            InlineKeyboardButton(text="📅 На сегодня", callback_data="today_reminders"),
            InlineKeyboardButton(text="🗓 На неделю", callback_data="week_reminders"),
            InlineKeyboardButton(text="🛠 Управление", callback_data="manage_reminders"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="reminders_close")
        )
        builder.adjust(2, 2, 2, 1)
        return builder.as_markup()

    @staticmethod
    def reminder_creation_menu() -> InlineKeyboardMarkup:
        """Меню создания напоминания."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="📝 Текст", callback_data="set_reminder_text"),
            InlineKeyboardButton(text="⏰ Время", callback_data="set_reminder_time"),
            InlineKeyboardButton(text="🔁 Повтор", callback_data="set_reminder_repeat"),
            InlineKeyboardButton(text="✅ Готово", callback_data="finish_reminder_creation"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_reminder_creation")
        )
        builder.adjust(2, 2, 1)
        return builder.as_markup()

    @staticmethod
    def reminder_actions(reminder_id: int) -> InlineKeyboardMarkup:
        """Действия над напоминанием."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_reminder_{reminder_id}"),
            InlineKeyboardButton(text="😴 Отложить", callback_data=f"snooze_reminder_{reminder_id}"),
            InlineKeyboardButton(text="✅ Выполнено", callback_data=f"complete_reminder_{reminder_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_reminder_{reminder_id}")
        )
        builder.adjust(2, 2)
        return builder.as_markup()

    @staticmethod
    def categories_list(categories: List[dict], current_category: Optional[str] = None) -> InlineKeyboardMarkup:
        """Список категорий."""
        builder = InlineKeyboardBuilder()

        color_emojis = {
            '#e74c3c': '🟥', '#e67e22': '🟧', '#f39c12': '🟨',
            '#27ae60': '🟩', '#3498db': '🟦', '#9b59b6': '🟪',
            '#34495e': '⬛', '#95a5a6': '⬜'
        }

        for category in categories:
            name = category['name']
            color = category.get('color', '#3498db')
            emoji = color_emojis.get(color, '📁')
            text = f"{emoji} {name}"
            if current_category == name:
                text += " ✅"
            builder.row(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"select_category_{category['id']}"
                )
            )

        builder.row(InlineKeyboardButton(text="➕ Новая категория", callback_data="create_category"))
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="notes_menu"))
        return builder.as_markup()

    @staticmethod
    def time_presets() -> InlineKeyboardMarkup:
        """Быстрый выбор времени."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="🕔 Через 5 минут", callback_data="time_5min"),
            InlineKeyboardButton(text="🕕 Через 15 минут", callback_data="time_15min"),
            InlineKeyboardButton(text="🕖 Через 30 минут", callback_data="time_30min"),
            InlineKeyboardButton(text="🕗 Через час", callback_data="time_1hour"),
            InlineKeyboardButton(text="🌅 Завтра", callback_data="time_tomorrow"),
            InlineKeyboardButton(text="🌄 Послезавтра", callback_data="time_day_after")
        )
        builder.adjust(2, 2, 2)
        return builder.as_markup()

    @staticmethod
    def repeat_options() -> InlineKeyboardMarkup:
        """Предложения по повтору."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="🚫 Без повтора", callback_data="repeat_none"),
            InlineKeyboardButton(text="🔁 Каждый день", callback_data="repeat_daily"),
            InlineKeyboardButton(text="🔂 Каждую неделю", callback_data="repeat_weekly"),
            InlineKeyboardButton(text="📅 Каждый месяц", callback_data="repeat_monthly")
        )
        builder.adjust(2, 2)
        return builder.as_markup()

    @staticmethod
    def confirm_action(action: str, item_id: int) -> InlineKeyboardMarkup:
        """Подтверждение действия."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}_{item_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_{action}_{item_id}")
        )
        builder.adjust(2)
        return builder.as_markup()

    @staticmethod
    def pagination(current_page: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
        """Построение пагинации."""
        builder = InlineKeyboardBuilder()

        if current_page > 1:
            builder.add(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}_page_{current_page-1}"))

        builder.add(InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="current_page"
        ))

        if current_page < total_pages:
            builder.add(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}_page_{current_page+1}"))

        builder.adjust(3)
        return builder.as_markup()

    @staticmethod
    def settings_menu() -> InlineKeyboardMarkup:
        """Меню настроек."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="timezone_settings"),
            InlineKeyboardButton(text="🔔 Уведомления", callback_data="notification_settings"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="statistics"),
            InlineKeyboardButton(text="📤 Экспорт данных", callback_data="export_data"),
            InlineKeyboardButton(text="🗑 Очистить данные", callback_data="clear_data"),
            InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_close")
        )
        builder.adjust(2, 2, 2, 1)
        return builder.as_markup()

    @staticmethod
    def back_button(callback_data: str = "back") -> InlineKeyboardMarkup:
        """Кнопка «Назад»."""
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=callback_data))
        return builder.as_markup()

    @staticmethod
    def notes_list_keyboard(notes: List[dict], list_type: str = "all") -> InlineKeyboardMarkup:
        """Клавиатура для списка заметок с пагинацией."""
        builder = InlineKeyboardBuilder()

        if notes:
            for note in notes[:10]:  # Показываем только первые 10 заметок
                title = note.get("title") or "Без названия"
                title = title.strip() or "Без названия"
                if len(title) > 40:
                    title = title[:37].rstrip() + "…"
                builder.row(
                    InlineKeyboardButton(
                        text=title,
                        callback_data=f"open_note_{list_type}_{note['id']}"
                    )
                )
        else:
            builder.row(
                InlineKeyboardButton(text="Заметок пока нет", callback_data="notes_empty")
            )

        # Добавляем кнопки действий
        builder.row(
            InlineKeyboardButton(text="✍️ Создать", callback_data=f"create_note_{list_type}"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="notes_menu")
        )
        return builder.as_markup()

    @staticmethod
    def note_detail_keyboard(note_id: int, list_type: str = "all") -> InlineKeyboardMarkup:
        """Клавиатура для деталей заметки."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_note_{note_id}"),
            InlineKeyboardButton(text="📌 Закрепить", callback_data=f"toggle_pin_{note_id}"),
            InlineKeyboardButton(text="⏰ Напомнить", callback_data=f"remind_note_{note_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_note_{note_id}"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"notes_list_{list_type}")
        )
        builder.adjust(2, 2, 1)
        return builder.as_markup()

    @staticmethod
    def note_creation_choice(origin: str = "menu", back_callback: str = "notes_menu") -> InlineKeyboardMarkup:
        """Выбор способа создания заметки."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="📝 Быстрое создание", callback_data=f"create_note_start_{origin}"),
            InlineKeyboardButton(text="📋 С шаблоном", callback_data=f"create_note_template_{origin}"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)
        )
        builder.adjust(2, 1)
        return builder.as_markup()

    @staticmethod
    def cancel_button() -> InlineKeyboardMarkup:
        """Кнопка отмены."""
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
        return builder.as_markup()

    @staticmethod
    def notes_list_keyboard_paginated(notes: List[dict], list_type: str = "all", current_page: int = 0) -> InlineKeyboardMarkup:
        """Клавиатура списка заметок с пагинацией"""
        builder = InlineKeyboardBuilder()

        if notes:
            # Добавляем заметки (до 10 на странице)
            for note in notes[current_page * 10:(current_page + 1) * 10]:
                title = note.get("title") or "Без названия"
                title = title.strip() or "Без названия"
                if len(title) > 40:
                    title = title[:37].rstrip() + "…"
                builder.row(
                    InlineKeyboardButton(
                        text=title,
                        callback_data=f"open_note_{list_type}_{note['id']}"
                    )
                )
        else:
            builder.row(
                InlineKeyboardButton(text="Заметок пока нет", callback_data="notes_empty")
            )

        # Кнопки пагинации
        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"notes_page_{list_type}_{current_page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text="✍️ Создать", callback_data=f"create_note_start_{list_type}"))
        if len(notes) > (current_page + 1) * 10:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"notes_page_{list_type}_{current_page + 1}"))

        if nav_buttons:
            builder.row(*nav_buttons)

        builder.row(InlineKeyboardButton(text="⬅️ К списку", callback_data="notes_menu"))
        return builder.as_markup()

    @staticmethod
    def files_menu() -> InlineKeyboardMarkup:
        """Меню файлов"""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="📸 Изображения", callback_data="files_images"),
            InlineKeyboardButton(text="📄 Документы", callback_data="files_documents"),
            InlineKeyboardButton(text="🎵 Аудио", callback_data="files_audio"),
            InlineKeyboardButton(text="📦 Архивы", callback_data="files_archives"),
            InlineKeyboardButton(text="⬆️ Загрузить файл", callback_data="upload_file"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="files_close")
        )
        builder.adjust(2, 2, 2, 1)
        return builder.as_markup()

    @staticmethod
    def files_menu_empty() -> InlineKeyboardMarkup:
        """Пустое меню файлов"""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="⬆️ Загрузить файл", callback_data="upload_file"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="files_close")
        )
        builder.adjust(2)
        return builder.as_markup()

    @staticmethod
    def search_results_keyboard(query: str) -> InlineKeyboardMarkup:
        """Клавиатура результатов поиска"""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="🔍 Искать снова", callback_data=f"search_again_{query}"),
            InlineKeyboardButton(text="📊 Расширенный поиск", callback_data="advanced_search"),
            InlineKeyboardButton(text="⬅️ К заметкам", callback_data="notes_menu")
        )
        builder.adjust(2, 1)
        return builder.as_markup()

    @staticmethod
    def confirm_dangerous_action(action: str, param: str) -> InlineKeyboardMarkup:
        """Подтверждение опасного действия"""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✅ Да, удалить всё", callback_data=f"confirm_{action}_{param}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_dangerous_action")
        )
        builder.adjust(2)
        return builder.as_markup()