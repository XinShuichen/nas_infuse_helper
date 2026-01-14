# Copyright (c) 2025 Trae AI. All rights reserved.

from pathlib import Path
from typing import List, Tuple
from src.core.models import MediaItem
from src.infrastructure.db.repository import MediaRepository, SymlinkRepository, LogRepository
import os

class LinkService:
    def __init__(self, config, media_repo: MediaRepository, symlink_repo: SymlinkRepository, log_repo: LogRepository):
        self.config = config
        self.media_repo = media_repo
        self.symlink_repo = symlink_repo
        self.log_repo = log_repo
        self.path_mapping = config.path_mapping

    def link_item(self, item: MediaItem, suggested_mappings: List[Tuple[object, Path]]):
        """
        Creates symlinks for a MediaItem and updates DB.
        """
        import logging
        logger = logging.getLogger(__name__)

        target_root = self.config.target_dir
        
        success_count = 0
        fail_count = 0
        errors = []
        common_parent = None

        for file, relative_target_path in suggested_mappings:
            full_target_path = target_root / relative_target_path
            
            if common_parent is None:
                common_parent = full_target_path.parent

            # Apply path mapping to source
            source_path = file.path
            target_source = str(source_path)
            if self.path_mapping:
                for old_prefix, new_prefix in self.path_mapping.items():
                    if target_source.startswith(old_prefix):
                        target_source = target_source.replace(old_prefix, new_prefix, 1)
                        break
            
            try:
                # Cleanup OLD link if exists
                old_link_path_str = self.symlink_repo.get_by_source(source_path)
                if old_link_path_str:
                    old_link_path = Path(old_link_path_str)
                    # If old link is different from new target, remove it
                    # We resolve() to handle potential relative path differences, though they should be absolute.
                    # Safety: check if old_link_path exists to avoid error
                    if old_link_path.resolve() != full_target_path.resolve():
                        if old_link_path.exists() or old_link_path.is_symlink():
                            try:
                                old_link_path.unlink()
                                # Clean up empty parent directories if possible?
                                # Optional but nice. For now just unlink.
                                logger.info(f"Removed old link: {old_link_path}")
                            except Exception as e:
                                logger.warning(f"Failed to remove old link {old_link_path}: {e}")

                # Ensure target directory exists
                full_target_path.parent.mkdir(parents=True, exist_ok=True)

                # Remove existing link/file (at new location, just in case)
                if full_target_path.exists() or full_target_path.is_symlink():
                    full_target_path.unlink()
                
                os.symlink(target_source, full_target_path)
                
                # Update DB
                self.symlink_repo.add(source_path, full_target_path)
                success_count += 1
                
            except Exception as e:
                fail_count += 1
                errors.append(f"{file.path.name}: {e}")
                self.log_repo.add("ERROR", str(full_target_path), f"Failed to link: {e}")
                logger.error(f"Failed to link {full_target_path}: {e}")

        # Aggregated Logging
        if success_count > 0:
            target_info = str(common_parent) if common_parent else "target"
            msg = f"Linked {success_count} files for '{item.title_cn or item.name}' to {target_info}"
            self.log_repo.add("LINK", item.name, msg)
            logger.info(msg)
        
        if fail_count > 0:
            logger.warning(f"Partial failures for '{item.name}': {fail_count} failed. {'; '.join(errors)}")
