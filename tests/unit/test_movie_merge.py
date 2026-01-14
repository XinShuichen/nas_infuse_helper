# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.core.renamer import Renamer
from src.core.models import MediaItem, MediaType, MediaFile

def test_renamer_merges_same_movie_files():
    """
    Test that multiple files belonging to the SAME Movie MediaItem
    are mapped to the SAME folder.
    """
    renamer = Renamer()
    
    # Setup: One Movie Item with 2 files (e.g. CD1, CD2)
    # They should end up in: Movies/My Movie (2000) {tmdb-123}/
    
    files = [
        MediaFile(path=Path("/source/movie-cd1.mkv"), extension=".mkv", size=0, mtime=0),
        MediaFile(path=Path("/source/movie-cd2.mkv"), extension=".mkv", size=0, mtime=0)
    ]
    
    item = MediaItem(
        name="My Movie",
        original_path=Path("/source/My Movie"),
        files=files,
        media_type=MediaType.MOVIE,
        title_cn="我的电影",
        title_en="My Movie",
        year=2000,
        tmdb_id=123,
        search_status="found"
    )
    
    # Calculate paths
    paths = []
    for f in item.files:
        paths.append(renamer.get_suggested_path(item, f))
    
    # Verify
    # Path 1: Movies/我的电影 (My Movie) (2000) {tmdb-123}/movie-cd1.mkv
    # Path 2: Movies/我的电影 (My Movie) (2000) {tmdb-123}/movie-cd2.mkv
    
    folder1 = paths[0].parent
    folder2 = paths[1].parent
    
    assert folder1 == folder2
    assert "我的电影 (My Movie) (2000) {tmdb-123}" in str(folder1)
    assert paths[0].name == "movie-cd1.mkv"
    assert paths[1].name == "movie-cd2.mkv"

def test_renamer_merges_separate_items_same_tmdb():
    """
    Test that two DIFFERENT MediaItems that match to the SAME TMDB ID
    end up in the SAME folder (Merging).
    """
    renamer = Renamer()
    
    # Item 1: /source/movie_a.mkv -> Matched ID 123
    file1 = MediaFile(path=Path("/source/movie_a.mkv"), extension=".mkv", size=0, mtime=0)
    item1 = MediaItem(
        name="movie_a",
        original_path=file1.path,
        files=[file1],
        media_type=MediaType.MOVIE,
        title_cn="我的电影",
        title_en="My Movie",
        year=2000,
        tmdb_id=123,
        search_status="found"
    )
    
    # Item 2: /source/other_folder/movie_b.mkv -> Matched ID 123 (Same movie, different copy)
    file2 = MediaFile(path=Path("/source/other_folder/movie_b.mkv"), extension=".mkv", size=0, mtime=0)
    item2 = MediaItem(
        name="movie_b",
        original_path=file2.path,
        files=[file2],
        media_type=MediaType.MOVIE,
        title_cn="我的电影",
        title_en="My Movie",
        year=2000,
        tmdb_id=123,
        search_status="found"
    )
    
    path1 = renamer.get_suggested_path(item1, file1)
    path2 = renamer.get_suggested_path(item2, file2)
    
    # Verify they share the same parent folder
    assert path1.parent == path2.parent
    assert "我的电影 (My Movie) (2000) {tmdb-123}" in str(path1.parent)
    
    # Filenames should be preserved (or sanitized)
    assert path1.name == "movie_a.mkv"
    assert path2.name == "movie_b.mkv"
