"""
Состояния FSM для NotesBot
"""

from aiogram.fsm.state import State, StatesGroup


class NoteStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_content = State()
    waiting_for_category = State()
    editing_note = State()
    editing_content = State()


class ReminderStates(StatesGroup):
    creating_reminder = State()
    waiting_for_reminder_title = State()
    waiting_for_reminder_text = State()
    waiting_for_reminder_time = State()
    waiting_for_reminder_repeat = State()
    editing_reminder = State()
    editing_time = State()


class CategoryStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_color = State()


class FileStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_description = State()


class TaskStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_repeat_type = State()
    waiting_for_start_date = State()


class TimeBlockStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    waiting_for_category = State()


class GoalStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_target = State()
    waiting_for_unit = State()
    waiting_for_deadline = State()
