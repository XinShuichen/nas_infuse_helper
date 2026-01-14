# Copyright (c) 2025 Trae AI. All rights reserved.

import os
from pathlib import Path
from .models import MediaItem, MediaFile
from ..db.manager import DatabaseManager


class Linker:
    """
    Handles creation of symbolic links.
    """

    def __init__(self, target_root: Path, db_manager: DatabaseManager, path_mapping: dict = None):
        self.target_root = target_root
        self.db_manager = db_manager
        self.path_mapping = path_mapping or {}

    def link_file(self, source_path: Path, relative_target_path: Path, media_type: str):
        """
        Creates a symbolic link from source_path to target_root / relative_target_path.
        """
        full_target_path = self.target_root / relative_target_path

        # Apply path mapping to source_path if configured
        target_source = str(source_path)
        if self.path_mapping:
            for old_prefix, new_prefix in self.path_mapping.items():
                if target_source.startswith(old_prefix):
                    target_source = target_source.replace(old_prefix, new_prefix, 1)
                    break
        
        # Ensure target directory exists
        full_target_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing link/file if it exists
        if full_target_path.exists() or full_target_path.is_symlink():
            full_target_path.unlink()

        try:
            os.symlink(target_source, full_target_path)
            self.db_manager.add_mapping(source_path, full_target_path, media_type)
            return True
        except Exception as e:
            print(f"Error creating symlink for {source_path}: {e}")
            return False

    def link_item(self, item: MediaItem, suggested_paths: list):
        """
        Links all files in a MediaItem to their suggested paths.
        suggested_paths should be a list of (MediaFile, Path) tuples.
        """
        success_count = 0
        for file, suggested_path in suggested_paths:
            if self.link_file(file.path, suggested_path, item.media_type.value):
                success_count += 1
        return success_count
