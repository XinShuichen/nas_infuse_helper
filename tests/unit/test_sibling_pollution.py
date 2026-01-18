# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.services.match_service import MatchService
from src.core.models import MediaItem, MediaType, MediaFile
from src.core.config import Config

@pytest.fixture
def mock_deps():
    config = MagicMock(spec=Config)
    config.source_dir = Path("/data/downloads")
    config.tmdb_api_key = "fake_key"
    
    media_repo = MagicMock()
    log_repo = MagicMock()
    
    return config, media_repo, log_repo

def test_sibling_pollution_in_root_dir(mock_deps):
    """
    Test that a file in the source root does NOT reuse metadata from a sibling
    if the directory is the source root (Mixed Content Risk).
    """
    config, media_repo, log_repo = mock_deps
    service = MatchService(config, media_repo, log_repo)
    
    # Setup: 
    # Root dir: /data/downloads
    # Sibling: /data/downloads/YiYi.mkv (Already matched as "Yi Yi" ID 25538)
    # Target: /data/downloads/Random_Movie.mkv (Unknown)
    
    target_file = config.source_dir / "Random_Movie.mkv"
    item = MediaItem(
        name="Random_Movie",
        original_path=target_file,
        files=[MediaFile(path=target_file, extension=".mkv", size=0, mtime=0)],
        media_type=MediaType.MOVIE
    )
    
    # Mock DB to return a sibling
    # get_by_path returns None (Target is new)
    media_repo.get_by_path.return_value = None
    
    # get_sibling_metadata returns the metadata of "Yi Yi"
    media_repo.get_sibling_metadata.return_value = {
        "tmdb_id": 25538,
        "title_cn": "一一",
        "title_en": "Yi Yi",
        "year": 2000,
        "media_type": "Movie"
    }
    
    # Mock Searcher to return nothing (so we rely on optimization logic)
    service.searcher.search = MagicMock(return_value=item) # Returns unmodified item
    
    # Execute
    result = service.process_item(item)
    
    # Verification
    # BUG EXPECTATION: It WILL match Yi Yi because of unsafe optimization
    # FIX EXPECTATION: It should NOT match Yi Yi (tmdb_id should be None or searcher result)
    
    # For reproduction, we assert the BAD behavior if we haven't fixed it yet?
    # Or we assert the GOOD behavior and expect fail.
    # Let's assert GOOD behavior.
    
    assert result.tmdb_id != 25538, "Should not reuse sibling metadata from source root!"
    assert result.title_cn != "一一"

def test_sibling_optimization_works_in_subdirs(mock_deps):
    """
    Test that sibling optimization STILL works for subdirectories (e.g. Season folders),
    assuming they are safe.
    """
    config, media_repo, log_repo = mock_deps
    service = MatchService(config, media_repo, log_repo)
    
    # Setup:
    # Dir: /data/downloads/MyShow_S01/
    # Sibling: /data/downloads/MyShow_S01/E01.mkv (Matched)
    # Target: /data/downloads/MyShow_S01/E02.mkv
    
    subdir = config.source_dir / "MyShow_S01"
    target_file = subdir / "E02.mkv"
    item = MediaItem(
        name="E02",
        original_path=target_file,
        files=[MediaFile(path=target_file, extension=".mkv", size=0, mtime=0)],
        media_type=MediaType.TV_SHOW
    )
    
    media_repo.get_by_path.return_value = None
    media_repo.get_sibling_metadata.return_value = {
        "tmdb_id": 12345,
        "title_cn": "My Show",
        "title_en": "My Show",
        "year": 2020,
        "media_type": "TV Show"
    }
    service.searcher.search = MagicMock(return_value=item)
    
    # Execute
    result = service.process_item(item)
    
    # Verification
    # Should match because it's in a subdirectory (likely a series folder)
    # AND it is a TV Show (if we add that restriction)
    
    assert result.tmdb_id == 12345
    assert result.title_cn == "My Show"


def test_subtitle_reuses_metadata_in_subdir(mock_deps):
    config, media_repo, log_repo = mock_deps
    config.subtitle_extensions = [".srt", ".ass"]
    service = MatchService(config, media_repo, log_repo)

    parent_dir = config.source_dir / "MovieFolder"
    subtitle_path = parent_dir / "Movie.2023.chs.ass"
    item = MediaItem(
        name=subtitle_path.name,
        original_path=subtitle_path,
        files=[MediaFile(path=subtitle_path, extension=".ass", size=0, mtime=0)],
        media_type=MediaType.UNKNOWN,
    )

    media_repo.get_by_path.return_value = None
    media_repo.get_found_in_dir.return_value = [
        {
            "original_path": str(parent_dir / "Movie.2023.mkv"),
            "tmdb_id": 999,
            "title_cn": "电影",
            "title_en": "Movie",
            "year": 2023,
            "media_type": "Movie",
        }
    ]
    service.searcher.search = MagicMock(return_value=item)

    result = service.process_item(item)
    assert result.search_status == "found"
    assert result.tmdb_id == 999
    assert result.media_type == MediaType.MOVIE


def test_subtitle_does_not_reuse_metadata_in_source_root(mock_deps):
    config, media_repo, log_repo = mock_deps
    config.subtitle_extensions = [".srt", ".ass"]
    service = MatchService(config, media_repo, log_repo)

    subtitle_path = config.source_dir / "Random.Movie.ass"
    item = MediaItem(
        name=subtitle_path.name,
        original_path=subtitle_path,
        files=[MediaFile(path=subtitle_path, extension=".ass", size=0, mtime=0)],
        media_type=MediaType.UNKNOWN,
    )

    media_repo.get_by_path.return_value = None
    media_repo.get_found_in_dir.return_value = [
        {
            "original_path": str(config.source_dir / "Other.Movie.mkv"),
            "tmdb_id": 111,
            "title_cn": "别的电影",
            "title_en": "Other",
            "year": 2000,
            "media_type": "Movie",
        }
    ]
    service.searcher.search = MagicMock(return_value=item)

    result = service.process_item(item)
    assert result.tmdb_id != 111
