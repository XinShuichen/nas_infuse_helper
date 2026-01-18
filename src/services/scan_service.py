# Copyright (c) 2025 Trae AI. All rights reserved.

import time
from src.core.scanner import Scanner
from src.core.aggregator import Aggregator
from src.core.classifier import Classifier
from src.core.renamer import Renamer
from src.infrastructure.db.repository import MediaRepository, LogRepository
from .match_service import MatchService
from .link_service import LinkService

class ScanService:
    def __init__(self, config, media_repo: MediaRepository, log_repo: LogRepository, 
                 match_service: MatchService, link_service: LinkService):
        self.config = config
        self.media_repo = media_repo
        self.log_repo = log_repo
        self.match_service = match_service
        self.link_service = link_service
        
        subtitle_extensions = getattr(config, "subtitle_extensions", [])
        if not isinstance(subtitle_extensions, (list, tuple, set)):
            subtitle_extensions = []
        self.scanner = Scanner(config.video_extensions, subtitle_extensions=list(subtitle_extensions))
        self.aggregator = Aggregator(
            config.source_dir, subtitle_extensions=list(subtitle_extensions)
        )
        self.classifier = Classifier(config.video_extensions)
        self.renamer = Renamer()

    def process_paths(self, paths):
        """
        Process a specific list of paths (files or directories).
        """
        from pathlib import Path
        from src.core.models import MediaFile
        
        video_exts = set(getattr(self.config, "video_extensions", []) or [])
        subtitle_exts = getattr(self.config, "subtitle_extensions", [])
        if not isinstance(subtitle_exts, (list, tuple, set)):
            subtitle_exts = []
        subtitle_exts = set(subtitle_exts)

        # Convert paths to MediaFiles
        media_files = []
        for p in paths:
            if isinstance(p, MediaFile):
                # Double check extension for MediaFile objects too (safety net)
                if p.extension.lower() in video_exts or p.extension.lower() in subtitle_exts:
                    media_files.append(p)
                else:
                    print(f"WARNING: Skipping invalid MediaFile: {p.path} (Ext: {p.extension})")
                continue
                
            path_obj = Path(p)
            # Strict validation: Check existence and extension
            if path_obj.is_file():
                if path_obj.suffix.lower() in video_exts or path_obj.suffix.lower() in subtitle_exts:
                    media_files.append(MediaFile(
                        path=path_obj,
                        extension=path_obj.suffix.lower(),
                        size=path_obj.stat().st_size if path_obj.exists() else 0,
                        mtime=path_obj.stat().st_mtime if path_obj.exists() else 0
                    ))
                else:
                     # Log warning for debugging user issues
                     print(f"WARNING: Skipping file with invalid extension: {path_obj}")
            elif path_obj.is_dir():
                # Scan directory
                media_files.extend(self.scanner.scan(path_obj))

        if not media_files:
            return

        self.log_repo.add("SCAN", "PARTIAL", f"Processing {len(media_files)} files")
        
        # Aggregate
        items = self.aggregator.aggregate(media_files)
        
        # Process items
        for item in items:
            try:
                self._process_single_item(item)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to process item {item.name}: {e}")
                # Continue to next item instead of aborting the whole batch

    def _process_single_item(self, item):
        # 1. Classify
        item = self.classifier.classify(item)
        
        # 2. Match
        item = self.match_service.process_item(item)
        
        # 3. Save to DB & Link
        if item.search_status == "found":
            suggested_mappings = []
            for file in item.files:
                suggested_path = self.renamer.get_suggested_path(item, file)
                suggested_mappings.append((file, suggested_path))
                
                # Save mapping to DB
                self.media_repo.save({
                    "original_path": str(file.path),
                    "target_path": str(suggested_path),
                    "media_type": item.media_type.value,
                    "title_cn": item.title_cn,
                    "title_en": item.title_en,
                    "tmdb_id": item.tmdb_id,
                    "year": item.year,
                    "alias": item.alias,
                    "search_status": item.search_status,
                    "last_scanned_at": time.time()
                })

            # Link files
            self.link_service.link_item(item, suggested_mappings)
        else:
            # Record unknown/uncertain
            # FIX: Iterate over files instead of saving item.original_path (which might be a directory)
            for file in item.files:
                self.media_repo.save({
                    "original_path": str(file.path),
                    "target_path": None,
                    "media_type": item.media_type.value,
                    "title_cn": item.title_cn,
                    "title_en": item.title_en,
                    "tmdb_id": item.tmdb_id,
                    "year": item.year,
                    "alias": item.alias,
                    "search_status": item.search_status,
                    "last_scanned_at": time.time()
                })

    def handle_deletion(self, path_str: str):
        """
        Handles file deletion: remove from DB and clean up symlink.
        """
        from pathlib import Path
        path_obj = Path(path_str)
        record = self.media_repo.get_by_path(path_obj)
        
        if record:
            # 1. Remove symlink if exists
            target_path_str = record.get("target_path")
            if target_path_str:
                target_path = Path(target_path_str)
                if target_path.exists() or target_path.is_symlink():
                    try:
                        target_path.unlink()
                        # Clean up empty parent directories if needed
                        # But be careful not to delete non-empty dirs
                        pass 
                    except OSError:
                        pass
            
            # 2. Delete from DB
            self.media_repo.delete_by_path(path_obj)
            self.log_repo.add("DELETE", path_str, "File deleted from source")
            import logging
            logging.getLogger(__name__).info(f"Deleted from DB: {path_str}")

    def run_incremental_scan(self, update_progress=None):
        """
        Executes incremental scan: checks for new files only.
        """
        import logging
        logger = logging.getLogger(__name__)

        def report(p, msg):
            if update_progress:
                update_progress(p, msg)

        try:
            report(10, "Scanning files for incremental update...")
            self.log_repo.add("SCAN", "START", "Incremental scan started")
            logger.info("Starting incremental scan...")
            
            # 1. Scan all files
            all_files = self.scanner.scan(self.config.source_dir)
            
            # 2. Filter new files
            new_files = []
            for f in all_files:
                # Check if this file path exists in DB (Raw Path)
                if self.media_repo.get_by_path(f.path):
                    continue
                
                # Check if mapped path exists in DB (Handle inconsistency from rebuild_db)
                mapped_path_str = str(f.path)
                if self.config.path_mapping:
                    for old_prefix, new_prefix in self.config.path_mapping.items():
                        if mapped_path_str.startswith(old_prefix):
                            mapped_path_str = mapped_path_str.replace(old_prefix, new_prefix, 1)
                            break
                
                if mapped_path_str != str(f.path):
                    existing_mapped = self.media_repo.get_by_path(mapped_path_str)
                    if existing_mapped:
                        # Found via mapping! 
                        # Self-healing: Update DB to use raw path for consistency
                        logger.info(f"Self-healing DB: Updating {f.path.name} from mapped path to raw path.")
                        existing_mapped["original_path"] = str(f.path)
                        # Delete old (mapped) key
                        self.media_repo.delete_by_path(mapped_path_str)
                        # Save new (raw) key
                        self.media_repo.save(existing_mapped)
                        continue

                new_files.append(f)
            
            if not new_files:
                report(100, "No new files found.")
                self.log_repo.add("SCAN", "COMPLETE", "Incremental scan: No new files")
                logger.info("Incremental scan: No new files found.")
                return

            msg = f"Found {len(new_files)} new files. Aggregating..."
            report(30, msg)
            logger.info(msg)
            
            # 3. Aggregate ONLY new files
            items = self.aggregator.aggregate(new_files)
            # Sort items by earliest mtime
            items.sort(key=lambda x: x.earliest_mtime)
            
            # Log aggregated items for confirmation
            logger.info(f"Aggregated {len(items)} items from {len(new_files)} files:")
            for item in items:
                logger.info(f" - {item.name} ({len(item.files)} files)")

            total_items = len(items)
            for i, item in enumerate(items):
                # Process item
                self._process_single_item(item)
                
                # Report progress
                current_progress = 30 + int((i / total_items) * 60)
                report(current_progress, f"Processing {item.name}...")

            report(100, "Incremental scan complete")
            self.log_repo.add("SCAN", "COMPLETE", f"Incremental processed {total_items} items")
            logger.info(f"Incremental scan complete. Processed {total_items} items.")
            
        except Exception as e:
            self.log_repo.add("ERROR", "SCAN", str(e))
            logger.error(f"Incremental scan failed: {e}")
            raise e

    def run_full_scan(self, update_progress=None):
        """
        Executes the full scan pipeline.
        update_progress: callable(percentage, message)
        """
        def report(p, msg):
            if update_progress:
                update_progress(p, msg)

        try:
            report(10, "Scanning files...")
            self.log_repo.add("SCAN", "START", "Full scan started")
            
            files = self.scanner.scan(self.config.source_dir)
            
            report(30, "Aggregating items...")
            items = self.aggregator.aggregate(files)
            # Sort items by earliest mtime
            items.sort(key=lambda x: x.earliest_mtime)
            
            total_items = len(items)
            for i, item in enumerate(items):
                # Process item
                self._process_single_item(item)
                
                # Report progress
                current_progress = 30 + int((i / total_items) * 60)
                report(current_progress, f"Processing {item.name}...")

            report(100, "Scan complete")
            self.log_repo.add("SCAN", "COMPLETE", f"Processed {total_items} items")
            
        except Exception as e:
            self.log_repo.add("ERROR", "SCAN", str(e))
            raise e
