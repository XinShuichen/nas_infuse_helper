# Copyright (c) 2025 Trae AI. All rights reserved.

import logging
import threading
import time
from pathlib import Path
from typing import Dict, Set

from src.core.config import Config
from src.core.scanner import Scanner
from src.infrastructure.db.repository import MediaRepository
from src.services.scan_service import ScanService

class WatchService:
    """
    Poller-based file watcher.
    Periodically scans source_dir, compares with DB, and triggers ScanService.
    """
    def __init__(self, config: Config, scan_service: ScanService, media_repo: MediaRepository):
        self.config = config
        self.scan_service = scan_service
        self.media_repo = media_repo
        self.logger = logging.getLogger(__name__)
        
        self.polling_interval = 60  # seconds
        self.stop_event = threading.Event()
        self.worker_thread = None

    def start(self):
        """Starts the polling loop in a separate thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            self.logger.warning("WatchService is already running.")
            return

        self.logger.info(f"Starting WatchService (Polling every {self.polling_interval}s)...")
        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Stops the polling loop."""
        self.logger.info("Stopping WatchService...")
        self.stop_event.set()
        if self.worker_thread:
            self.worker_thread.join()

    def _polling_loop(self):
        """Main polling loop."""
        while not self.stop_event.is_set():
            try:
                self._poll()
            except Exception as e:
                self.logger.error(f"Error in polling loop: {e}")
            
            # Sleep with check for stop_event
            for _ in range(self.polling_interval):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

    def _poll(self):
        source_path = Path(self.config.source_dir)
        if not source_path.exists():
            self.logger.warning(f"Source directory not found: {source_path}")
            return

        subtitle_extensions = getattr(self.config, "subtitle_extensions", [])
        if not isinstance(subtitle_extensions, (list, tuple, set)):
            subtitle_extensions = []

        scanner = Scanner(self.config.video_extensions, subtitle_extensions=list(subtitle_extensions))
        scanned_files = scanner.scan(source_path)
        disk_map: Dict[str, object] = {str(f.path): f for f in scanned_files}
        disk_paths: Set[str] = set(disk_map.keys())

        db_records = self.media_repo.get_all()
        db_paths: Set[str] = {r["original_path"] for r in db_records if r.get("original_path")}

        normalized_db_paths: Set[str] = set()
        normalized_to_db: Dict[str, str] = {}

        for p in db_paths:
            normalized = p
            if self.config.path_mapping:
                for raw_prefix, mapped_prefix in self.config.path_mapping.items():
                    if normalized.startswith(mapped_prefix):
                        normalized = normalized.replace(mapped_prefix, raw_prefix, 1)
                        break
            normalized_db_paths.add(normalized)
            normalized_to_db[normalized] = p

        new_path_strs = sorted(disk_paths - normalized_db_paths)
        deleted_normalized = sorted(normalized_db_paths - disk_paths)
        deleted_paths = []
        for p in deleted_normalized:
            if Path(p).exists() and Path(p).is_file():
                continue
            db_p = normalized_to_db.get(p)
            if db_p:
                deleted_paths.append(db_p)

        if not new_path_strs and not deleted_paths:
            return

        self.logger.info(
            f"Poll detected changes: {len(new_path_strs)} new, {len(deleted_paths)} deleted."
        )
        if self.config.verbose:
            for p in new_path_strs[:20]:
                self.logger.info(f" + {p}")
            for p in deleted_paths[:20]:
                self.logger.info(f" - {p}")

        for path_str in deleted_paths:
            self.scan_service.handle_deletion(path_str)

        if new_path_strs:
            new_files = [disk_map[p] for p in new_path_strs if p in disk_map]
            self.scan_service.process_paths(new_files)
