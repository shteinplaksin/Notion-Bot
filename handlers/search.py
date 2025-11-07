"""
Обработчики поиска для NotesBot
"""

import asyncio
import json
import html
import logging
from typing import Dict, Any, Optional, List

from aiogram import F, Router, Bot
from aiogram.types import Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.fsm.context import FSMContext

from database import Database

router = Router()

# Обработчик инлайн-запросов будет добавлен в bot_modular.py

from keyboards import Keyboards
from analytics import activity_tracker

logger = logging.getLogger(__name__)


class SearchHandlers:
    """Обработчики для поиска"""

    def __init__(self, db: Database, bot: Bot):
        self.db = db
        self.bot = bot

    async def start_search(self, message: Message, user_id: int, state: FSMContext, edit: bool = False):
        """Начать поиск по заметкам"""
        await state.update_data(awaiting_note_search=True)
        text = "🔍 <b>Поиск заметок</b>\n\nОтправьте ключевые слова или фразу для поиска."

        if edit:
            await message.edit_text(text, reply_markup=Keyboards.back_button("notes_menu"), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=Keyboards.back_button("notes_menu"), parse_mode="HTML")

    async def process_search_query(self, message: Message, user_id: int):
        """Обработать поисковый запрос"""
        query = message.text.strip()
        if len(query) < 2:
            await message.answer(
                "🔍 <b>Поиск</b>\n\nВведите минимум 2 символа для поиска.",
                parse_mode="HTML"
            )
            return

        try:
            # Поиск по заметкам
            notes = await self.db.search_notes(user_id, query, limit=10)

            if not notes:
                await message.answer(
                    f"🔍 <b>Поиск: '{query}'</b>\n\nНичего не найдено. Попробуйте другие ключевые слова.",
                    parse_mode="HTML"
                )
                return

            text = f"🔍 <b>Результаты поиска: '{query}'</b>\n\n"
            for note in notes:
                pinned = "📌 " if note['is_pinned'] else ""
                title = note.get('title', 'Без названия')[:40]
                text += f"{pinned}<b>{html.escape(title)}</b>\n"

                if note.get('content'):
                    # Подсвечиваем найденные слова
                    content = note['content'][:150] + "..." if len(note['content']) > 150 else note['content']
                    # Здесь можно добавить подсветку найденных слов
                    text += f"<i>{html.escape(content)}</i>\n"

                text += f"📁 {note['category']} • {note['created_at'][:10]}\n\n"

            # Добавляем кнопки для действий с результатами поиска
            keyboard = Keyboards.search_results_keyboard(query)

            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error in search: {e}")
            await message.answer("❌ Ошибка при поиске.")

    async def advanced_search(self, message: Message, user_id: int):
        """Расширенный поиск с фильтрами"""
        await message.answer(
            "🔍 <b>Расширенный поиск</b>\n\n"
            "Используйте следующие фильтры:\n"
            "• <code>category:работа</code> - поиск в категории\n"
            "• <code>date:2024</code> - поиск по году\n"
            "• <code>tag:важное</code> - поиск по тегам\n"
            "• <code>title:заметка</code> - поиск только в заголовках\n\n"
            "Пример: <code>category:работа важный проект</code>",
            parse_mode="HTML"
        )

    async def search_in_category(self, callback: CallbackQuery, category_name: str, query: str):
        """Поиск в конкретной категории"""
        user_id = callback.from_user.id

        try:
            # Получаем заметки категории
            category_notes = await self.db.get_notes(user_id, category=category_name, limit=100)

            # Фильтруем по поисковому запросу
            filtered_notes = []
            for note in category_notes:
                title_match = query.lower() in (note.get('title', '') or '').lower()
                content_match = query.lower() in (note.get('content', '') or '').lower()

                if title_match or content_match:
                    filtered_notes.append(note)

            if not filtered_notes:
                await callback.answer(f"В категории '{category_name}' ничего не найдено по запросу '{query}'", show_alert=True)
                return

            text = f"🔍 <b>Поиск в категории '{category_name}': '{query}'</b>\n\n"
            for note in filtered_notes[:10]:
                pinned = "📌 " if note['is_pinned'] else ""
                title = note.get('title', 'Без названия')[:40]
                text += f"{pinned}<b>{html.escape(title)}</b>\n"

                if note.get('content'):
                    content = note['content'][:100] + "..." if len(note['content']) > 100 else note['content']
                    text += f"<i>{html.escape(content)}</i>\n"

                text += f"📅 {note['created_at'][:10]}\n\n"

            await callback.message.edit_text(text, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error in category search: {e}")
            await callback.answer("❌ Ошибка при поиске в категории", show_alert=True)

    async def search_by_date_range(self, message: Message, user_id: int, start_date: str, end_date: str):
        """Поиск по диапазону дат"""
        try:
            # Здесь можно реализовать поиск по датам
            # Пока заглушка
            await message.answer(
                "📅 <b>Поиск по датам</b>\n\n"
                f"Поиск заметок с {start_date} по {end_date}\n\n"
                "Функция находится в разработке.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in date search: {e}")
            await message.answer("❌ Ошибка при поиске по датам.")

    async def handle_inline_search(self, inline_query: InlineQuery) -> None:
        """Обработка инлайн-запросов поиска"""
        try:
            query = inline_query.query.strip()
            user_id = inline_query.from_user.id

            if not query:
                # Показываем популярные заметки
                notes = await self.db.get_notes(user_id, limit=10)
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
            search_results = await self.search_notes(query, user_id, limit=10)

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
            logger.error(f"Error in inline search: {e}")

    async def search_notes(self, query: str, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Поиск заметок по запросу"""
        try:
            # Получаем заметки пользователя
            notes = await self.db.get_notes(user_id, limit=limit * 2)  # Берем больше для фильтрации

            results = []
            query_lower = query.lower()

            for note in notes:
                title = note.get("title", "").lower()
                content = note.get("content", "").lower()

                # Проверяем совпадения
                if (query_lower in title or
                    query_lower in content or
                    any(word in title for word in query_lower.split()) or
                    any(word in content for word in query_lower.split())):

                    # Вычисляем релевантность
                    relevance = 0
                    if query_lower in title:
                        relevance += 10
                    if query_lower in content:
                        relevance += 5
                    for word in query_lower.split():
                        if word in title:
                            relevance += 3
                        if word in content:
                            relevance += 1

                    results.append({
                        **note,
                        "search_relevance": relevance
                    })

            # Сортируем по релевантности
            results.sort(key=lambda x: x["search_relevance"], reverse=True)

            return results[:limit]

        except Exception as e:
            logger.error(f"Error searching notes: {e}")
            return []
