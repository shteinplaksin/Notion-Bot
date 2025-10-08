"""
Мониторинг и health checks для NotesBot
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

from aiohttp import web
from aiohttp.web import Request, Response

from database import Database
from config import DEBUG

logger = logging.getLogger(__name__)

class HealthMonitor:
    """Мониторинг состояния бота"""

    def __init__(self, db: Database):
        self.db = db
        self.start_time = datetime.now()
        self.last_check = datetime.now()

    async def health_check(self) -> Dict[str, Any]:
        """Основная проверка здоровья"""
        self.last_check = datetime.now()

        health_status = {
            "status": "healthy",
            "timestamp": self.last_check.isoformat(),
            "uptime_seconds": (self.last_check - self.start_time).total_seconds(),
            "checks": {}
        }

        # Проверка базы данных
        try:
            await self.db.execute("SELECT 1")
            health_status["checks"]["database"] = {"status": "healthy"}
        except Exception as e:
            health_status["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
            health_status["status"] = "unhealthy"

        # Проверка памяти и процессов
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()

            health_status["checks"]["memory"] = {
                "status": "healthy",
                "rss_mb": memory_info.rss / 1024 / 1024,
                "vms_mb": memory_info.vms / 1024 / 1024
            }
        except ImportError:
            health_status["checks"]["memory"] = {"status": "unknown", "message": "psutil not installed"}
        except Exception as e:
            health_status["checks"]["memory"] = {"status": "error", "error": str(e)}

        return health_status

    async def get_stats(self) -> Dict[str, Any]:
        """Получение статистики бота"""
        stats = {
            "timestamp": self.last_check.isoformat(),
            "uptime_seconds": (self.last_check - self.start_time).total_seconds(),
            "bot_info": {}
        }

        try:
            # Количество пользователей
            users_count = await self.db.execute("SELECT COUNT(*) as count FROM users", fetch_one=True)
            stats["bot_info"]["total_users"] = users_count["count"] if users_count else 0

            # Количество заметок
            notes_count = await self.db.execute("SELECT COUNT(*) as count FROM notes", fetch_one=True)
            stats["bot_info"]["total_notes"] = notes_count["count"] if notes_count else 0

            # Количество напоминаний
            reminders_count = await self.db.execute("SELECT COUNT(*) as count FROM reminders WHERE is_active = TRUE", fetch_one=True)
            stats["bot_info"]["active_reminders"] = reminders_count["count"] if reminders_count else 0

            # Количество файлов
            files_count = await self.db.execute("SELECT COUNT(*) as count FROM files", fetch_one=True)
            stats["bot_info"]["total_files"] = files_count["count"] if files_count else 0

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            stats["bot_info"]["error"] = str(e)

        return stats

async def create_monitoring_app(db: Database) -> web.Application:
    """Создание приложения мониторинга"""
    monitor = HealthMonitor(db)

    async def health_endpoint(request: Request) -> Response:
        """Эндпоинт проверки здоровья"""
        health_data = await monitor.health_check()

        status_code = 200 if health_data["status"] == "healthy" else 503
        return web.json_response(health_data, status=status_code)

    async def stats_endpoint(request: Request) -> Response:
        """Эндпоинт статистики"""
        stats_data = await monitor.get_stats()
        return web.json_response(stats_data)

    async def metrics_endpoint(request: Request) -> Response:
        """Эндпоинт метрик в формате Prometheus"""
        health_data = await monitor.health_check()

        metrics = []
        metrics.append(f"notesbot_uptime_seconds {health_data['uptime_seconds']}")
        metrics.append(f"notesbot_status {1 if health_data['status'] == 'healthy' else 0}")

        for check_name, check_data in health_data["checks"].items():
            status = 1 if check_data.get("status") == "healthy" else 0
            metrics.append(f"notesbot_check_{check_name} {status}")

        # Добавляем статистику пользователей и заметок
        stats_data = await monitor.get_stats()
        bot_info = stats_data.get("bot_info", {})

        if "total_users" in bot_info:
            metrics.append(f"notesbot_total_users {bot_info['total_users']}")
        if "total_notes" in bot_info:
            metrics.append(f"notesbot_total_notes {bot_info['total_notes']}")
        if "active_reminders" in bot_info:
            metrics.append(f"notesbot_active_reminders {bot_info['active_reminders']}")
        if "total_files" in bot_info:
            metrics.append(f"notesbot_total_files {bot_info['total_files']}")

        response_text = "\n".join(metrics) + "\n"
        return web.Response(text=response_text, content_type="text/plain")

    app = web.Application()

    # Добавляем маршруты
    app.router.add_get("/health", health_endpoint)
    app.router.add_get("/stats", stats_endpoint)
    app.router.add_get("/metrics", metrics_endpoint)

    # Добавляем CORS если в режиме отладки
    if DEBUG:
        from aiohttp_cors import setup as cors_setup, ResourceOptions

        cors_setup(app, defaults={
            "*": ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*"
            )
        })

    return app

async def start_monitoring_server(db: Database, host: str = "0.0.0.0", port: int = 8080) -> None:
    """Запуск сервера мониторинга"""
    app = await create_monitoring_app(db)

    logger.info(f"Starting monitoring server on {host}:{port}")
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info("Monitoring server started")

    # Бесконечный цикл для поддержания сервера
    while True:
        await asyncio.sleep(3600)  # Проверяем каждые час
