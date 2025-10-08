"""
Обработчики настроек для NotesBot
"""

import asyncio
import json
import html
import logging
import datetime
from typing import Dict, Any, Optional, List

from aiogram import F, Router, Bot
from aiogram.types import Message, CallbackQuery

from database import Database

router = Router()
from keyboards import Keyboards
from user_data import get_user_data, set_user_data
from analytics import activity_tracker

logger = logging.getLogger(__name__)


class SettingsHandlers:
    """Обработчики для управления настройками"""

    def __init__(self, db: Database, bot: Bot):
        self.db = db
        self.bot = bot

    async def show_settings_overview(self, message: Message, user_id: int, edit: bool = False):
        """Показать обзор настроек"""
        try:
            user = await self.db.get_user(user_id)

            if not user:
                await message.answer("❌ Пользователь не найден в базе данных.", parse_mode="HTML")
                return

            # Получаем статистику
            notes = await self.db.get_notes(user_id, limit=1000)
            reminders = await self.db.get_active_reminders(user_id)
            categories = await self.db.get_categories(user_id)

            settings_text = f"""
⚙️ <b>Настройки</b>

👤 <b>Профиль:</b>
• Имя: {user['first_name'] or 'не указано'}
• Username: @{user['username'] or 'нет'}
• Язык: {user['language_code'] or 'не указан'}
• Зарегистрирован: {user['created_at'][:10]}

📊 <b>Статистика:</b>
• Заметок: {len(notes)}
• Активных напоминаний: {len(reminders)}
• Категорий: {len(categories)}

Выберите действие в меню ниже:
"""

            await self._safe_edit_or_send(
                message,
                settings_text,
                reply_markup=Keyboards.settings_menu(),
                edit=edit,
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Error in settings: {e}")
            await message.answer("⚠️ Не удалось получить настройки.")

    async def show_timezone_settings(self, message: Message, edit: bool = False):
        """Показать настройки часового пояса"""
        try:
            user = await self.db.get_user(message.from_user.id)
            timezone = user.get('timezone') if user and user.get('timezone') else 'не указан'

            text = (
                "🌍 <b>Часовой пояс</b>\n\n"
                f"Текущий часовой пояс: <b>{html.escape(timezone)}</b>\n"
                "Измените его командой <code>/timezone +3</code> (пример)."
            )

            await self._safe_edit_or_send(
                message,
                text,
                reply_markup=Keyboards.settings_menu(),
                edit=edit,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in timezone settings: {e}")
            await message.answer("⚠️ Не удалось получить настройки часового пояса.")

    async def show_notification_settings(self, message: Message, edit: bool = False):
        """Показать настройки уведомлений"""
        try:
            text = (
                "🔔 <b>Уведомления</b>\n\n"
                "Напоминания приходят автоматически.\n"
                "Используйте команду <code>/remind</code>, чтобы добавить новое уведомление."
            )

            await self._safe_edit_or_send(
                message,
                text,
                reply_markup=Keyboards.settings_menu(),
                edit=edit,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in notification settings: {e}")
            await message.answer("⚠️ Не удалось получить настройки уведомлений.")

    async def show_export_settings(self, message: Message, edit: bool = False):
        """Показать настройки экспорта"""
        try:
            text = (
                "📤 <b>Экспорт данных</b>\n\n"
                "Используйте команду <code>/export</code>, чтобы получить все заметки в виде текста."
            )

            await self._safe_edit_or_send(
                message,
                text,
                reply_markup=Keyboards.settings_menu(),
                edit=edit,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in export settings: {e}")
            await message.answer("⚠️ Не удалось получить настройки экспорта.")

    async def show_data_management(self, message: Message, edit: bool = False):
        """Показать управление данными"""
        try:
            text = (
                "🗑 <b>Очистка данных</b>\n\n"
                "Для удаления данных обратитесь к разработчику или очистите записи вручную.\n"
                "Автоматическая очистка появится в будущих версиях."
            )

            await self._safe_edit_or_send(
                message,
                text,
                reply_markup=Keyboards.settings_menu(),
                edit=edit,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in data management: {e}")
            await message.answer("⚠️ Не удалось получить настройки управления данными.")

    async def show_help_settings(self, message: Message, edit: bool = False):
        """Показать справку по настройкам"""
        try:
            text = (
                "❓ <b>Помощь</b>\n\n"
                "• /help — справка по всем командам\n"
                "• /new — создать заметку\n"
                "• /remind — новое напоминание\n"
                "• /notes — список заметок"
            )

            await self._safe_edit_or_send(
                message,
                text,
                reply_markup=Keyboards.settings_menu(),
                edit=edit,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in help settings: {e}")
            await message.answer("⚠️ Не удалось получить справку.")

    async def show_statistics_settings(self, message: Message, user_id: int, edit: bool = False):
        """Показать расширенную статистику в настройках"""
        try:
            # Получаем статистику
            notes = await self.db.get_notes(user_id, limit=1000)
            reminders = await self.db.get_active_reminders(user_id)
            categories = await self.db.get_categories(user_id)

            total_notes = len(notes)
            pinned_notes = len([n for n in notes if n['is_pinned']])
            active_reminders = len(reminders)
            total_categories = len(categories)

            # Статистика по категориям
            category_stats = {}
            for note in notes:
                category = note['category']
                category_stats[category] = category_stats.get(category, 0) + 1

            stats_text = f"📊 <b>Ваша статистика</b>\n\n"
            stats_text += f"📝 Всего заметок: {total_notes}\n"
            stats_text += f"📌 Закрепленных: {pinned_notes}\n"
            stats_text += f"⏰ Активных напоминаний: {active_reminders}\n"
            stats_text += f"📁 Категорий: {total_categories}\n\n"

            if category_stats:
                stats_text += "<b>Заметки по категориям:</b>\n"
                for category, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
                    stats_text += f"• {category}: {count}\n"

            await self._safe_edit_or_send(
                message,
                stats_text,
                reply_markup=Keyboards.settings_menu(),
                edit=edit,
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Error in statistics settings: {e}")
            await message.answer("⚠️ Не удалось получить статистику.")

    async def show_export_notes_settings(self, message: Message, user_id: int, edit: bool = False):
        """Показать экспорт заметок в настройках"""
        try:
            notes = await self.db.get_notes(user_id, limit=1000)

            if not notes:
                await message.answer("У вас нет заметок для экспорта!", parse_mode="HTML")
                return

            # Формируем текст для экспорта
            export_text = f"📤 Экспорт заметок от {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"

            for note in notes:
                pinned = "📌 " if note['is_pinned'] else ""
                export_text += f"{pinned}<b>{note['title']}</b>\n"
                export_text += f"📁 Категория: {note['category']}\n"
                export_text += f"📅 Создано: {note['created_at'][:16]}\n"
                if note['content']:
                    export_text += f"📝 Содержимое:\n{note['content']}\n"
                export_text += "\n" + "="*50 + "\n\n"

            # Разбиваем на части если текст слишком длинный
            max_length = 4000
            if len(export_text) > max_length:
                parts = [export_text[i:i+max_length] for i in range(0, len(export_text), max_length)]
                for i, part in enumerate(parts):
                    await message.answer(
                        f"📤 <b>Экспорт заметок (часть {i+1}/{len(parts)})</b>\n\n{part}",
                        parse_mode="HTML"
                    )
            else:
                await message.answer(export_text, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error in export notes settings: {e}")
            await message.answer("❌ Ошибка при экспорте заметок.")

    async def set_timezone(self, message: Message, timezone_offset: str):
        """Установить часовой пояс пользователя"""
        try:
            # Простая валидация
            if not timezone_offset.replace('+', '').replace('-', '').isdigit():
                await message.answer("❌ Неверный формат часового пояса. Используйте формат +3 или -5.")
                return

            offset_int = int(timezone_offset)
            if not -12 <= offset_int <= 14:
                await message.answer("❌ Часовой пояс должен быть в диапазоне от -12 до +14.")
                return

            # Сохраняем в БД (пока просто сохраняем как строку)
            # В будущем можно расширить для поддержки именованных зон
            await self.db.update_user_timezone(message.from_user.id, timezone_offset)

            await message.answer(
                f"✅ Часовой пояс установлен: UTC{timezone_offset}\n\n"
                "Это повлияет на время отображения напоминаний и заметок.",
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Error setting timezone: {e}")
            await message.answer("❌ Ошибка при установке часового пояса.")

    async def clear_user_data(self, message: Message, user_id: int):
        """Очистить все данные пользователя (опасная операция)"""
        try:
            # Показываем предупреждение
            text = """⚠️ <b>ВНИМАНИЕ!</b>

Вы действительно хотите удалить ВСЕ свои данные?

Это действие:
• 🗑 Удалит все заметки
• 🗑 Удалит все напоминания
• 🗑 Удалит все файлы
• 🗑 Удалит все категории
• 🗑 Очистит статистику

Это действие НЕЛЬЗЯ отменить!

Используйте эту функцию только если вы уверены."""

            await message.answer(
                text,
                reply_markup=Keyboards.confirm_dangerous_action("clear_all_data", user_id),
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Error in clear data warning: {e}")
            await message.answer("❌ Ошибка при подготовке очистки данных.")

    async def execute_clear_all_data(self, message: Message, user_id: int):
        """Выполнить очистку всех данных пользователя"""
        try:
            # Получаем подтверждение через callback
            await message.answer("⚠️ Используйте кнопку подтверждения ниже.", parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error in clear all data: {e}")
            await message.answer("❌ Ошибка при очистке данных.")

    async def _safe_edit_or_send(self, message: Message, text: str, reply_markup=None, *, parse_mode: str = "HTML", edit: bool = True):
        """Безопасное редактирование или отправка сообщения"""
        if edit:
            try:
                await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
                return
            except Exception:
                pass
        await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
