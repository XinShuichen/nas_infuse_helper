# Copyright (c) 2025 Trae AI. All rights reserved.

import threading
from typing import Dict, Any, Optional
import time


class TaskManager:
    """
    Manages background tasks and their progress.
    """

    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start_task(self, task_id: str, total_steps: int = 100):
        with self._lock:
            self._tasks[task_id] = {
                "status": "running",
                "progress": 0,
                "total": total_steps,
                "message": "Starting...",
                "start_time": time.time(),
            }

    def update_progress(self, task_id: str, progress: int, message: Optional[str] = None):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["progress"] = progress
                if message:
                    self._tasks[task_id]["message"] = message

    def complete_task(self, task_id: str, message: str = "Completed"):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = "completed"
                self._tasks[task_id]["progress"] = self._tasks[task_id]["total"]
                self._tasks[task_id]["message"] = message

    def fail_task(self, task_id: str, message: str):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["message"] = message

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return self._tasks.copy()


# Global instance
task_manager = TaskManager()
