# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
import os
from pathlib import Path
from unittest.mock import MagicMock
from src.core.scanner import Scanner
from src.services.scan_service import ScanService
from src.core.models import MediaFile
from src.core.config import Config

@pytest.fixture
def temp_env(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    return source, target

def test_scanner_ignores_non_video_files(temp_env):
    source, _ = temp_env
    
    # Create various files
    (source / "video.mp4").touch()
    (source / "video.mkv").touch()
    (source / "image.jpg").touch()
    (source / "text.txt").touch()
    (source / "script.py").touch()
    (source / "log").touch()  # No extension
    (source / ".DS_Store").touch()
    
    # Create hidden dir
    (source / "#recycle").mkdir()
    (source / "#recycle" / "trash.mp4").touch()
    
    scanner = Scanner(video_extensions=[".mp4", ".mkv"])
    files = scanner.scan(source)
    
    # Verify
    filenames = [f.path.name for f in files]
    assert "video.mp4" in filenames
    assert "video.mkv" in filenames
    assert "image.jpg" not in filenames
    assert "text.txt" not in filenames
    assert "script.py" not in filenames
    assert "log" not in filenames
    assert ".DS_Store" not in filenames
    assert "trash.mp4" not in filenames

def test_scan_service_process_paths_filtering(temp_env):
    source, target = temp_env
    
    # Mock Config
    config = MagicMock(spec=Config)
    config.source_dir = source
    config.target_dir = target
    config.video_extensions = [".mp4", ".mkv"]
    config.path_mapping = {}
    
    # Mock Repos
    media_repo = MagicMock()
    log_repo = MagicMock()
    match_service = MagicMock()
    link_service = MagicMock()
    
    service = ScanService(config, media_repo, log_repo, match_service, link_service)
    
    # Create files
    video = source / "movie.mp4"
    video.touch()
    logfile = source / "log"
    logfile.touch()
    
    # 1. Test processing explicit list of paths
    # Passing 'log' file explicitly (e.g. from WatchService poll bug?)
    service.process_paths([video, logfile])
    
    # Check what was passed to aggregator/classifier
    # We can check verify by inspecting calls to match_service.process_item
    # Only the video should be processed.
    
    # Since ScanService aggregates first, we need to mock aggregator?
    # ScanService uses self.aggregator.aggregate(media_files)
    # Let's inspect the media_files passed to aggregator if we can mock it?
    # Or easier: Mock match_service.process_item
    
    assert match_service.process_item.call_count <= 1
    # If it was called, it should be for the video
    if match_service.process_item.called:
        item = match_service.process_item.call_args[0][0]
        assert item.name == "movie"
        assert len(item.files) == 1
        assert item.files[0].path.name == "movie.mp4"

def test_watch_service_poll_filtering(temp_env):
    source, target = temp_env
    
    # Create files
    (source / "movie.mp4").touch()
    (source / "log").touch()
    
    from src.services.watch_service import WatchService
    
    # Mock dependencies
    config = MagicMock(spec=Config)
    config.source_dir = source
    config.video_extensions = [".mp4"]
    config.path_mapping = {}
    config.verbose = False  # Fix for AttributeError
    
    scan_service = MagicMock()
    media_repo = MagicMock()
    media_repo.get_all.return_value = []
    
    watcher = WatchService(config, scan_service, media_repo)
    
    # Run poll
    watcher._poll()
    
    # Verify scan_service.process_paths called with ONLY mp4
    assert scan_service.process_paths.called
    args = scan_service.process_paths.call_args[0][0] # List[MediaFile]
    
    filenames = [f.path.name for f in args]
    assert "movie.mp4" in filenames
    assert "log" not in filenames
