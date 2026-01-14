# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.server.app import Server
from src.core.models import MediaType, MediaItem
from src.core.models import MediaFile

@pytest.fixture
def app_client(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        f.write(f"""
source_dir: "{source}"
target_dir: "{target}"
database_path: ":memory:"
video_extensions: [".mkv"]
tmdb_api_key: "dummy"
server_port: 5000
verbose: true
""")

    with patch('src.infrastructure.db.database.Database') as MockDB:
        server = Server(str(config_path))
        server.app.config.update({"TESTING": True})
        server.media_repo = MagicMock()
        server.link_service = MagicMock()
        
        # Real classifier with mocks for external deps?
        # Actually we need classifier to FAIL on these specific filenames to trigger fallback
        # "Cyberpunk.Edgerunners.02.Like.A.Boy..." usually fails standard regexes expecting SxxExx
        # But we can mock it to be sure.
        
        mock_classifier = MagicMock()
        def classify_side_effect(item):
            # Simulate failure to detect episode
            item.season = None
            item.episode = None
            return item
        mock_classifier.classify.side_effect = classify_side_effect
        server.scan_service.classifier = mock_classifier
        
        yield server.app.test_client(), source, server

def test_cyberpunk_fallback_logic(app_client):
    """
    Test the scenario:
    1. User searches "tmdb-105248" (Cyberpunk TV Show).
    2. Backend switches type to TV Show (simulated by input selection).
    3. Files are "Cyberpunk...02...", "Cyberpunk...03..." (no SxxExx).
    4. Verify backend assigns S01E01, S01E02 based on sort order.
    """
    client, source, server = app_client
    
    # 1. Setup Files (Cyberpunk style)
    # Using alphanumeric ordering
    folder = source / "Cyberpunk Edgerunners"
    folder.mkdir()
    
    # Create 3 files with names that sort correctly
    f1 = folder / "Cyberpunk.Edgerunners.01.mkv"
    f2 = folder / "Cyberpunk.Edgerunners.02.mkv"
    f3 = folder / "Cyberpunk.Edgerunners.03.mkv"
    
    f1.touch()
    f2.touch()
    f3.touch()
    
    # 2. Payload
    # User selects "Movie" initially (because that's what UI defaulted to)
    # But provides a TV Show selection result (from ID lookup)
    payload = {
        "original_path": str(f1),
        "selection": {
            "title_cn": "赛博朋克：边缘行者",
            "tmdb_id": 105248,
            "media_type": "TV Show" # This triggers the switch
        },
        "type": "Movie", # Initial request type
        "apply_batch": True
    }
    
    # 3. Mock Scanner to return these files
    with patch("src.core.scanner.Scanner") as MockScanner, \
         patch("src.core.renamer.Renamer") as MockRenamer:
             
        scanner_instance = MockScanner.return_value
        # Return files in random order to test sorting
        scanner_instance.scan.return_value = [
            MediaFile(path=f3, extension=".mkv", size=0, mtime=0),
            MediaFile(path=f1, extension=".mkv", size=0, mtime=0),
            MediaFile(path=f2, extension=".mkv", size=0, mtime=0)
        ]
        
        renamer_instance = MockRenamer.return_value
        renamer_instance.get_suggested_path.return_value = Path("/target/dummy")
        
        # 4. Execute
        response = client.post("/api/confirm", json=payload)
        
        assert response.status_code == 200
        
        # 5. Verify Logic
        # We expect 3 calls to save()
        assert server.media_repo.save.call_count == 3
        
        # Inspect saved records to check if Season/Episode was assigned correctly
        # We need to capture the 'target_path' logic or check how item was constructed.
        # But wait, 'save' takes a dict. The 'target_path' is from renamer.
        # But we mocked renamer.
        
        # We should verify that the Items passed to Renamer had correct S/E.
        # Renamer.get_suggested_path(item, file)
        
        calls = renamer_instance.get_suggested_path.call_args_list
        assert len(calls) == 3
        
        # Verify items in calls
        # Call 1 -> Should be f1 (01.mkv) -> S1E1
        # Call 2 -> Should be f2 (02.mkv) -> S1E2
        # Call 3 -> Should be f3 (03.mkv) -> S1E3
        
        # Note: calls might not be in order of files if implementation changes, 
        # but our implementation sorts files.
        
        # Let's extract items and files
        items_processed = []
        for call in calls:
            item, file = call[0]
            items_processed.append((str(file.path), item.season, item.episode))
            
        # Sort by file path to verify
        items_processed.sort(key=lambda x: x[0])
        
        assert items_processed[0][0].endswith("01.mkv")
        assert items_processed[0][1] == 1 and items_processed[0][2] == 1
        
        assert items_processed[1][0].endswith("02.mkv")
        assert items_processed[1][1] == 1 and items_processed[1][2] == 2
        
        assert items_processed[2][0].endswith("03.mkv")
        assert items_processed[2][1] == 1 and items_processed[2][2] == 3
