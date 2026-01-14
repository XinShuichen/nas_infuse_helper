# Copyright (c) 2025 Trae AI. All rights reserved.

import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Callable


class SourceDirHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable, debounce_seconds: int = 30):
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.timer = None
        self._lock = threading.Lock()
        self.changes = set()

    def on_created(self, event):
        if not event.is_directory:
            self._trigger(f"Created: {event.src_path}")

    def on_moved(self, event):
        if not event.is_directory:
            self._trigger(f"Moved: {event.src_path} -> {event.dest_path}")

    def _trigger(self, change_desc: str):
        with self._lock:
            self.changes.add(change_desc)
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(self.debounce_seconds, self._execute_callback)
            self.timer.start()

    def _execute_callback(self):
        with self._lock:
            changes_snapshot = list(self.changes)
            self.changes.clear()
            self.timer = None
        
        self.callback(changes_snapshot)


class FileWatcher:
    """
    Watches the source directory for new files and triggers a scan.
    """

    def __init__(self, source_dir: str, callback: Callable, debounce_seconds: int = 30):
        self.source_dir = source_dir
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.observer = Observer()
        self.handler = SourceDirHandler(callback, debounce_seconds)

    def start(self):
        print(f"Starting FileWatcher on {self.source_dir}...")
        self.observer.schedule(self.handler, self.source_dir, recursive=True)
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()
