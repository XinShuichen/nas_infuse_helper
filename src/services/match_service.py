# Copyright (c) 2025 Trae AI. All rights reserved.

from src.core.searcher import Searcher
from src.core.models import MediaItem, MediaType
from src.infrastructure.db.repository import MediaRepository, LogRepository
import re
from pathlib import Path

class MatchService:
    def __init__(self, config, media_repo: MediaRepository, log_repo: LogRepository):
        self.config = config
        self.media_repo = media_repo
        self.log_repo = log_repo
        self.searcher = Searcher(config.tmdb_api_key)

    def process_item(self, item: MediaItem) -> MediaItem:
        """
        Searches for metadata for a media item.
        Checks DB first for existing aliases/mappings.
        """
        # 1. Check if we already have a mapping for THIS specific file
        existing = self.media_repo.get_by_path(item.original_path)
        if existing:
            # If status is hidden, respect it
            if existing.get("search_status") == "hidden":
                item.search_status = "hidden"
                return item

            # Use existing metadata
            item.alias = existing.get("alias")
            if existing.get("tmdb_id") is not None and existing.get("search_status") == "found":
                # Restore metadata from DB
                item.tmdb_id = existing.get("tmdb_id")
                item.title_cn = existing.get("title_cn")
                item.title_en = existing.get("title_en")
                item.year = existing.get("year")
                stored_media_type = existing.get("media_type")
                if stored_media_type:
                    try:
                        stored_enum = MediaType(stored_media_type)
                        if stored_enum != MediaType.UNKNOWN:
                            item.media_type = stored_enum
                    except ValueError:
                        pass
                item.search_status = "found"
                return item

        subtitle_exts = getattr(self.config, "subtitle_extensions", [])
        if not isinstance(subtitle_exts, (list, tuple, set)):
            subtitle_exts = []
        subtitle_exts = {e.lower() for e in subtitle_exts}
        is_subtitle_only = bool(item.files) and all(
            f.extension.lower() in subtitle_exts for f in item.files
        )

        if is_subtitle_only and not item.tmdb_id:
            try:
                item_parent = item.original_path.parent.resolve()
                source_root = self.config.source_dir.resolve()
            except Exception:
                item_parent = None
                source_root = None

            if item_parent and source_root and item_parent != source_root:
                candidates = []
                try:
                    candidates = self.media_repo.get_found_in_dir(str(item_parent), limit=50)
                except Exception:
                    candidates = []

                def normalize_subtitle_stem(stem: str) -> str:
                    return re.sub(r"\.[a-z]{2,3}$", "", stem, flags=re.IGNORECASE)

                subtitle_stem = normalize_subtitle_stem(item.original_path.stem)
                best = None
                best_score = 0
                for c in candidates:
                    c_path_str = c.get("original_path") or ""
                    c_stem = normalize_subtitle_stem(Path(c_path_str).stem) if c_path_str else ""
                    if not c_stem:
                        continue
                    score = 0
                    if c_stem == subtitle_stem:
                        score = 100
                    elif subtitle_stem.startswith(c_stem) or c_stem.startswith(subtitle_stem):
                        score = 80
                    elif c_stem in subtitle_stem or subtitle_stem in c_stem:
                        score = 60
                    if score > best_score:
                        best = c
                        best_score = score

                if best and best_score >= 60:
                    item.tmdb_id = best.get("tmdb_id")
                    item.title_cn = best.get("title_cn")
                    item.title_en = best.get("title_en")
                    item.year = best.get("year")
                    stored_media_type = best.get("media_type")
                    if stored_media_type:
                        try:
                            item.media_type = MediaType(stored_media_type)
                        except ValueError:
                            pass
                    item.search_status = "found"
                    self.log_repo.add(
                        "MATCH",
                        item.name,
                        f"Reused metadata for subtitle from sibling: {item.title_cn} (TMDB: {item.tmdb_id})",
                    )
                    return item

        # 2. Optimization: Check for siblings in the same directory (Same Series Strategy)
        # SAFETY CHECK: Only enable sibling optimization if:
        # A) The item is a TV Show (Movies in same dir are rarely the same movie)
        # B) AND the parent directory is NOT the Source Root (prevents pollution in flat dump folders)
        
        is_safe_to_optimize = False
        if item.media_type == MediaType.TV_SHOW:
            # Check if parent is source root
            # Convert paths to absolute strings for comparison
            # We assume config.source_dir is absolute
            try:
                item_parent = item.original_path.parent.resolve()
                source_root = self.config.source_dir.resolve()
                
                if item_parent != source_root:
                    is_safe_to_optimize = True
            except Exception:
                # If path resolution fails, default to unsafe
                pass
        
        if not item.tmdb_id and is_safe_to_optimize:
            parent_dir = str(item.original_path.parent)
            sibling = self.media_repo.get_sibling_metadata(parent_dir)
            
            if sibling:
                # Reuse metadata
                item.tmdb_id = sibling.get("tmdb_id")
                item.title_cn = sibling.get("title_cn")
                item.title_en = sibling.get("title_en")
                item.year = sibling.get("year")
                item.media_type = MediaType(sibling.get("media_type")) if sibling.get("media_type") else item.media_type
                item.search_status = "found"
                self.log_repo.add("MATCH", item.name, f"Optimized match via sibling: {sibling.get('title_cn')} (TMDB: {item.tmdb_id})")
                return item

        # 3. Perform search (Searcher handles logic: if alias exists, search by alias)
        item = self.searcher.search(item)
        
        if item.search_status == "found":
            self.log_repo.add("MATCH", item.name, f"Matched with TMDB ID: {item.tmdb_id}")
        else:
            self.log_repo.add("MATCH_FAIL", item.name, f"Status: {item.search_status}")
            
        return item

    def manual_search(self, name: str, media_type: MediaType):
        return self.searcher.search_all(name, media_type)
