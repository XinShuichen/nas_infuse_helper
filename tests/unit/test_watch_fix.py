# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.services.watch_service import WatchService
from src.core.config import Config

@pytest.fixture
def watch_env(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    config = MagicMock(spec=Config)
    config.source_dir = source
    config.video_extensions = [".mp4", ".mkv"]
    config.path_mapping = {"/datanas": "/volume1/PT-DATA"}
    config.verbose = False
    return config, source

def test_watch_service_ignores_recycle_folder(watch_env):
    config, source = watch_env
    
    # Create normal file
    (source / "movie.mp4").touch()
    
    # Create recycle file
    recycle = source / "#recycle"
    recycle.mkdir()
    (recycle / "deleted.mp4").touch()
    
    # Mock deps
    scan_service = MagicMock()
    media_repo = MagicMock()
    media_repo.get_all.return_value = [] # No existing DB records
    
    watcher = WatchService(config, scan_service, media_repo)
    watcher._poll()
    
    # Verify only movie.mp4 is processed
    assert scan_service.process_paths.called
    args = scan_service.process_paths.call_args[0][0] # List[MediaFile]
    
    paths = [str(f.path) for f in args]
    assert any("movie.mp4" in p for p in paths)
    assert not any("deleted.mp4" in p for p in paths)

def test_watch_service_handles_path_mapping_diff(watch_env):
    """
    Test that if DB has Mapped path and Disk has Raw path, they are considered SAME.
    """
    config, source = watch_env
    # source is like /tmp/source (Raw path on this machine)
    # But let's pretend config.source_dir IS /datanas for logic testing
    # Since we can't easily change real paths, we mock the path strings.
    
    # Let's adjust the config.path_mapping to match our temp env
    # Raw: str(source)
    # Mapped: "/mapped/source"
    config.path_mapping = {str(source): "/mapped/source"}
    
    # 1. File on disk (Raw)
    disk_file = source / "movie.mp4"
    disk_file.touch()
    
    # 2. File in DB (Mapped)
    mapped_path = f"/mapped/source/movie.mp4"
    
    media_repo = MagicMock()
    media_repo.get_all.return_value = [{"original_path": mapped_path, "search_status": "found"}]
    
    scan_service = MagicMock()
    watcher = WatchService(config, scan_service, media_repo)
    
    # Execute Poll
    watcher._poll()
    
    # Verification
    # Should NOT detect new files (because disk_file matches mapped_path via normalization)
    # Should NOT detect deleted files (because mapped_path matches disk_file)
    
    # process_paths should NOT be called (no new files)
    scan_service.process_paths.assert_not_called()
    
    # handle_deletion should NOT be called
    scan_service.handle_deletion.assert_not_called()
