from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from datetime import datetime, timedelta
import logging
import html

from database import Database
from keyboards import Keyboards
from states import ReminderStates
from time_utils import parse_time_input

router = Router()
logger = logging.getLogger(__name__)


class ReminderHandlers:
    """Обработчики для управления напоминаниями"""

    def __init__(self, db: Database, bot: Bot):
        self.db = db
        self.bot = bot

    async def show_reminders_menu(self, message: Message, *, edit: bool = False):
        """Показать меню напоминаний"""
        text = """⏰ <b>Напоминания</b>\n\nВыберите действие ниже, чтобы создать новое напоминание или управлять существующими."""
        await self._safe_edit_or_send(message, text, reply_markup=Keyboards.reminders_menu(), edit=edit)

    async def _safe_edit_or_send(self, message: Message, text: str, reply_markup=None, *, edit: bool = False, parse_mode="HTML"):
        """Безопасно отправить или отредактировать сообщение"""
        try:
            if edit and message.message_id:
                await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            else:
                await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            # Если редактирование не удалось, отправляем новое сообщение
            await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)

    async def quick_reminder_creation(self, message: Message):
        """Быстрое создание напоминания из команды /remind"""
        try:
            args = message.text.split(maxsplit=1)
            if len(args) > 1:
                reminder_text = args[1]

                # Получаем время по умолчанию (через 1 час)
                reminder_time = datetime.now() + timedelta(hours=1)

                await self.db.add_reminder(
                    user_id=message.from_user.id,
                    title=reminder_text[:100],
                    content=reminder_text,
                    reminder_time=reminder_time,
                    repeat_type="none"
                )

                await message.answer(
                    f"✅ Напоминание создано!\n⏰ Время: {reminder_time.strftime('%d.%m.%Y %H:%M')}\n📝 Текст: {reminder_text}",
                    reply_markup=Keyboards.reminders_menu()
                )
        except Exception as e:
            logger.error(f"Error in quick reminder creation: {e}")
            await message.answer("❌ Ошибка при создании напоминания.")

    async def start_reminder_creation(self, message: Message, state: FSMContext):
        """Начать процесс создания напоминания"""
        await state.set_state(ReminderStates.creating_reminder)
        await message.edit_text(
            "⏰ <b>Создание напоминания</b>\n\nНастройте параметры ниже и нажмите 'Готово'.",
            reply_markup=Keyboards.reminder_creation_menu(),
            parse_mode="HTML"
        )

    async def show_active_reminders(self, message: Message, user_id: int, *, edit: bool = False):
        """Показать активные напоминания"""
        reminders = await self.db.get_active_reminders(user_id)

        if reminders:
            text = "📋 <b>Активные напоминания</b>\n\n"
            for i, reminder in enumerate(reminders[:10], 1):  # Показываем до 10 напоминаний
                reminder_time = reminder.get('reminder_time', '')
                title = reminder.get('title', 'Без названия')[:50]
                text += f"{i}. {title}\n   ⏰ {reminder_time}\n\n"

            if len(reminders) > 10:
                text += f"... и еще {len(reminders) - 10} напоминаний"
        else:
            text = "📋 <b>Активные напоминания</b>\n\nУ вас нет активных напоминаний."

        await self._safe_edit_or_send(message, text, reply_markup=Keyboards.reminders_menu(), edit=edit)

    async def show_today_reminders(self, message: Message, user_id: int, *, edit: bool = False):
        """Показать напоминания на сегодня"""
        # Получаем все активные напоминания и фильтруем по сегодняшней дате
        all_reminders = await self.db.get_active_reminders(user_id)
        today = datetime.now().date()

        today_reminders = []
        for reminder in all_reminders:
            reminder_date = None
            try:
                # Пробуем распарсить дату из reminder_time
                if isinstance(reminder.get('reminder_time'), str):
                    reminder_datetime = datetime.fromisoformat(reminder['reminder_time'].replace('Z', '+00:00'))
                else:
                    reminder_datetime = reminder.get('reminder_time')

                if reminder_datetime and reminder_datetime.date() == today:
                    today_reminders.append(reminder)
            except (ValueError, AttributeError):
                continue

        if today_reminders:
            text = "📅 <b>Напоминания на сегодня</b>\n\n"
            for i, reminder in enumerate(today_reminders[:10], 1):
                reminder_time = reminder.get('reminder_time', '')
                title = reminder.get('title', 'Без названия')[:50]
                text += f"{i}. {title}\n   ⏰ {reminder_time}\n\n"

            if len(today_reminders) > 10:
                text += f"... и еще {len(today_reminders) - 10} напоминаний"
        else:
            text = "📅 <b>Напоминания на сегодня</b>\n\nНа сегодня напоминаний нет."

        await self._safe_edit_or_send(message, text, reply_markup=Keyboards.reminders_menu(), edit=edit)

    async def show_week_reminders(self, message: Message, user_id: int, *, edit: bool = False):
        """Показать напоминания на неделю"""
        # Получаем все активные напоминания и фильтруем по текущей неделе
        all_reminders = await self.db.get_active_reminders(user_id)
        today = datetime.now().date()
        week_end = today + timedelta(days=7)

        week_reminders = []
        for reminder in all_reminders:
            reminder_date = None
            try:
                # Пробуем распарсить дату из reminder_time
                if isinstance(reminder.get('reminder_time'), str):
                    reminder_datetime = datetime.fromisoformat(reminder['reminder_time'].replace('Z', '+00:00'))
                else:
                    reminder_datetime = reminder.get('reminder_time')

                if reminder_datetime and today <= reminder_datetime.date() <= week_end:
                    week_reminders.append(reminder)
            except (ValueError, AttributeError):
                continue

        if week_reminders:
            text = "🗓 <b>Напоминания на неделю</b>\n\n"
            for i, reminder in enumerate(week_reminders[:10], 1):
                reminder_time = reminder.get('reminder_time', '')
                title = reminder.get('title', 'Без названия')[:50]
                text += f"{i}. {title}\n   ⏰ {reminder_time}\n\n"

            if len(week_reminders) > 10:
                text += f"... и еще {len(week_reminders) - 10} напоминаний"
        else:
            text = "🗓 <b>Напоминания на неделю</b>\n\nНа эту неделю напоминаний нет."

        await self._safe_edit_or_send(message, text, reply_markup=Keyboards.reminders_menu(), edit=edit)


