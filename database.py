import aiosqlite
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "notes_bot.db"):
        self.db_path = db_path

    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    language_code TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    settings TEXT DEFAULT '{}'
                )
            """)
            
            # Таблица заметок
            await db.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    content TEXT,
                    category TEXT DEFAULT 'general',
                    tags TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_pinned BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Таблица напоминаний
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    note_id INTEGER,
                    title TEXT NOT NULL,
                    content TEXT,
                    reminder_time TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    repeat_type TEXT DEFAULT 'none',
                    repeat_interval INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (note_id) REFERENCES notes (id)
                )
            """)
            
            # Таблица категорий
            await db.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT NOT NULL,
                    color TEXT DEFAULT '#3498db',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    UNIQUE(user_id, name)
                )
            """)
            
            # Таблица файлов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    file_id TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    file_size INTEGER,
                    file_hash TEXT,
                    file_category TEXT,
                    mime_type TEXT,
                    file_path TEXT,
                    note_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (note_id) REFERENCES notes (id)
                )
            """)
            
            # Таблица повторяющихся задач
            await db.execute("""
                CREATE TABLE IF NOT EXISTS recurring_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    repeat_type TEXT NOT NULL,
                    repeat_interval INTEGER DEFAULT 1,
                    start_date TIMESTAMP,
                    end_date TIMESTAMP,
                    next_due TIMESTAMP,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Таблица временных блоков
            await db.execute("""
                CREATE TABLE IF NOT EXISTS time_blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    category TEXT DEFAULT 'work',
                    color TEXT DEFAULT '#3498db',
                    is_recurring BOOLEAN DEFAULT FALSE,
                    recurring_pattern TEXT,
                    status TEXT DEFAULT 'scheduled',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Таблица целей и прогресса
            await db.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    target_value REAL NOT NULL,
                    current_value REAL DEFAULT 0.0,
                    unit TEXT DEFAULT 'штук',
                    deadline TIMESTAMP,
                    category TEXT DEFAULT 'general',
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Таблица истории прогресса
            await db.execute("""
                CREATE TABLE IF NOT EXISTS progress_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id INTEGER,
                    value_change REAL NOT NULL,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (goal_id) REFERENCES goals (id)
                )
            """)
            
            # Таблица активности пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action_type TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Создаем индексы для оптимизации
            await db.execute("CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes (user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_notes_category ON notes (category)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes (created_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders (user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders (reminder_time)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_files_user_id ON files (user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON recurring_tasks (user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_blocks_user_time ON time_blocks (user_id, start_time)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_goals_user_id ON goals (user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_activity_user_time ON user_activity (user_id, timestamp)")
            
            await db.commit()

    async def add_user(self, user_id: int, username: str = None, first_name: str = None, 
                      last_name: str = None, language_code: str = None):
        """Добавление пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, language_code)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, language_code))
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def add_note(self, user_id: int, title: str, content: str = "", 
                      category: str = "general", tags: List[str] = None) -> int:
        """Добавление заметки"""
        if tags is None:
            tags = []
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO notes (user_id, title, content, category, tags)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, title, content, category, json.dumps(tags)))
            await db.commit()
            return cursor.lastrowid

    async def get_notes(self, user_id: int, category: str = None, 
                       limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Получение заметок пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if category:
                query = """
                    SELECT * FROM notes 
                    WHERE user_id = ? AND category = ?
                    ORDER BY is_pinned DESC, updated_at DESC
                    LIMIT ? OFFSET ?
                """
                params = (user_id, category, limit, offset)
            else:
                query = """
                    SELECT * FROM notes 
                    WHERE user_id = ?
                    ORDER BY is_pinned DESC, updated_at DESC
                    LIMIT ? OFFSET ?
                """
                params = (user_id, limit, offset)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_note(self, note_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение конкретной заметки"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM notes WHERE id = ? AND user_id = ?
            """, (note_id, user_id)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_note(self, note_id: int, user_id: int, title: str = None, 
                         content: str = None, category: str = None, 
                         tags: List[str] = None, is_pinned: bool = None) -> bool:
        """Обновление заметки"""
        updates = []
        params = []
        
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
        if is_pinned is not None:
            updates.append("is_pinned = ?")
            params.append(is_pinned)
        
        if not updates:
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([note_id, user_id])
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"""
                UPDATE notes SET {', '.join(updates)}
                WHERE id = ? AND user_id = ?
            """, params)
            await db.commit()
            return cursor.rowcount > 0

    async def delete_note(self, note_id: int, user_id: int) -> bool:
        """Удаление заметки"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM notes WHERE id = ? AND user_id = ?
            """, (note_id, user_id))
            await db.commit()
            return cursor.rowcount > 0

    async def search_notes(self, user_id: int, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Поиск заметок"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM notes 
                WHERE user_id = ? AND (title LIKE ? OR content LIKE ?)
                ORDER BY is_pinned DESC, updated_at DESC
                LIMIT ?
            """, (user_id, f"%{query}%", f"%{query}%", limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def add_reminder(self, user_id: int, title: str, content: str, 
                          reminder_time: datetime, note_id: int = None,
                          repeat_type: str = "none", repeat_interval: int = 0) -> int:
        """Добавление напоминания"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO reminders (user_id, note_id, title, content, reminder_time, repeat_type, repeat_interval)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, note_id, title, content, reminder_time, repeat_type, repeat_interval))
            await db.commit()
            return cursor.lastrowid

    async def get_active_reminders(self, user_id: int = None) -> List[Dict[str, Any]]:
        """Получение активных напоминаний"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if user_id:
                query = """
                    SELECT * FROM reminders 
                    WHERE user_id = ? AND is_active = TRUE AND reminder_time > datetime('now')
                    ORDER BY reminder_time ASC
                """
                params = (user_id,)
            else:
                query = """
                    SELECT * FROM reminders 
                    WHERE is_active = TRUE AND reminder_time <= datetime('now')
                    ORDER BY reminder_time ASC
                """
                params = ()
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def update_reminder(self, reminder_id: int, user_id: int, **kwargs) -> bool:
        """Обновление напоминания"""
        updates = []
        params = []
        
        for key, value in kwargs.items():
            if key in ['title', 'content', 'reminder_time', 'is_active', 'repeat_type', 'repeat_interval']:
                updates.append(f"{key} = ?")
                params.append(value)
        
        if not updates:
            return False
        
        params.extend([reminder_id, user_id])
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"""
                UPDATE reminders SET {', '.join(updates)}
                WHERE id = ? AND user_id = ?
            """, params)
            await db.commit()
            return cursor.rowcount > 0

    async def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        """Удаление напоминания"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM reminders WHERE id = ? AND user_id = ?
            """, (reminder_id, user_id))
            await db.commit()
            return cursor.rowcount > 0

    async def add_category(self, user_id: int, name: str, color: str = "#3498db") -> bool:
        """Добавление категории"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO categories (user_id, name, color)
                    VALUES (?, ?, ?)
                """, (user_id, name, color))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def get_categories(self, user_id: int) -> List[Dict[str, Any]]:
        """Получение категорий пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM categories WHERE user_id = ?
                ORDER BY name ASC
            """, (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def delete_category(self, category_id: int, user_id: int) -> bool:
        """Удаление категории"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM categories WHERE id = ? AND user_id = ?
            """, (category_id, user_id))
            await db.commit()
            return cursor.rowcount > 0

    # Методы для работы с файлами
    async def add_file(self, user_id: int, file_id: str, original_name: str,
                      file_size: int, file_hash: str, file_category: str,
                      mime_type: str, file_path: str, note_id: int = None) -> int:
        """Добавление файла"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO files (user_id, file_id, original_name, file_size, file_hash, 
                                 file_category, mime_type, file_path, note_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, file_id, original_name, file_size, file_hash, 
                  file_category, mime_type, file_path, note_id))
            await db.commit()
            return cursor.lastrowid

    async def get_user_files(self, user_id: int, category: str = None) -> List[Dict[str, Any]]:
        """Получение файлов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if category:
                query = "SELECT * FROM files WHERE user_id = ? AND file_category = ? ORDER BY created_at DESC"
                params = (user_id, category)
            else:
                query = "SELECT * FROM files WHERE user_id = ? ORDER BY created_at DESC"
                params = (user_id,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def delete_file(self, file_id: str, user_id: int) -> bool:
        """Удаление файла"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM files WHERE file_id = ? AND user_id = ?
            """, (file_id, user_id))
            await db.commit()
            return cursor.rowcount > 0

    # Методы для работы с повторяющимися задачами
    async def add_recurring_task(self, user_id: int, title: str, description: str,
                               repeat_type: str, repeat_interval: int, start_date: str,
                               end_date: str, next_due: str, priority: str, 
                               metadata: str = "{}") -> int:
        """Добавление повторяющейся задачи"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO recurring_tasks (user_id, title, description, repeat_type, 
                                           repeat_interval, start_date, end_date, next_due, 
                                           priority, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, title, description, repeat_type, repeat_interval, 
                  start_date, end_date, next_due, priority, metadata))
            await db.commit()
            return cursor.lastrowid

    async def get_recurring_tasks(self, user_id: int, status: str = None) -> List[Dict[str, Any]]:
        """Получение повторяющихся задач"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if status:
                query = "SELECT * FROM recurring_tasks WHERE user_id = ? AND status = ? ORDER BY next_due ASC"
                params = (user_id, status)
            else:
                query = "SELECT * FROM recurring_tasks WHERE user_id = ? ORDER BY next_due ASC"
                params = (user_id,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def update_recurring_task(self, task_id: int, user_id: int, **kwargs) -> bool:
        """Обновление повторяющейся задачи"""
        updates = []
        params = []
        
        for key, value in kwargs.items():
            if key in ['title', 'description', 'status', 'next_due', 'priority', 'metadata']:
                updates.append(f"{key} = ?")
                params.append(value)
        
        if not updates:
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([task_id, user_id])
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"""
                UPDATE recurring_tasks SET {', '.join(updates)}
                WHERE id = ? AND user_id = ?
            """, params)
            await db.commit()
            return cursor.rowcount > 0

    # Методы для работы с временными блоками
    async def add_time_block(self, user_id: int, title: str, description: str,
                           start_time: str, end_time: str, category: str = "work",
                           color: str = "#3498db", is_recurring: bool = False,
                           recurring_pattern: str = None) -> int:
        """Добавление временного блока"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO time_blocks (user_id, title, description, start_time, end_time,
                                       category, color, is_recurring, recurring_pattern)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, title, description, start_time, end_time, category, 
                  color, is_recurring, recurring_pattern))
            await db.commit()
            return cursor.lastrowid

    async def get_time_blocks(self, user_id: int, start_date: str = None, 
                            end_date: str = None) -> List[Dict[str, Any]]:
        """Получение временных блоков"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if start_date and end_date:
                query = """
                    SELECT * FROM time_blocks 
                    WHERE user_id = ? AND start_time >= ? AND end_time <= ?
                    ORDER BY start_time ASC
                """
                params = (user_id, start_date, end_date)
            else:
                query = "SELECT * FROM time_blocks WHERE user_id = ? ORDER BY start_time ASC"
                params = (user_id,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def update_time_block(self, block_id: int, user_id: int, **kwargs) -> bool:
        """Обновление временного блока"""
        updates = []
        params = []
        
        for key, value in kwargs.items():
            if key in ['title', 'description', 'start_time', 'end_time', 'category', 
                      'color', 'status', 'is_recurring', 'recurring_pattern']:
                updates.append(f"{key} = ?")
                params.append(value)
        
        if not updates:
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([block_id, user_id])
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"""
                UPDATE time_blocks SET {', '.join(updates)}
                WHERE id = ? AND user_id = ?
            """, params)
            await db.commit()
            return cursor.rowcount > 0

    # Методы для работы с целями
    async def add_goal(self, user_id: int, title: str, description: str,
                      target_value: float, current_value: float = 0.0,
                      unit: str = "штук", deadline: str = None,
                      category: str = "general") -> int:
        """Добавление цели"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO goals (user_id, title, description, target_value, current_value,
                                 unit, deadline, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, title, description, target_value, current_value, 
                  unit, deadline, category))
            await db.commit()
            return cursor.lastrowid

    async def get_goals(self, user_id: int, status: str = "active") -> List[Dict[str, Any]]:
        """Получение целей пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if status == "all":
                query = "SELECT * FROM goals WHERE user_id = ? ORDER BY created_at DESC"
                params = (user_id,)
            else:
                query = "SELECT * FROM goals WHERE user_id = ? AND status = ? ORDER BY created_at DESC"
                params = (user_id, status)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def update_goal_progress(self, goal_id: int, user_id: int, 
                                 current_value: float) -> bool:
        """Обновление прогресса цели"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE goals SET current_value = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (current_value, goal_id, user_id))
            await db.commit()
            return cursor.rowcount > 0

    async def log_progress_change(self, goal_id: int, value_change: float, note: str = ""):
        """Логирование изменения прогресса"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO progress_history (goal_id, value_change, note)
                VALUES (?, ?, ?)
            """, (goal_id, value_change, note))
            await db.commit()

    # Методы для работы с активностью пользователей
    async def log_user_activity(self, user_id: int, action_type: str, metadata: str = "{}"):
        """Логирование активности пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO user_activity (user_id, action_type, metadata)
                VALUES (?, ?, ?)
            """, (user_id, action_type, metadata))
            await db.commit()

    async def get_user_activity(self, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Получение активности пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM user_activity 
                WHERE user_id = ? AND timestamp >= datetime('now', '-{} days')
                ORDER BY timestamp DESC
            """.format(days), (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_database_stats(self) -> Dict[str, Any]:
        """Получение статистики базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}

            # Подсчитываем записи в каждой таблице
            tables = ['users', 'notes', 'reminders', 'categories', 'files',
                     'recurring_tasks', 'time_blocks', 'goals', 'progress_history', 'user_activity']

            for table in tables:
                try:
                    async with db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                        count = await cursor.fetchone()
                        stats[table] = count[0] if count else 0
                except Exception:
                    stats[table] = 0

            return stats

    async def get_file_info(self, file_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение информации о файле пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM files WHERE file_id = ? AND user_id = ?
            """, (file_id, user_id)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_user_timezone(self, user_id: int, timezone: str):
        """Обновление часового пояса пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users SET settings = json_set(
                    COALESCE(settings, '{}'),
                    '$.timezone',
                    ?
                ) WHERE user_id = ?
            """, (timezone, user_id))
            await db.commit()

    async def clear_user_data(self, user_id: int) -> bool:
        """Очистка всех данных пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Удаляем в правильном порядке (с учетом внешних ключей)
                await db.execute("DELETE FROM progress_history WHERE goal_id IN (SELECT id FROM goals WHERE user_id = ?)", (user_id,))
                await db.execute("DELETE FROM goals WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM time_blocks WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM recurring_tasks WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM files WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM reminders WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM notes WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM categories WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM user_activity WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error clearing user data: {e}")
                return False