"""
Обработчики файлов для NotesBot
"""

import asyncio
import json
import html
import logging
import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from aiogram import F, Router, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile

from database import Database

router = Router()
from keyboards import Keyboards
from file_manager import file_manager
from security import security_manager
from user_data import get_user_data
from analytics import activity_tracker

logger = logging.getLogger(__name__)


class FileHandlers:
    """Обработчики для управления файлами"""

    def __init__(self, db: Database, bot: Bot):
        self.db = db
        self.bot = bot

    async def show_files_menu(self, message: Message, user_id: int, edit: bool = False):
        """Показать меню файлов"""
        try:
            files = await self.db.get_user_files(user_id)

            if not files:
                text = "📁 <b>Ваши файлы</b>\n\nУ вас пока нет загруженных файлов."
                keyboard = Keyboards.files_menu_empty()
            else:
                text = f"📁 <b>Ваши файлы ({len(files)})</b>\n\n"

                # Группируем файлы по категориям
                files_by_category = {}
                for file in files[:20]:  # Показываем первые 20 файлов
                    category = file.get('file_category', 'other')
                    if category not in files_by_category:
                        files_by_category[category] = []
                    files_by_category[category].append(file)

                for category, category_files in files_by_category.items():
                    emoji = self._get_category_emoji(category)
                    text += f"\n{emoji} <b>{category.title()} ({len(category_files)})</b>\n"

                    for file in category_files[:5]:  # Показываем до 5 файлов в категории
                        size_mb = file['file_size'] / (1024 * 1024)
                        name = file.get('original_name', 'Без названия')[:30]
                        text += f"  • {html.escape(name)} ({size_mb:.1f}MB)\n"

                    if len(category_files) > 5:
                        text += f"  ... и ещё {len(category_files) - 5} файлов\n"

                keyboard = Keyboards.files_menu()

                await self._safe_edit_or_send(message, text, reply_markup=keyboard, edit=edit)

        except Exception as e:
            logger.error(f"Error showing files menu: {e}")
            await message.answer("⚠️ Не удалось открыть меню файлов.")

    async def handle_photo_upload(self, message: Message, user_id: int):
        """Обработать загрузку фото"""
        try:
            # Проверяем rate limit
            access_check = await security_manager.check_user_access(user_id, "file")
            if not access_check['allowed']:
                await message.answer(f"⚠️ {access_check['reason']}")
                return

            # Получаем файл наибольшего размера
            photo = message.photo[-1]
            file_info = await self.bot.get_file(photo.file_id)
            file_content = await self.bot.download_file(file_info.file_path)

            # Валидируем файл
            file_data = {
                'file_name': f"photo_{photo.file_id}.jpg",
                'file_size': photo.file_size or 0,
                'mime_type': 'image/jpeg'
            }

            validation = security_manager.validate_file_upload(file_data)
            if not validation['valid']:
                await message.answer(f"❌ {'; '.join(validation['errors'])}")
                return

            # Сохраняем файл
            save_result = await file_manager.save_file(
                file_content.read(),
                file_data['file_name'],
                'image',
                user_id
            )

            if save_result['success']:
                # Сохраняем в БД
                await self.db.add_file(
                    user_id=user_id,
                    file_id=save_result['file_id'],
                    original_name=file_data['file_name'],
                    file_size=save_result['file_size'],
                    file_hash=save_result['file_hash'],
                    file_category='image',
                    mime_type='image/jpeg',
                    file_path=save_result['file_path']
                )

                activity_tracker.log_activity(user_id, "upload_file")
                await self.db.log_user_activity(user_id, "upload_file")

                await message.answer(
                    f"""📸 <b>Изображение сохранено!</b>\n\n"""
                    f"""📏 Размер: {save_result['file_size'] / 1024:.1f}KB\n"""
                    f"""🆔 ID файла: {save_result['file_id'][:8]}...""",
                    parse_mode="HTML"
                )
            else:
                await message.answer(f"""❌ Ошибка сохранения: {save_result['error']}""")

        except Exception as e:
            logger.error(f"""Error handling photo: {e}""")
            await message.answer("""❌ Произошла ошибка при обработке изображения.""")

    async def handle_document_upload(self, message: Message, user_id: int):
        """Обработать загрузку документа"""
        try:
            # Проверяем rate limit
            access_check = await security_manager.check_user_access(user_id, "file")
            if not access_check['allowed']:
                await message.answer(f"⚠️ {access_check['reason']}")
                return

            document = message.document
            file_info = await self.bot.get_file(document.file_id)
            file_content = await self.bot.download_file(file_info.file_path)

            # Определяем тип файла
            file_name = document.file_name or f"doc_{document.file_id}"
            file_category = self._get_file_category(file_name)

            # Валидируем файл
            file_data = {
                'file_name': file_name,
                'file_size': document.file_size or 0,
                'mime_type': document.mime_type or 'application/octet-stream'
            }

            validation = security_manager.validate_file_upload(file_data)
            if not validation['valid']:
                await message.answer(f"❌ {'; '.join(validation['errors'])}")
                return

            # Сохраняем файл
            save_result = await file_manager.save_file(
                file_content.read(),
                file_name,
                file_category,
                user_id
            )

            if save_result['success']:
                # Сохраняем в БД
                await self.db.add_file(
                    user_id=user_id,
                    file_id=save_result['file_id'],
                    original_name=file_name,
                    file_size=save_result['file_size'],
                    file_hash=save_result['file_hash'],
                    file_category=file_category,
                    mime_type=document.mime_type or 'application/octet-stream',
                    file_path=save_result['file_path']
                )

                activity_tracker.log_activity(user_id, "upload_file")
                await self.db.log_user_activity(user_id, "upload_file")

                size_mb = save_result['file_size'] / (1024 * 1024)
                emoji = self._get_category_emoji(file_category)
                await message.answer(
                    f"""{emoji} <b>Файл сохранен!</b>\n\n"""
                    f"""📄 {html.escape(file_name)}\n"""
                    f"""📏 Размер: {size_mb:.1f}MB\n"""
                    f"""🆔 ID файла: {save_result['file_id'][:8]}...""",
                    parse_mode="HTML"
                )
            else:
                await message.answer(f"""❌ Ошибка сохранения: {save_result['error']}""")

        except Exception as e:
            logger.error(f"""Error handling document: {e}""")
            await message.answer("""❌ Произошла ошибка при обработке файла.""")

    async def show_file_preview(self, callback: CallbackQuery, file_id: str):
        """Показать предпросмотр файла"""
        try:
            user_id = callback.from_user.id

            # Получаем информацию о файле
            file_info = await self.db.get_file_info(file_id, user_id)
            if not file_info:
                await callback.answer("Файл не найден", show_alert=True)
                return

            file_path = file_info['file_path']
            file_category = file_info['file_category']
            file_name = file_info['original_name']

            # Проверяем существование файла
            if not os.path.exists(file_path):
                await callback.answer("Файл не найден на сервере", show_alert=True)
                return

            # Для изображений показываем миниатюру
            if file_category == 'image':
                await self._show_image_preview(callback, file_path, file_name)
            elif file_category == 'document':
                await self._show_document_preview(callback, file_path, file_name, file_info)
            elif file_category == 'audio':
                await self._show_audio_preview(callback, file_path, file_name, file_info)
            else:
                await callback.answer("Предпросмотр недоступен для этого типа файлов", show_alert=True)

        except Exception as e:
            logger.error(f"Error showing file preview: {e}")
            await callback.answer("❌ Ошибка при загрузке предпросмотра", show_alert=True)

    async def _show_image_preview(self, callback: CallbackQuery, file_path: str, file_name: str):
        """Показать предпросмотр изображения"""
        try:
            # Отправляем изображение
            photo = FSInputFile(file_path)
            await self.bot.send_photo(
                chat_id=callback.from_user.id,
                photo=photo,
                caption=f"📸 {html.escape(file_name)}",
                parse_mode="HTML"
            )
            await callback.answer("Изображение отправлено")
        except Exception as e:
            logger.error(f"Error showing image preview: {e}")
            await callback.answer("❌ Ошибка при загрузке изображения", show_alert=True)

    async def _show_document_preview(self, callback: CallbackQuery, file_path: str, file_name: str, file_info: dict):
        """Показать предпросмотр документа"""
        try:
            # Определяем тип документа и пытаемся извлечь текст
            file_extension = Path(file_name).suffix.lower()

            if file_extension == '.txt':
                # Читаем текстовый файл
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()[:1000]  # Первые 1000 символов
                        text = f"📄 <b>{html.escape(file_name)}</b>\n\n<pre>{html.escape(content)}{'...' if len(content) >= 1000 else ''}</pre>"
                        await callback.message.answer(text, parse_mode="HTML")
                        await callback.answer("Предпросмотр отправлен")
                except Exception:
                    await callback.answer("Не удалось прочитать текстовый файл", show_alert=True)

            elif file_extension == '.pdf':
                await callback.answer("Предпросмотр PDF файлов в разработке", show_alert=True)

            else:
                # Для других документов показываем только информацию
                size_mb = file_info['file_size'] / (1024 * 1024)
                text = f"""📄 <b>{html.escape(file_name)}</b>

📏 Размер: {size_mb:.1f} МБ
📅 Загружен: {file_info['created_at'][:10]}

Предпросмотр недоступен для этого типа файлов."""

                await callback.message.answer(text, parse_mode="HTML")
                await callback.answer("Информация о файле отправлена")

        except Exception as e:
            logger.error(f"Error showing document preview: {e}")
            await callback.answer("❌ Ошибка при загрузке предпросмотра", show_alert=True)

    async def _show_audio_preview(self, callback: CallbackQuery, file_path: str, file_name: str, file_info: dict):
        """Показать предпросмотр аудио"""
        try:
            size_mb = file_info['file_size'] / (1024 * 1024)
            text = f"""🎵 <b>{html.escape(file_name)}</b>

📏 Размер: {size_mb:.1f} МБ
📅 Загружен: {file_info['created_at'][:10]}

Аудиофайл сохранен в системе."""

            await callback.message.answer(text, parse_mode="HTML")
            await callback.answer("Информация об аудиофайле отправлена")
        except Exception as e:
            logger.error(f"Error showing audio preview: {e}")
            await callback.answer("❌ Ошибка при загрузке информации", show_alert=True)

    async def download_file(self, callback: CallbackQuery, file_id: str):
        """Скачать файл пользователю"""
        try:
            user_id = callback.from_user.id

            # Получаем информацию о файле
            file_info = await self.db.get_file_info(file_id, user_id)
            if not file_info:
                await callback.answer("Файл не найден", show_alert=True)
                return

            file_path = file_info['file_path']
            file_name = file_info['original_name']

            # Проверяем существование файла
            if not os.path.exists(file_path):
                await callback.answer("Файл не найден на сервере", show_alert=True)
                return

            # Отправляем файл
            document = FSInputFile(file_path, filename=file_name)

            if file_info['file_category'] == 'image':
                await self.bot.send_photo(
                    chat_id=callback.from_user.id,
                    photo=document,
                    caption=f"📸 {file_name}"
                )
            else:
                await self.bot.send_document(
                    chat_id=callback.from_user.id,
                    document=document,
                    caption=f"📄 {file_name}"
                )

            await callback.answer("Файл отправлен")

        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            await callback.answer("❌ Ошибка при отправке файла", show_alert=True)

    async def delete_file_confirm(self, callback: CallbackQuery, file_id: str):
        """Подтвердить удаление файла"""
        try:
            user_id = callback.from_user.id

            # Получаем информацию о файле
            file_info = await self.db.get_file_info(file_id, user_id)
            if not file_info:
                await callback.answer("Файл не найден", show_alert=True)
                return

            file_name = file_info['original_name']
            text = f"""🗑 <b>Удалить файл?</b>

📄 {html.escape(file_name)}

Это действие нельзя отменить."""

            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.confirm_action("delete_file", file_id),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in delete confirmation: {e}")
            await callback.answer("❌ Ошибка при удалении файла", show_alert=True)

    async def delete_file_execute(self, callback: CallbackQuery, file_id: str):
        """Выполнить удаление файла"""
        try:
            user_id = callback.from_user.id

            # Получаем информацию о файле
            file_info = await self.db.get_file_info(file_id, user_id)
            if not file_info:
                await callback.answer("Файл не найден", show_alert=True)
                return

            file_path = file_info['file_path']

            # Удаляем из файловой системы
            if os.path.exists(file_path):
                os.remove(file_path)

            # Удаляем из базы данных
            success = await self.db.delete_file(file_id, user_id)

            if success:
                activity_tracker.log_activity(user_id, "delete_file", {"file_id": file_id})
                await self.db.log_user_activity(user_id, "delete_file", json.dumps({"file_id": file_id}, ensure_ascii=False))
                await callback.answer("Файл удален", show_alert=True)
                await self.show_files_menu(callback.message, user_id, edit=True)
            else:
                await callback.answer("Не удалось удалить файл", show_alert=True)

        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            await callback.answer("❌ Ошибка при удалении файла", show_alert=True)

    def _get_category_emoji(self, category: str) -> str:
        """Получить эмодзи для категории файла"""
        emojis = {
            'image': '🖼️',
            'document': '📄',
            'audio': '🎵',
            'video': '🎥',
            'archive': '📦',
            'other': '📎'
        }
        return emojis.get(category, '📎')

    def _get_file_category(self, file_name: str) -> str:
        """Определить категорию файла по расширению"""
        extension = Path(file_name).suffix.lower()

        if extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
            return 'image'
        elif extension in ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt']:
            return 'document'
        elif extension in ['.mp3', '.wav', '.ogg', '.m4a', '.flac']:
            return 'audio'
        elif extension in ['.mp4', '.avi', '.mov', '.mkv']:
            return 'video'
        elif extension in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            return 'archive'
        else:
            return 'other'

    async def _safe_edit_or_send(self, message: Message, text: str, reply_markup=None, *, parse_mode: str = "HTML", edit: bool = True):
        """Безопасное редактирование или отправка сообщения"""
        if edit:
            try:
                await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
                return
            except Exception:
                pass
        await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)

