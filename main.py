"""
Основной файл запуска NotesBot Professional
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем текущую директорию в путь поиска модулей
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

from bot_modular import bot, dp, db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота"""
    try:
        logger.info("🚀 Запуск NotesBot Professional...")

        # Инициализация базы данных
        logger.info("📊 Инициализация базы данных...")
        await db.init_db()
        logger.info("✅ База данных готова")

        # Проверка токена бота
        if not bot.token:
            logger.error("❌ Токен бота не найден в конфигурации")
            return

        if len(bot.token) < 45:
            logger.warning("⚠️ Токен бота выглядит подозрительно коротким")

        logger.info("🤖 Бот готов к работе")
        logger.info("📋 Функции: заметки, напоминания, файлы, аналитика")
        logger.info("🎯 Запуск polling...")

        # Запуск бота
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "inline_query"],
            skip_updates=True
        )

    except KeyboardInterrupt:
        logger.info("🛑 Остановка по запросу пользователя")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        logger.error("📍 Подробности:", exc_info=True)
    finally:
        logger.info("🔄 Завершение работы...")
        try:
            await bot.session.close()
        except:
            pass
        logger.info("✅ NotesBot остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 До свидания!")
    except Exception as e:
        logger.error(f"💥 Неожиданная ошибка при запуске: {e}")
        sys.exit(1)
