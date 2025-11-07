from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
import html
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from aiogram import Bot
from database import Database
from keyboards import Keyboards
from states import NoteStates
from time_utils import parse_time_input, TimeParser

router = Router()
logger = logging.getLogger(__name__)


class NotesHandlers:
    """Обработчики для управления заметками"""

    def __init__(self, db: Database, bot: Bot):
        self.db = db
        self.bot = bot

    async def _safe_edit_or_send(self, message: Message, text: str, reply_markup=None, *, parse_mode: str = "HTML", edit: bool = True):
        """Безопасное редактирование или отправка сообщения"""
        if edit:
            try:
                await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
                return
            except Exception:
                pass
        await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)

    async def show_notes_menu(self, message: Message, user_id: int, state: FSMContext = None, *, edit: bool = False):
        """Показать меню заметок"""
        text = """📒 <b>Заметки</b>\n\nВыберите действие ниже, чтобы создать новую запись или открыть существующие заметки."""
        await self._safe_edit_or_send(message, text, reply_markup=Keyboards.notes_menu(), edit=edit)
        if state:
            await state.update_data(notes_current_list="all")
            data = await state.get_data()
            if "awaiting_note_search" in data:
                data_copy = data.copy()
                data_copy.pop("awaiting_note_search", None)
                await state.set_data(data_copy)

    async def show_notes_list(self, message: Message, user_id: int, list_type: str = "all", state: FSMContext = None, *, edit: bool = False):
        """Показать список заметок"""
        if list_type.startswith("category:"):
            category_name = list_type.split(":", 1)[1]
            notes = await self.db.get_notes(user_id, category=category_name, limit=50)
            header = f"📁 <b>Категория: {html.escape(category_name)}</b>"
        else:
            raw_notes = await self.db.get_notes(user_id, limit=50)
            if list_type == "pinned":
                notes = [note for note in raw_notes if note.get("is_pinned")]
                header = "📌 <b>Закреплённые заметки</b>"
            else:
                notes = raw_notes
                header = "📋 <b>Все заметки</b>"

        lines = [header]

        if not notes:
            lines.append("Пока нет заметок в этом разделе.")
        else:
            for note in notes[:10]:
                title = (note.get("title") or "Без названия").strip() or "Без названия"
                lines.append(f"• <b>{html.escape(title)}</b>")
                content = (note.get("content") or "").strip()
                if content:
                    preview = content.replace("\n", " ")
                    if len(preview) > 80:
                        preview = preview[:77].rstrip() + "…"
                    lines.append(f"  {html.escape(preview)}")

        lines.append("\nОткройте заметку кнопкой ниже или создайте новую запись.")
        text_block = "\n".join(lines)
        markup = Keyboards.notes_list(notes[:20], list_type=list_type)
        await self._safe_edit_or_send(message, text_block, reply_markup=markup, edit=edit)
        if state:
            await state.update_data(notes_current_list=list_type)

    async def create_note_interactive(self, message: Message, state: FSMContext):
        """Начать интерактивное создание заметки"""
        await state.set_state(NoteStates.waiting_for_title)
        await message.answer(
            "📝 <b>Создание новой заметки</b>\n\nВведите заголовок заметки:",
            parse_mode="HTML"
        )

    async def toggle_pin_note(self, callback: CallbackQuery, note_id: int):
        """Переключить закрепление заметки"""
        try:
            note_id = int(note_id)
            user_id = callback.from_user.id

            # Получаем текущий статус закрепления
            note = await self.db.get_note(note_id, user_id)
            if not note:
                await callback.answer("Заметка не найдена", show_alert=True)
                return

            current_pin_status = note.get("is_pinned", False)
            new_pin_status = not current_pin_status

            # Обновляем статус закрепления
            await self.db.update_note(note_id, user_id, is_pinned=new_pin_status)

            # Получаем обновленную заметку для корректного отображения
            updated_note = await self.db.get_note(note_id, user_id)
            list_type = "pinned" if new_pin_status else "all"

            # Показываем обновленную заметку
            success = await self.show_note_detail(
                callback.message, user_id, note_id,
                list_type=list_type, edit=True
            )

            if success:
                pin_text = "закреплена" if new_pin_status else "откреплена"
                await callback.answer(f"Заметка {pin_text}", show_alert=True)
            else:
                await callback.answer("Ошибка при обновлении заметки", show_alert=True)

        except Exception as e:
            logger.error(f"Error toggling pin for note {note_id}: {e}")
            await callback.answer("Ошибка при изменении закрепления", show_alert=True)

    async def edit_note_start(self, callback: CallbackQuery, state: FSMContext, note_id: int):
        """Начать редактирование заметки"""
        try:
            note_id = int(note_id)
            user_id = callback.from_user.id

            note = await self.db.get_note(note_id, user_id)
            if not note:
                await callback.answer("Заметка не найдена", show_alert=True)
                return

            await state.set_state(NoteStates.editing_note)
            await state.update_data(note_id=note_id, edit_title=note.get("title", ""), edit_content=note.get("content", ""))

            await callback.message.edit_text(
                f"✏️ <b>Редактирование заметки</b>\n\n"
                f"<b>Текущий заголовок:</b> {html.escape(note.get('title', ''))}\n"
                f"<b>Текущее содержание:</b> {html.escape(note.get('content', '')[:100])}\n\n"
                f"Выберите, что редактировать:",
                reply_markup=Keyboards.note_actions(note_id, note.get("is_pinned"), "all"),
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Error starting note edit for {note_id}: {e}")
            await callback.answer("Ошибка при начале редактирования", show_alert=True)

    async def delete_note_confirm(self, callback: CallbackQuery, note_id: int):
        """Подтвердить удаление заметки"""
        try:
            note_id = int(note_id)
            user_id = callback.from_user.id

            note = await self.db.get_note(note_id, user_id)
            if not note:
                await callback.answer("Заметка не найдена", show_alert=True)
                return

            await callback.message.edit_text(
                f"🗑 <b>Подтверждение удаления</b>\n\n"
                f"Вы действительно хотите удалить заметку:\n"
                f"<b>{html.escape(note.get('title', 'Без названия'))}</b>?\n\n"
                f"Это действие нельзя отменить.",
                reply_markup=Keyboards.confirm_action("delete_note", note_id),
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Error confirming note deletion for {note_id}: {e}")
            await callback.answer("Ошибка при подтверждении удаления", show_alert=True)

    async def delete_note_execute(self, callback: CallbackQuery, note_id: int):
        """Выполнить удаление заметки"""
        try:
            note_id = int(note_id)
            user_id = callback.from_user.id

            note = await self.db.get_note(note_id, user_id)
            if not note:
                await callback.answer("Заметка не найдена", show_alert=True)
                return

            # Удаляем заметку
            success = await self.db.delete_note(note_id, user_id)

            if success:
                await callback.message.edit_text(
                    f"✅ Заметка удалена:\n<b>{html.escape(note.get('title', 'Без названия'))}</b>",
                    reply_markup=Keyboards.notes_menu(),
                    parse_mode="HTML"
                )
                await callback.answer("Заметка удалена", show_alert=True)
            else:
                await callback.answer("Ошибка при удалении заметки", show_alert=True)

        except Exception as e:
            logger.error(f"Error deleting note {note_id}: {e}")
            await callback.answer("Ошибка при удалении заметки", show_alert=True)

    async def process_note_title(self, message: Message, state: FSMContext):
        """Обработать ввод заголовка заметки"""
        title = message.text.strip()

        if not title:
            await message.answer("❌ Заголовок не может быть пустым. Попробуйте еще раз:")
            return

        await state.update_data(note_title=title)
        await state.set_state(NoteStates.waiting_for_content)

        await message.answer(
            f"📝 <b>Заголовок сохранен:</b> {html.escape(title)}\n\n"
            f"Теперь введите содержание заметки (или отправьте пустое сообщение для завершения):",
            parse_mode="HTML"
        )

    async def process_note_content(self, message: Message, state: FSMContext):
        """Обработать ввод содержания заметки"""
        content = message.text.strip()
        user_data = await state.get_data()

        title = user_data.get("note_title", "")
        note_id = await self.db.add_note(
            user_id=message.from_user.id,
            title=title,
            content=content,
            category="general"
        )

        await state.clear()

        await message.answer(
            f"✅ <b>Заметка создана!</b>\n\n"
            f"<b>ID:</b> {note_id}\n"
            f"<b>Заголовок:</b> {html.escape(title)}\n"
            f"<b>Содержание:</b> {html.escape(content[:100]) if content else 'Без содержания'}",
            reply_markup=Keyboards.notes_menu(),
            parse_mode="HTML"
        )

    async def process_edit_note_title(self, message: Message, state: FSMContext):
        """Обработать редактирование заголовка заметки"""
        new_title = message.text.strip()

        if not new_title:
            await message.answer("❌ Заголовок не может быть пустым. Попробуйте еще раз:")
            return

        user_data = await state.get_data()
        note_id = user_data.get("note_id")

        if note_id:
            await self.db.update_note(note_id, message.from_user.id, title=new_title)
            await state.update_data(edit_title=new_title)

            await message.answer(
                f"✏️ <b>Заголовок обновлен:</b> {html.escape(new_title)}\n\n"
                f"Теперь введите новое содержание заметки:",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка: не найдена заметка для редактирования")

    async def process_edit_note_content(self, message: Message, state: FSMContext):
        """Обработать редактирование содержания заметки"""
        new_content = message.text.strip()
        user_data = await state.get_data()

        note_id = user_data.get("note_id")
        title = user_data.get("edit_title", "")

        if note_id:
            await self.db.update_note(note_id, message.from_user.id, title=title, content=new_content)
            await state.clear()

            await message.answer(
                f"✅ <b>Заметка обновлена!</b>\n\n"
                f"<b>Заголовок:</b> {html.escape(title)}\n"
                f"<b>Содержание:</b> {html.escape(new_content[:100]) if new_content else 'Без содержания'}",
                reply_markup=Keyboards.notes_menu(),
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка: не найдена заметка для редактирования")

    def _parse_db_datetime(self, datetime_str):
        """Вспомогательный метод для парсинга даты из БД"""
        if not datetime_str:
            return None
        try:
            if isinstance(datetime_str, str):
                # Пробуем разные форматы
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S.%f']:
                    try:
                        return datetime.strptime(datetime_str, fmt)
                    except ValueError:
                        continue
                return None
            return datetime_str
        except Exception:
            return None


    async def show_note_detail(self, message: Message, user_id: int, note_id: int, list_type: str = "all", state: FSMContext = None, *, edit: bool = False):
        """Показать детали заметки"""
        note = await self.db.get_note(note_id, user_id)
        if not note:
            return False

        created_at = self._parse_db_datetime(note.get("created_at") or "") or datetime.now()
        updated_at = self._parse_db_datetime(note.get("updated_at") or "") or created_at

        header = (note.get("title") or "Без названия").strip() or "Без названия"
        category = note.get("category") or "Без категории"
        pinned_flag = '📌 ' if note.get("is_pinned") else ''
        text_parts = [
            f"{pinned_flag}<b>{html.escape(header)}</b>",
            f"Категория: {html.escape(category)}",
            f"Создано: {created_at.strftime('%d.%m.%Y %H:%M')}",
        ]
        if updated_at > created_at:
            text_parts.append(f"Обновлено: {updated_at.strftime('%d.%m.%Y %H:%M')}")

        content = (note.get("content") or "").strip()
        if content:
            safe_content = html.escape(content)
            if len(safe_content) > 3500:
                safe_content = safe_content[:3497] + "…"
            text_parts.append("")
            text_parts.append(f"<pre>{safe_content}</pre>")

        text_block = "\n".join(text_parts)

        markup = Keyboards.note_actions(note_id, bool(note.get("is_pinned")), list_type=list_type)
        await self._safe_edit_or_send(message, text_block, reply_markup=markup, edit=edit)
        if state:
            await state.update_data(
                notes_current_list=list_type,
                notes_last_note_id=note_id,
                notes_last_list_type=list_type
            )
        return True


    async def show_note_creation_choice(self, message: Message, user_id: int, origin: str, back_callback: str, state: FSMContext = None, *, edit: bool = True):
        """Показ этапа выбора перед созданием заметки."""
        prompt_text = "✍️ <b>Создание заметки</b>\n\nНажмите «Создать», чтобы ввести заголовок, или вернитесь назад."
        start_callback = f"create_note_start_{origin}"
        if state:
            if origin.startswith('list_'):
                list_type = origin.split('_', 1)[1]
                await state.update_data(note_creation_list_type=list_type)
            else:
                await state.update_data(note_creation_list_type="all")
            await state.update_data(note_creation_origin=origin)
        markup = Keyboards.note_creation_options(back_callback=back_callback, start_callback=start_callback)
        await self._safe_edit_or_send(message, prompt_text, reply_markup=markup, edit=edit)

    async def cmd_new_note(self, message: Message, state: FSMContext):
        """Быстрое создание заметки"""
        try:
            args = message.text.split(maxsplit=1)
            if len(args) > 1:
                text = args[1]
                reminder_time, remaining_text = parse_time_input(text)

                await state.update_data(
                    note_title=remaining_text[:50],
                    note_content=remaining_text,
                    reminder_time=reminder_time
                )

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
                    note_id = await self.db.add_note(
                        user_id=message.from_user.id,
                        title=remaining_text[:50],
                        content=remaining_text,
                        category="general"
                    )

                    await message.answer(
                        f"✅ <b>Заметка создана!</b>\n\n"
                        f"<b>ID:</b> {note_id}\n"
                        f"<b>Заголовок:</b> {remaining_text[:50]}",
                        parse_mode="HTML"
                    )
            else:
                await state.set_state(NoteStates.waiting_for_title)
                await message.answer(
                    "📝 <b>Создание новой заметки</b>\n\nВведите заголовок заметки:",
                    parse_mode="HTML"
                )

        except Exception as e:
            logger.error(f"Error in new note command: {e}")
            await message.answer("❌ Ошибка при создании заметки.")

    async def show_categories_menu(self, message: Message, user_id: int, *, edit: bool = False):
        """Показать меню категорий"""
        try:
            categories = await self.db.get_categories(user_id)

            if not categories:
                text = (
                    "📭 <b>У вас пока нет категорий</b>\n\n"
                    "Категории создаются автоматически при добавлении заметок.\n"
                    "Используйте команду /new для создания первой заметки."
                )
                await self._safe_edit_or_send(message, text, reply_markup=Keyboards.notes_menu(), edit=edit)
                return

            text = "📁 <b>Ваши категории:</b>\n\n"
            for category in categories:
                notes = await self.db.get_notes(user_id, category=category['name'])
                notes_count = len(notes)
                color_emoji = {
                    '#e74c3c': '🟥', '#e67e22': '🟧', '#f39c12': '🟨',
                    '#27ae60': '🟩', '#3498db': '🟦', '#9b59b6': '🟪',
                    '#34495e': '⬛', '#95a5a6': '⬜'
                }.get(category.get('color', '#3498db'), '📁')

                text += f"{color_emoji} <b>{category['name']}</b>\n"
                text += f"   📝 Заметок: {notes_count}\n\n"

            await self._safe_edit_or_send(message, text, reply_markup=Keyboards.categories_list(categories), edit=edit)

        except Exception as e:
            logger.error(f"Error showing categories: {e}")
            await message.answer("❌ Ошибка при получении категорий.")
