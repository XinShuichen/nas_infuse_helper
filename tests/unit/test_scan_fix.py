# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.services.scan_service import ScanService
from src.core.models import MediaItem, MediaType, MediaFile

def test_scan_service_saves_files_not_directory_when_unknown():
    """
    Test that when an item is unknown, we save its individual files to DB,
    NOT the directory path.
    """
    # Setup
    config = MagicMock()
    config.video_extensions = ['.mp4']
    media_repo = MagicMock()
    log_repo = MagicMock()
    match_service = MagicMock()
    link_service = MagicMock()
    
    service = ScanService(config, media_repo, log_repo, match_service, link_service)
    
    # Mock item (Unknown TV Show Directory)
    dir_path = Path("/downloads/MyShow")
    file1 = MediaFile(path=dir_path / "ep1.mp4", extension=".mp4", size=100, mtime=0)
    file2 = MediaFile(path=dir_path / "ep2.mp4", extension=".mp4", size=100, mtime=0)
    
    item = MediaItem(
        name="MyShow",
        original_path=dir_path, # This is a directory!
        files=[file1, file2],
        media_type=MediaType.TV_SHOW,
        search_status="pending" # Unknown
    )
    
    # Mock classifier/match to return the item as is
    service.classifier.classify = MagicMock(return_value=item)
    service.match_service.process_item = MagicMock(return_value=item)
    
    # Execute
    service._process_single_item(item)
    
    # Verify
    # Should call save 2 times (once for each file)
    # Should NOT call save with dir_path
    
    assert media_repo.save.call_count == 2
    
    calls = media_repo.save.call_args_list
    saved_paths = [c[0][0]['original_path'] for c in calls]
    
    assert str(file1.path) in saved_paths
    assert str(file2.path) in saved_paths
    assert str(dir_path) not in saved_paths

def test_scan_service_continues_on_error():
    """
    Test that process_paths continues even if one item fails.
    """
    config = MagicMock()
    config.video_extensions = ['.mp4']
    media_repo = MagicMock()
    log_repo = MagicMock()
    match_service = MagicMock()
    link_service = MagicMock()
    
    service = ScanService(config, media_repo, log_repo, match_service, link_service)
    
    # Mock Aggregator to return 2 items
    item1 = MediaItem(name="Item1", original_path=Path("/1"), files=[], media_type=MediaType.MOVIE)
    item2 = MediaItem(name="Item2", original_path=Path("/2"), files=[], media_type=MediaType.MOVIE)
    
    service.aggregator.aggregate = MagicMock(return_value=[item1, item2])
    
    # Mock process_single_item to fail for first item
    service._process_single_item = MagicMock(side_effect=[Exception("TMDB Error"), None])
    
    # Execute - Pass MediaFile objects to bypass disk checks
    f1 = MediaFile(path=Path("/1.mp4"), extension=".mp4", size=0, mtime=0)
    f2 = MediaFile(path=Path("/2.mp4"), extension=".mp4", size=0, mtime=0)
    service.process_paths([f1, f2])
    
    # Verify
    # Should have called _process_single_item twice
    assert service._process_single_item.call_count == 2
