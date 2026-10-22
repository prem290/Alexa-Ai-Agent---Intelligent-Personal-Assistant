
"""SQLite persistence layer for Alexa+ task storage."""

import json
import sqlite3
from pathlib import Path
from typing import Optional

from agent.schemas import Task

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "alexa_tasks.db"
JSON_PATH = PROJECT_ROOT / "agent_tasks_store.json"


class SQLiteTaskStore:
    """Persist tasks in SQLite and import legacy JSON data once."""

    def __init__(
        self,
        db_path: Path = DB_PATH,
        json_path: Path = JSON_PATH,
    ):
        self.db_path = Path(db_path)
        self.json_path = Path(json_path)
        self._initialize()
        self._load_or_seed()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        """Create the task table and metadata table."""
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS task_metadata (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
            """)
            connection.execute("""
                INSERT OR IGNORE INTO task_metadata (key, value)
                VALUES ('counter', 100)
            """)

    def _load_or_seed(self) -> None:
        """
        Import tasks from the legacy JSON file if SQLite is empty.
        If there is no JSON file, leave the task table empty.
        """
        with self._connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM tasks"
            ).fetchone()[0]

        if count > 0:
            self._sync_counter()
            return

        if not self.json_path.exists():
            return

        try:
            with self.json_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Could not read legacy task data: {self.json_path}"
            ) from exc

        tasks = payload.get("tasks", [])
        highest_id = 100

        for item in tasks:
            task = Task(**item)
            self.update(task)

            task_id = task.id
            if task_id.startswith("TSK-"):
                number = task_id.removeprefix("TSK-")
                if number.isdigit():
                    highest_id = max(highest_id, int(number))

        try:
            legacy_counter = int(payload.get("counter", 100))
        except (ValueError, TypeError):
            legacy_counter = 100

        self._set_counter(max(highest_id, legacy_counter))

    def _set_counter(self, value: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO task_metadata (key, value)
                VALUES ('counter', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (value,),
            )

    def _sync_counter(self) -> None:
        """Ensure the counter is at least the largest existing task ID."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM tasks"
            ).fetchall()
            row = connection.execute(
                "SELECT value FROM task_metadata WHERE key = 'counter'"
            ).fetchone()

        highest_id = max(
            (
                int(item["id"].split("-", 1)[1])
                for item in rows
                if item["id"].startswith("TSK-")
                and item["id"].split("-", 1)[1].isdigit()
            ),
            default=100,
        )
        current = int(row["value"]) if row else 100
        self._set_counter(max(current, highest_id))

    def all(self) -> list[Task]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT data FROM tasks ORDER BY rowid"
            ).fetchall()

        return [Task(**json.loads(row["data"])) for row in rows]

    def get(self, task_id: str) -> Optional[Task]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

        return Task(**json.loads(row["data"])) if row else None

    def find_by_title(self, query: str) -> list[Task]:
        search = f"%{query}%"

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT data FROM tasks
                WHERE title LIKE ? OR data LIKE ?
                ORDER BY rowid
                """,
                (search, search),
            ).fetchall()

        return [Task(**json.loads(row["data"])) for row in rows]

    def add(self, task: Task) -> Task:
        return self.update(task)

    def update(self, task: Task) -> Task:
        """Insert a new task or update an existing task."""
        data = task.model_dump(mode="json")

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (id, title, data)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    data = excluded.data
                """,
                (
                    task.id,
                    task.title,
                    json.dumps(data),
                ),
            )

        return task

    def delete(self, task_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM tasks WHERE id = ?",
                (task_id,),
            )

        return cursor.rowcount > 0

    def clear(self) -> None:
        """Delete all tasks without deleting the ID counter."""
        with self._connect() as connection:
            connection.execute("DELETE FROM tasks")

    def next_id(self) -> str:
        """Generate the next task ID and persist the counter atomically."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            row = connection.execute(
                "SELECT value FROM task_metadata WHERE key = 'counter'"
            ).fetchone()

            current = int(row["value"]) if row else 100

            rows = connection.execute(
                "SELECT id FROM tasks"
            ).fetchall()

            highest_id = max(
                (
                    int(item["id"].split("-", 1)[1])
                    for item in rows
                    if item["id"].startswith("TSK-")
                    and item["id"].split("-", 1)[1].isdigit()
                ),
                default=100,
            )

            next_number = max(current, highest_id) + 1

            connection.execute(
                """
                INSERT INTO task_metadata (key, value)
                VALUES ('counter', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (next_number,),
            )

        return f"TSK-{next_number}"
