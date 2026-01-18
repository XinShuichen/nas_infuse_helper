# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.server.app import Server
from src.core.models import MediaType, MediaItem
from src.core.config import Config

@pytest.fixture
def app_client(tmp_path):
    # Setup directories
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    
    # Create config file
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        f.write(f"""
source_dir: "{source}"
target_dir: "{target}"
database_path: ":memory:"
video_extensions: [".mp4", ".mkv"]
tmdb_api_key: "dummy"
server_port: 5000
verbose: true
""")

    # Mock DB and Repos
    with patch('src.infrastructure.db.database.Database') as MockDB:
        server = Server(str(config_path))
        server.app.config.update({"TESTING": True})
        
        # Mock repositories to avoid real DB calls
        server.media_repo = MagicMock()
        server.link_service = MagicMock()
        server.scan_service = MagicMock() # We need real classifier logic though?
        
        # We want to test the LOGIC in confirm_selection, which uses 
        # server.scan_service.classifier (if we modify app.py to use it)
        # Or we can just mock the scanner/renamer inside app.py if it imports them locally.
        # Currently app.py imports Scanner, Renamer locally in the function.
        
        yield server.app.test_client(), source, server

def test_confirm_selection_batch_processing(app_client):
    client, source, server = app_client
    
    # 1. Setup Files
    # /source/Cyberpunk/ep1.mkv
    # /source/Cyberpunk/ep2.mkv
    series_dir = source / "Cyberpunk"
    series_dir.mkdir()
    (series_dir / "ep1.mkv").touch()
    (series_dir / "ep2.mkv").touch()
    
    # 2. Prepare Request
    # User selects ep1.mkv and confirms it as "Cyberpunk Edgerunners" (ID 100)
    # AND requests batch application
    payload = {
        "original_path": str(series_dir / "ep1.mkv"),
        "selection": {
            "title_cn": "边缘行者",
            "title_en": "Cyberpunk: Edgerunners",
            "tmdb_id": 100,
            "year": 2022
        },
        "type": "TV Show",
        "apply_batch": True  # New flag
    }
    
    # 3. Mock internal dependencies of the route
    # The route imports Scanner and Renamer INSIDE the function.
    # So we cannot patch them on 'src.server.app.Scanner' because they are not module-level attributes.
    # We must patch where they come from: 'src.core.scanner.Scanner' and 'src.core.renamer.Renamer'
    
    with patch("src.core.scanner.Scanner") as MockScanner, \
         patch("src.core.renamer.Renamer") as MockRenamer:
             
        # Setup Scanner to return both files when scanned
        scanner_instance = MockScanner.return_value
        from src.core.models import MediaFile
        
        # When scanning the directory
        scanner_instance.scan.return_value = [
            MediaFile(path=series_dir/"ep1.mkv", extension=".mkv", size=0, mtime=0),
            MediaFile(path=series_dir/"ep2.mkv", extension=".mkv", size=0, mtime=0)
        ]
        
        # Setup Renamer to return dummy paths
        renamer_instance = MockRenamer.return_value
        renamer_instance.get_suggested_path.side_effect = lambda item, file: Path(f"/target/Show/{file.path.name}")
        
        # We also need Classifier logic to extract S/E? 
        # The current app.py doesn't use Classifier in confirm_selection yet. 
        # But our plan requires it.
        # So we should expect the code to use Classifier.
        
        # Let's inject a mock classifier into the server instance if the code uses self.scan_service.classifier
        mock_classifier = MagicMock()
        # Mock classify to return item with season/episode
        def side_effect_classify(item):
            # Simple mock parsing
            if "ep1" in item.files[0].path.name:
                item.season = 1
                item.episode = 1
            elif "ep2" in item.files[0].path.name:
                item.season = 1
                item.episode = 2
            return item
            
        mock_classifier.classify.side_effect = side_effect_classify
        server.scan_service.classifier = mock_classifier

        # 4. Execute
        response = client.post("/api/confirm", json=payload)
        
        # 5. Verify
        assert response.status_code == 200
        data = response.json
        # Expecting to process 2 files
        # The response structure depends on implementation
        assert data.get("processed_count") == 2
        
        # Verify Repo Calls
        # save() should be called twice (once for ep1, once for ep2)
        assert server.media_repo.save.call_count == 2
        
        saved_records = [call[0][0] for call in server.media_repo.save.call_args_list]
        paths = [r["original_path"] for r in saved_records]
        assert str(series_dir / "ep1.mkv") in paths
        assert str(series_dir / "ep2.mkv") in paths
        
        # Verify Link Service
        assert server.link_service.link_item.call_count == 2

def test_confirm_selection_batch_ignored_in_root(app_client):
    client, source, server = app_client
    
    # 1. Setup Files in ROOT
    # /source/root_ep1.mkv
    # /source/root_ep2.mkv
    (source / "root_ep1.mkv").touch()
    (source / "root_ep2.mkv").touch()
    
    # 2. Payload with apply_batch=True
    payload = {
        "original_path": str(source / "root_ep1.mkv"),
        "selection": {"tmdb_id": 100},
        "type": "TV Show",
        "apply_batch": True
    }
    
    with patch("src.core.scanner.Scanner") as MockScanner, \
         patch("src.core.renamer.Renamer") as MockRenamer:
        scanner_instance = MockScanner.return_value
        # If it were to scan, it would find both. 
        # But we expect it NOT to scan root.
        
        # Setup Renamer
        renamer_instance = MockRenamer.return_value
        renamer_instance.get_suggested_path.return_value = Path("/target/Show/root_ep1.mkv")

        # Mock Classifier (implicit in scan_service)
        mock_classifier = MagicMock()
        mock_classifier.classify.side_effect = lambda item: item # Return item as is
        server.scan_service.classifier = mock_classifier

        # Execute
        response = client.post("/api/confirm", json=payload)
        
        assert response.status_code == 200
        # Should only process 1 file (safety check)
        # Note: If implementation falls back to single file, count is 1.
        # We need to verify that.
        
        # Check save calls
        assert server.media_repo.save.call_count == 1
        saved = server.media_repo.save.call_args[0][0]
        assert saved["original_path"] == str(source / "root_ep1.mkv")


def test_confirm_selection_requires_tmdb_id(app_client):
    client, source, server = app_client
    (source / "movie.mkv").touch()

    payload = {
        "original_path": str(source / "movie.mkv"),
        "selection": {"title_cn": "测试"},
        "type": "Movie",
        "apply_batch": False,
    }

    response = client.post("/api/confirm", json=payload)
    assert response.status_code == 400
    assert server.media_repo.save.call_count == 0
    assert server.link_service.link_item.call_count == 0
