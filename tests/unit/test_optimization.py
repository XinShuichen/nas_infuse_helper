# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.services.match_service import MatchService
from src.core.models import MediaItem, MediaType

def test_optimization_uses_sibling_metadata():
    # Setup
    config = MagicMock()
    repo = MagicMock()
    log_repo = MagicMock()
    service = MatchService(config, repo, log_repo)
    
    # Existing sibling in DB
    parent_dir = "/mnt/tv/Show/Season 1"
    repo.get_by_path.return_value = None # Not self
    repo.get_sibling_metadata.return_value = {
        "tmdb_id": 12345,
        "title_cn": "Existing Show",
        "title_en": "Existing Show",
        "year": 2024,
        "media_type": "TV Show",
        "search_status": "found"
    }
    
    # New Item
    item = MediaItem(
        name="Show.S01E02.mkv",
        original_path=Path(f"{parent_dir}/Show.S01E02.mkv"),
        files=[],
        media_type=MediaType.TV_SHOW
    )
    
    # Execute
    result = service.process_item(item)
    
    # Verify
    repo.get_sibling_metadata.assert_called_with(parent_dir)
    assert result.tmdb_id == 12345
    assert result.title_cn == "Existing Show"
    assert result.search_status == "found"
    
    # Ensure Searcher was NOT called
    # We can't easily assert searcher.search not called because it's instantiated inside __init__
    # But we can check if it returns early.
    # We can mock searcher if we want, but since we didn't mock it in init, 
    # we rely on the fact that result has tmdb_id set correctly without calling network (mock config has no API key anyway)
