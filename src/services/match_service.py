# Copyright (c) 2025 Trae AI. All rights reserved.

from src.core.searcher import Searcher
from src.core.models import MediaItem, MediaType
from src.infrastructure.db.repository import MediaRepository, LogRepository

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
            if existing.get("tmdb_id") and existing.get("search_status") == "found":
                # Restore metadata from DB
                item.tmdb_id = existing.get("tmdb_id")
                item.title_cn = existing.get("title_cn")
                item.title_en = existing.get("title_en")
                item.year = existing.get("year")
                stored_media_type = existing.get("media_type")
                if stored_media_type:
                    try:
                        item.media_type = MediaType(stored_media_type)
                    except ValueError:
                        pass
                item.search_status = "found"
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
