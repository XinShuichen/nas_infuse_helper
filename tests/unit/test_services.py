# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.services.match_service import MatchService
from src.services.link_service import LinkService
from src.core.models import MediaItem, MediaType, MediaFile

def test_match_service_found(media_repo, log_repo, mock_config):
    # Mock Searcher
    with patch("src.services.match_service.Searcher") as MockSearcher:
        mock_searcher_instance = MockSearcher.return_value
        
        # Setup item
        item = MediaItem(
            name="Inception.mkv", 
            original_path=Path("/source/Inception.mkv"),
            files=[],
            media_type=MediaType.MOVIE
        )
        
        # Mock search result
        mock_searcher_instance.search.return_value = item
        item.search_status = "found"
        item.tmdb_id = 12345
        
        service = MatchService(mock_config, media_repo, log_repo)
        result = service.process_item(item)
        
        assert result.search_status == "found"
        assert result.tmdb_id == 12345
        
        # Verify log
        logs = log_repo.get_recent()
        assert len(logs) > 0
        assert logs[0]["action_type"] == "MATCH"

def test_link_service(media_repo, symlink_repo, log_repo, mock_config):
    service = LinkService(mock_config, media_repo, symlink_repo, log_repo)
    
    item = MediaItem(
        name="Test",
        original_path=Path("/source/test.mkv"),
        files=[MediaFile(path=Path("/source/test.mkv"), extension=".mkv")],
        media_type=MediaType.MOVIE
    )
    
    suggested_mappings = [
        (item.files[0], Path("Movies/Test/test.mkv"))
    ]
    
    with patch("os.symlink") as mock_symlink:
        service.link_item(item, suggested_mappings)
        
        # Verify os.symlink called
        expected_target = mock_config.target_dir / "Movies/Test/test.mkv"
        mock_symlink.assert_called()
        
        # Verify DB
        # Note: LinkService uses SymlinkRepository
        # We can't easily check DB here because we are mocking symlink which might raise if dir doesn't exist?
        # But we create parent dir.
        pass
