# Copyright (c) 2025 Trae AI. All rights reserved.

import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional, Dict


class DatabaseManager:
    """
    Manages the SQLite database for media mapping.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
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
                    search_status TEXT DEFAULT 'pending', -- pending, found, not_found, uncertain
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def add_mapping(
        self,
        original: Path,
        target: Path,
        media_type: str,
        title_cn: str = None,
        title_en: str = None,
        tmdb_id: int = None,
        year: int = None,
        alias: str = None,
        search_status: str = "found",
    ):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO media_mapping 
                (original_path, target_path, media_type, title_cn, title_en, tmdb_id, year, alias, search_status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(original),
                    str(target) if target else None,
                    media_type,
                    title_cn,
                    title_en,
                    tmdb_id,
                    year,
                    alias,
                    search_status,
                ),
            )

    def get_mapping(self, original_path: Path) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM media_mapping WHERE original_path = ?",
                (str(original_path),),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_mappings(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM media_mapping ORDER BY created_at DESC"
            )
            return [dict(row) for row in cursor.fetchall()]
