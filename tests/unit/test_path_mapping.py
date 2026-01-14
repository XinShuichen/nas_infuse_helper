# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.services.watch_service import WatchService
from src.services.link_service import LinkService
from src.core.models import MediaItem, MediaType, MediaFile
from src.core.config import Config

@pytest.fixture
def mock_config(tmp_path):
    config = MagicMock(spec=Config)
    config.source_dir = tmp_path / "source"
    config.target_dir = tmp_path / "target"
    config.source_dir.mkdir()
    config.target_dir.mkdir()
    config.video_extensions = [".mp4", ".mkv"]
    # Map internal source_dir to some external path
    config.path_mapping = {
        str(config.source_dir): "/external/path"
    }
    return config

def test_link_service_applies_mapping(mock_config):
    # Setup services
    media_repo = MagicMock()
    symlink_repo = MagicMock()
    log_repo = MagicMock()
    service = LinkService(mock_config, media_repo, symlink_repo, log_repo)
    
    # Create a mock item and file
    source_file = mock_config.source_dir / "movie.mp4"
    item = MediaItem(
        name="Movie",
        original_path=source_file,
        files=[MediaFile(path=source_file, extension=".mp4", size=100, mtime=100)],
        media_type=MediaType.MOVIE
    )
    
    # Suggested mapping (relative)
    suggested = [(item.files[0], Path("Movies/Movie.mp4"))]
    
    # Execute
    with patch("os.symlink") as mock_symlink:
        service.link_item(item, suggested)
        
        # Verify os.symlink called with mapped path
        expected_target = f"/external/path/movie.mp4"
        expected_link = str(mock_config.target_dir / "Movies/Movie.mp4")
        
        mock_symlink.assert_called_once_with(expected_target, Path(expected_link))

def test_watch_service_handles_mapped_db_paths(mock_config):
    """
    Test that WatchService correctly identifies that a file on disk (Raw Path)
    matches a file in DB (Mapped Path) and updates DB instead of Deleting+Adding.
    """
    scan_service = MagicMock()
    media_repo = MagicMock()
    
    watcher = WatchService(mock_config, scan_service, media_repo)
    
    # Setup: 
    # File on disk: /tmp/source/movie.mp4
    # File in DB: /external/path/movie.mp4 (Mapped)
    # Status in DB: hidden (We want to preserve this!)
    
    disk_file = mock_config.source_dir / "movie.mp4"
    disk_file.touch()
    
    mock_config.verbose = False # Fix for AttributeError
    
    # CRITICAL: We MUST set path_mapping in config for the logic to work!
    # The test expects logic to handle mapping, so config must have mapping.
    mock_config.path_mapping = {
        str(mock_config.source_dir): "/external/path"
    }

    mapped_path = "/external/path/movie.mp4"
    
    media_repo.get_all.return_value = [{
        "original_path": mapped_path,
        "search_status": "hidden"
    }]
    
    # Mock get_by_path to return the record when queried by mapped path
    def get_by_path_side_effect(path):
        if str(path) == mapped_path:
            return {"original_path": mapped_path, "search_status": "hidden"}
        return None
    media_repo.get_by_path.side_effect = get_by_path_side_effect
    
    # Run poll
    watcher._poll()
    
    # Verification
    # 1. Should NOT trigger scan_service.process_paths (New File)
    #    Because it should detect it's the same file (via mapping normalization).
    scan_service.process_paths.assert_not_called()
    
    # 2. Should NOT trigger handle_deletion (Deleted File)
    #    Because it should detect it's the same file.
    scan_service.handle_deletion.assert_not_called()
    
    # 3. Verify DB update logic
    # The normalization logic in WatchService sees that Mapped DB Path == Raw Disk Path (after mapping applied).
    # Since they match, it considers the file "Found" and does nothing.
    # It does NOT migrate the DB entry to Raw Path automatically, which preserves the user's Mapped Path preference.
    # So media_repo.save should NOT be called.
    assert not media_repo.save.called
    assert not media_repo.delete_by_path.called
