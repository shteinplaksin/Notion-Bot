"""
Финальное тестирование NotesBot
"""

import sys
import asyncio
sys.path.append('C:/Users/Alex/Desktop/bot/project_bot')

async def test_all():
    print("Testing NotesBot...")

    try:
        # Тестируем импорты
        print("1. Проверка импортов...")
        from bot_modular import bot, dp, db
        from config import BOT_TOKEN, DATABASE_PATH
        from keyboards import Keyboards
        from time_utils import TimeParser
        from states import NoteStates, ReminderStates
        from user_data import get_user_data
        from security import security_manager
        from file_manager import file_manager
        from analytics import activity_tracker
        from task_manager import TaskManager
        print("All imports successful")

        # Тестируем базу данных
        print("2. Проверка базы данных...")
        await db.init_db()
        print("Database initialized")

        # Тестируем создание пользователя и заметки
        test_user_id = 123456789
        await db.add_user(test_user_id, 'test_user', 'Test', 'User', 'ru')

        note_id = await db.add_note(test_user_id, 'Test Note', 'Note content', 'general')
        print(f"Note created with ID: {note_id}")

        notes = await db.get_notes(test_user_id)
        print(f"Notes retrieved: {len(notes)}")

        # Тестируем клавиатуры
        print("3. Checking keyboards...")
        main_menu = Keyboards.main_menu()
        notes_menu = Keyboards.notes_menu()
        print("Keyboards created")

        # Тестируем парсер времени
        print("4. Checking time parser...")
        parser = TimeParser()
        test_time = parser.parse_time("tomorrow at 15:30")
        print(f"Time parsed: {test_time}")

        # Тестируем токен бота
        print("5. Checking bot token...")
        if BOT_TOKEN and len(BOT_TOKEN) > 30:
            print("Bot token looks valid")
        else:
            print("WARNING: Bot token may be invalid")

        print("All tests passed!")
        print("Bot is ready!")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_all())