@router.message(Command("remind"))
async def cmd_remind(message: Message, state: FSMContext, advanced_handlers):
    """Быстрое создание напоминания"""
    try:
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            await advanced_handlers.handle_reminder_creation(message, state)
        else:
            await state.set_state(ReminderStates.waiting_for_reminder_title)
            await message.answer(
                "⏰ <b>Создание напоминания</b>\n\nВведите заголовок напоминания:",
                parse_mode="HTML"
            )
    except Exception as e:
        # logger.error(f"Error in remind command: {e}")
        await message.answer("❌ Ошибка при создании напоминания.")

@router.callback_query(F.data == "create_reminder")
async def callback_create_reminder(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ReminderStates.creating_reminder)
    await callback.message.edit_text(
        "⏰ <b>Создание напоминания</b>\n\nНастройте параметры ниже и нажмите 'Готово'.",
        reply_markup=Keyboards.reminder_creation_menu(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "set_reminder_text", ReminderStates.creating_reminder)
async def set_reminder_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ReminderStates.waiting_for_reminder_text)
    await callback.message.edit_text("Введите текст напоминания:")

@router.message(ReminderStates.waiting_for_reminder_text)
async def process_reminder_text(message: Message, state: FSMContext):
    await state.update_data(reminder_text=message.text)
    await state.set_state(ReminderStates.creating_reminder)
    await message.answer("Текст напоминания сохранен.", reply_markup=Keyboards.reminder_creation_menu())

@router.callback_query(F.data == "set_reminder_time", ReminderStates.creating_reminder)
async def set_reminder_time(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ReminderStates.waiting_for_reminder_time)
    await callback.message.edit_text("Выберите время для напоминания:", reply_markup=Keyboards.time_presets())

@router.callback_query(F.data.startswith("time_"), ReminderStates.waiting_for_reminder_time)
async def process_reminder_time_preset(callback: CallbackQuery, state: FSMContext):
    preset = callback.data.split("_")[1]
    now = datetime.now()
    if preset == "5min":
        reminder_time = now + timedelta(minutes=5)
    elif preset == "15min":
        reminder_time = now + timedelta(minutes=15)
    elif preset == "30min":
        reminder_time = now + timedelta(minutes=30)
    elif preset == "1hour":
        reminder_time = now + timedelta(hours=1)
    elif preset == "tomorrow":
        reminder_time = now + timedelta(days=1)
    elif preset == "day_after":
        reminder_time = now + timedelta(days=2)
    else:
        await callback.answer("Некорректный пресет времени", show_alert=True)
        return

    await state.update_data(reminder_time=reminder_time)
    await state.set_state(ReminderStates.creating_reminder)
    await callback.message.edit_text(
        f"Время установлено: {reminder_time.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=Keyboards.reminder_creation_menu()
    )

@router.message(ReminderStates.waiting_for_reminder_time)
async def process_reminder_time_custom(message: Message, state: FSMContext):
    reminder_time, _ = parse_time_input(message.text)
    if not reminder_time:
        await message.answer("Не удалось распознать время. Попробуйте еще раз.")
        return

    await state.update_data(reminder_time=reminder_time)
    await state.set_state(ReminderStates.creating_reminder)
    await message.answer(
        f"Время установлено: {reminder_time.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=Keyboards.reminder_creation_menu()
    )

@router.callback_query(F.data == "set_reminder_repeat", ReminderStates.creating_reminder)
async def set_reminder_repeat(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Выберите интервал повторения:", reply_markup=Keyboards.repeat_options())

@router.callback_query(F.data.startswith("repeat_"), ReminderStates.creating_reminder)
async def process_reminder_repeat(callback: CallbackQuery, state: FSMContext):
    repeat_type = callback.data.split("_")[1]
    await state.update_data(reminder_repeat=repeat_type)
    await state.set_state(ReminderStates.creating_reminder)
    await callback.message.edit_text(f"Интервал повторения установлен: {repeat_type}", reply_markup=Keyboards.reminder_creation_menu())

@router.callback_query(F.data == "finish_reminder_creation", ReminderStates.creating_reminder)
async def finish_reminder_creation(callback: CallbackQuery, state: FSMContext, db):
    data = await state.get_data()
    reminder_text = data.get("reminder_text")
    reminder_time = data.get("reminder_time")
    reminder_repeat = data.get("reminder_repeat", "none")

    if not reminder_text or not reminder_time:
        await callback.answer("Необходимо указать текст и время напоминания", show_alert=True)
        return

    await db.add_reminder(
        user_id=callback.from_user.id,
        title=reminder_text[:100],
        content=reminder_text,
        reminder_time=reminder_time,
        repeat_type=reminder_repeat
    )

    await state.clear()
    await callback.message.edit_text("✅ Напоминание успешно создано!", reply_markup=Keyboards.reminders_menu())

@router.callback_query(F.data == "cancel_reminder_creation", ReminderStates.creating_reminder)
async def cancel_reminder_creation(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Создание напоминания отменено.", reply_markup=Keyboards.reminders_menu())
