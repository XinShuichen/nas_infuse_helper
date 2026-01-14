# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.core.aggregator import Aggregator
from src.core.models import MediaFile

def test_aggregator_handles_flat_directory_with_many_files(tmp_path):
    source_dir = tmp_path / "downloads"
    source_dir.mkdir()
    
    files = []
    # Create 50 distinct movie files
    for i in range(50):
        f = source_dir / f"Random_Movie_{i}_(202{i%5}).mp4"
        f.touch()
        files.append(MediaFile(path=f, extension=".mp4", size=0, mtime=0))
        
    aggregator = Aggregator(source_dir)
    items = aggregator.aggregate(files)
    
    # We expect 50 separate items, NOT 1 big item named "downloads"
    assert len(items) == 50, f"Expected 50 items, got {len(items)}. Names: {[i.name for i in items]}"
    
    for item in items:
        assert len(item.files) == 1

def test_aggregator_groups_tv_show_in_flat_directory(tmp_path):
    source_dir = tmp_path / "downloads"
    source_dir.mkdir()
    
    files = []
    # Create a TV show (S01E01 - S01E10)
    for i in range(1, 11):
        f = source_dir / f"My_Show_S01E{i:02d}.mp4"
        f.touch()
        files.append(MediaFile(path=f, extension=".mp4", size=0, mtime=0))
        
    # And some unrelated movies
    f_movie = source_dir / "Other_Movie.mp4"
    f_movie.touch()
    files.append(MediaFile(path=f_movie, extension=".mp4", size=0, mtime=0))
    
    aggregator = Aggregator(source_dir)
    items = aggregator.aggregate(files)
    
    # Expect 2 items: "My Show" (10 files) and "Other Movie" (1 file)
    # Current logic might fail this if it relies on folders
    
    tv_shows = [i for i in items if "My_Show" in i.name]
    movies = [i for i in items if "Other_Movie" in i.name]
    
    assert len(tv_shows) == 1
    assert len(tv_shows[0].files) == 10
    assert len(movies) == 1
