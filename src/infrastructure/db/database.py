# Copyright (c) 2025 Trae AI. All rights reserved.

import sqlite3
from pathlib import Path
import logging

class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        # Force init if memory, otherwise normal check
        # But wait, we need to create schema even if file exists but table missing?
        # Current logic: only if parent dir missing or memory?
        # Actually _init_db is always called.
        self._init_db()

    def _init_db(self):
        # Allow using :memory: for testing, which is not a path
        if str(self.db_path) != ":memory:" and not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            # 1. media_mapping table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS media_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_path TEXT UNIQUE,
                    target_path TEXT,
                    media_type TEXT,
                    title_cn TEXT,
                    title_en TEXT,
                    tmdb_id INTEGER,
                    year INTEGER,
                    alias TEXT,
                    search_status TEXT DEFAULT 'pending',
                    file_hash TEXT,
                    last_scanned_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit() # Important: commit schema creation!
            
            # Check for new columns in media_mapping (migration)
            cursor = conn.execute("PRAGMA table_info(media_mapping)")
            columns = [info[1] for info in cursor.fetchall()]
            
            if "file_hash" not in columns:
                conn.execute("ALTER TABLE media_mapping ADD COLUMN file_hash TEXT")
            if "last_scanned_at" not in columns:
                conn.execute("ALTER TABLE media_mapping ADD COLUMN last_scanned_at TIMESTAMP")

            # 2. operation_logs table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    action_type TEXT,
                    target TEXT,
                    details TEXT
                )
                """
            )

            # 3. symlink_map table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS symlink_map (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT,
                    link_path TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(source_path) REFERENCES media_mapping(original_path)
                )
                """
            )

    def get_connection(self):
        # If memory, we must reuse the same connection or it will be wiped
        # But here we return a new connection each time.
        # For :memory:, this is fatal - each connection is a fresh empty DB.
        
        if str(self.db_path) == ":memory:":
            if not hasattr(self, '_memory_conn'):
                self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
            return self._memory_conn
            
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
