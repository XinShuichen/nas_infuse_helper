# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.server.app import Server
from src.core.models import MediaFile

@pytest.fixture
def app_server():
    # Mock config
    with patch('src.server.app.Config') as MockConfig:
        MockConfig.load.return_value.source_dir = Path("/tmp/source")
        MockConfig.load.return_value.target_dir = Path("/tmp/target")
        MockConfig.load.return_value.database_path = ":memory:"
        MockConfig.load.return_value.video_extensions = [".mp4"]
        
        server = Server("dummy_config.yaml")
        server.app.config['TESTING'] = True
        
        return server

def test_hide_media_updates_status_and_unlinks(app_server):
    with app_server.app.test_client() as client:
        # Setup: Add item to DB
        original_path = "/tmp/source/movie.mp4"
        target_path = "/tmp/target/Movies/Movie (2024)/movie.mp4"
        
        app_server.media_repo.save({
            "original_path": original_path,
            "target_path": target_path,
            "search_status": "found"
        })
        
        # Mock unlink
        with patch('pathlib.Path.unlink') as mock_unlink:
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_symlink', return_value=True):
                    # Call Hide API
                    resp = client.post('/api/media/hide', json={"original_path": original_path})
                    assert resp.status_code == 200
                    
                    # Verify DB updated
                    item = app_server.media_repo.get_by_path(Path(original_path))
                    assert item['search_status'] == 'hidden'
                    
                    # Verify unlink called
                    # Note: We need to verify it was called on target_path
                    # Since we patched Path.unlink globally, any call is captured.
                    # Ideally check specific call but mock is simple here.
                    assert mock_unlink.called

def test_unhide_media_resets_status_and_triggers_scan(app_server):
    with app_server.app.test_client() as client:
        # Setup: Hidden item
        original_path = "/tmp/source/hidden_movie.mp4"
        app_server.media_repo.save({
            "original_path": original_path,
            "search_status": "hidden"
        })
        
        # Mock ScanService
        app_server.scan_service.process_paths = MagicMock()
        
        # Call Unhide API
        resp = client.post('/api/media/unhide', json={"original_path": original_path})
        assert resp.status_code == 200
        
        # Verify DB updated to pending
        item = app_server.media_repo.get_by_path(Path(original_path))
        assert item['search_status'] == 'pending'
        
        # Wait briefly for thread to start (unhide spawns thread)
        # In test environment, threads might be tricky. 
        # But we mocked process_paths.
        # We can join the thread if we had handle, but we don't.
        # Just sleep a tiny bit.
        import time
        time.sleep(0.1)
        
        # Verify scan triggered
        assert app_server.scan_service.process_paths.called
        args = app_server.scan_service.process_paths.call_args[0][0]
        assert len(args) == 1
        assert str(args[0].path) == original_path
