# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from pathlib import Path
from src.core.renamer import Renamer
from src.core.models import MediaItem, MediaType, MediaFile

def test_renamer_respects_item_season_episode():
    renamer = Renamer()
    
    # 1. Setup an Item that HAS season/episode assigned (e.g. from manual fallback)
    # But the filename is garbage (no SxxExx)
    item = MediaItem(
        name="MyShow",
        original_path=Path("/source/MyShow/garbage_01.mkv"),
        files=[],
        media_type=MediaType.TV_SHOW,
        title_cn="测试剧集",
        season=1,
        episode=5  # Manually assigned
    )
    
    file = MediaFile(
        path=Path("/source/MyShow/garbage_01.mkv"),
        extension=".mkv",
        size=0,
        mtime=0
    )
    
    # 2. Get suggested path
    path = renamer.get_suggested_path(item, file)
    
    # 3. Verify it used S1E5
    path_str = str(path)
    assert "TV Shows" in path_str
    assert "Season 1" in path_str
    assert "S01E05" in path_str # Should be formatted correctly

def test_renamer_fallback_to_filename_if_item_se_missing():
    renamer = Renamer()
    
    # Item has NO season/episode
    item = MediaItem(
        name="MyShow",
        original_path=Path("/source/MyShow/MyShow.S02E10.mkv"),
        files=[],
        media_type=MediaType.TV_SHOW,
        title_cn="测试剧集"
    )
    
    file = MediaFile(
        path=Path("/source/MyShow/MyShow.S02E10.mkv"),
        extension=".mkv",
        size=0,
        mtime=0
    )
    
    path = renamer.get_suggested_path(item, file)
    path_str = str(path)
    
    assert "TV Shows" in path_str
    assert "Season 2" in path_str
    assert "S02E10" in path_str
