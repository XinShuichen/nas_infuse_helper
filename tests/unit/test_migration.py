# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import sys

# Add scripts path to sys.path to import rebuild_db
sys.path.append(str(Path(__file__).resolve().parents[2] / "scripts"))

# Import the module (it might fail if dependencies aren't found, but PYTHONPATH should handle it)
# We need to make sure src is in path too, which is handled by previous export PYTHONPATH
import rebuild_db

@pytest.fixture
def mock_fs(tmp_path):
    # Create a mock target structure
    target_dir = tmp_path / "organized"
    movies_dir = target_dir / "Movies"
    tv_dir = target_dir / "TV Shows"
    movies_dir.mkdir(parents=True)
    tv_dir.mkdir(parents=True)
    
    # Create a movie folder
    movie_name = "Inception (2010) {tmdb-27205}"
    movie_folder = movies_dir / movie_name
    movie_folder.mkdir()
    
    # Create a symlink in movie folder
    # Note: os.symlink might fail if we don't have permission or on some FS, but usually tmp_path supports it.
    # We'll just create a dummy file and mock is_symlink/readlink if needed, 
    # OR actually create it if possible.
    
    source_file = tmp_path / "source" / "Inception.mkv"
    source_file.parent.mkdir(parents=True)
    source_file.touch()
    
    link_file = movie_folder / "Inception.mkv"
    try:
        link_file.symlink_to(source_file)
    except OSError:
        # Fallback for systems that don't support symlinks (unlikely in this env but good practice)
        pass
        
    return target_dir, source_file

def test_parse_folder_name():
    # Test cases for parse_folder_name
    cases = [
        ("Inception (2010) {tmdb-27205}", ("Inception", None, 2010, 27205)),
        ("Start-Up (Start Up) (2020) {tmdb-109983}", ("Start-Up", "Start Up", 2020, 109983)),
        ("No Year {tmdb-123}", ("No Year", None, None, 123)),
        # Chinese title with English
        ("星际穿越 (Interstellar) (2014) {tmdb-157336}", ("星际穿越", "Interstellar", 2014, 157336)),
    ]
    
    for folder_name, expected in cases:
        assert rebuild_db.parse_folder_name(folder_name) == expected

@patch("rebuild_db.Database")
@patch("rebuild_db.MediaRepository")
@patch("rebuild_db.SymlinkRepository")
@patch("rebuild_db.load_config")
def test_rebuild_script(mock_load_config, MockSymlinkRepo, MockMediaRepo, MockDatabase, mock_fs):
    target_dir, source_file = mock_fs
    
    # Setup config mock
    mock_load_config.return_value = {
        "target_dir": str(target_dir),
        "database_path": ":memory:"
    }
    
    # Run rebuild
    rebuild_db.rebuild()
    
    # Verify MediaRepository.save was called
    mock_media_repo_instance = MockMediaRepo.return_value
    assert mock_media_repo_instance.save.called
    
    # Verify call args
    call_args = mock_media_repo_instance.save.call_args[0][0]
    assert call_args["title_cn"] == "Inception"
    assert call_args["year"] == 2010
    assert call_args["tmdb_id"] == 27205
    assert call_args["media_type"] == "Movie"
