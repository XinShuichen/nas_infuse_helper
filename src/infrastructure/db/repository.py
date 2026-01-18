# Copyright (c) 2025 Trae AI. All rights reserved.

from typing import List, Optional, Dict
from pathlib import Path
from .database import Database

class MediaRepository:
    def __init__(self, db: Database):
        self.db = db

    def save(self, data: Dict):
        """
        Saves or updates a media mapping.
        """
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO media_mapping 
                (original_path, target_path, media_type, title_cn, title_en, tmdb_id, year, alias, search_status, file_hash, last_scanned_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(data["original_path"]),
                    str(data["target_path"]) if data.get("target_path") else None,
                    data.get("media_type"),
                    data.get("title_cn"),
                    data.get("title_en"),
                    data.get("tmdb_id"),
                    data.get("year"),
                    data.get("alias"),
                    data.get("search_status", "pending"),
                    data.get("file_hash"),
                    data.get("last_scanned_at")
                ),
            )
            conn.commit()

    def get_by_path(self, original_path: Path) -> Optional[Dict]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM media_mapping WHERE original_path = ?",
                (str(original_path),),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all(self, status_filter: str = None) -> List[Dict]:
        query = "SELECT * FROM media_mapping"
        params = []
        if status_filter:
            query += " WHERE search_status = ?"
            params.append(status_filter)
        query += " ORDER BY created_at DESC"
        
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]

    def delete_by_path(self, original_path: Path):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM media_mapping WHERE original_path = ?", (str(original_path),))
            conn.commit()

    def get_sibling_metadata(self, parent_dir: str) -> Optional[Dict]:
        """
        Finds any 'found' media item in the same directory.
        Used for optimization to reuse metadata for new episodes.
        """
        query = """
        SELECT * FROM media_mapping 
        WHERE original_path LIKE ? || '%' 
        AND search_status = 'found' 
        AND tmdb_id IS NOT NULL 
        LIMIT 1
        """
        # Ensure parent_dir ends with slash to avoid partial matches on similar folder names
        # Actually, user might provide string without slash.
        # But 'original_path LIKE /a/b/%' works.
        if not parent_dir.endswith("/"):
            parent_dir += "/"
            
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (parent_dir,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_found_in_dir(self, parent_dir: str, limit: int = 50) -> List[Dict]:
        query = """
        SELECT * FROM media_mapping
        WHERE original_path LIKE ? || '%'
        AND search_status = 'found'
        AND tmdb_id IS NOT NULL
        ORDER BY created_at DESC
        LIMIT ?
        """
        if not parent_dir.endswith("/"):
            parent_dir += "/"

        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (parent_dir, limit))
            return [dict(row) for row in cursor.fetchall()]

class SymlinkRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, source_path: Path, link_path: Path):
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO symlink_map (source_path, link_path) VALUES (?, ?)",
                (str(source_path), str(link_path))
            )
            conn.commit()

    def get_by_source(self, source_path: Path) -> Optional[str]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT link_path FROM symlink_map WHERE source_path = ?", (str(source_path),))
            row = cursor.fetchone()
            return row["link_path"] if row else None

    def remove_by_link(self, link_path: Path):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM symlink_map WHERE link_path = ?", (str(link_path),))
            conn.commit()

    def remove_by_source(self, source_path: Path):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM symlink_map WHERE source_path = ?", (str(source_path),))
            conn.commit()

class LogRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, action_type: str, target: str, details: str = None):
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO operation_logs (action_type, target, details) VALUES (?, ?, ?)",
                (action_type, target, details)
            )
            conn.commit()

    def get_recent(self, limit: int = 100) -> List[Dict]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM operation_logs ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
