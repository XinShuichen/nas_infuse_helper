# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.services.watch_service import WatchService
from src.core.config import Config
from src.services.scan_service import ScanService
from src.infrastructure.db.repository import MediaRepository

@pytest.fixture
def mock_config(tmp_path):
    config = MagicMock(spec=Config)
    config.source_dir = tmp_path
    config.scan_interval_minutes = 60
    config.video_extensions = [".mp4", ".mkv"]
    config.path_mapping = {}
    config.verbose = False # Fix for AttributeError
    return config

@pytest.fixture
def mock_services():
    scan = MagicMock(spec=ScanService)
    repo = MagicMock(spec=MediaRepository)
    return scan, repo

def test_polling_detects_new_files(mock_config, mock_services):
    scan_service, media_repo = mock_services
    watcher = WatchService(mock_config, scan_service, media_repo)
    
    # Setup: DB is empty
    media_repo.get_all.return_value = []
    
    # Create a file
    new_file = mock_config.source_dir / "test.mp4"
    new_file.touch()
    
    # Run one poll
    watcher._poll()
    
    # Verify process_paths called
    assert scan_service.process_paths.called
    args = scan_service.process_paths.call_args[0][0]
    assert len(args) == 1
    assert args[0].path.name == "test.mp4"

def test_polling_detects_deletions(mock_config, mock_services):
    scan_service, media_repo = mock_services
    watcher = WatchService(mock_config, scan_service, media_repo)
    
    # Setup: DB has file, Disk does not
    deleted_path = str(mock_config.source_dir / "deleted.mp4")
    media_repo.get_all.return_value = [{"original_path": deleted_path}]
    
    # Run poll
    watcher._poll()
    
    # Verify handle_deletion called
    scan_service.handle_deletion.assert_called_with(deleted_path)

def test_polling_ignores_hidden_files(mock_config, mock_services):
    scan_service, media_repo = mock_services
    watcher = WatchService(mock_config, scan_service, media_repo)
    
    # Setup: File on disk, DB has it as 'hidden'
    hidden_file = mock_config.source_dir / "hidden.mp4"
    hidden_file.touch()
    
    media_repo.get_all.return_value = [{
        "original_path": str(hidden_file),
        "search_status": "hidden"
    }]
    
    # Run poll
    watcher._poll()
    
    # Verify NOT processed
    scan_service.process_paths.assert_not_called()
