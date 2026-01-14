# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
import sqlite3
import os
from pathlib import Path
from src.infrastructure.db.database import Database
from src.infrastructure.db.repository import MediaRepository, LogRepository, SymlinkRepository

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"

@pytest.fixture
def database(db_path):
    return Database(db_path)

@pytest.fixture
def media_repo(database):
    return MediaRepository(database)

@pytest.fixture
def log_repo(database):
    return LogRepository(database)

@pytest.fixture
def symlink_repo(database):
    return SymlinkRepository(database)

@pytest.fixture
def mock_config(tmp_path):
    class Config:
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        tmdb_api_key = "fake_key"
        video_extensions = [".mp4", ".mkv"]
        path_mapping = {}
        database_path = tmp_path / "test.db"
    
    Config.source_dir.mkdir()
    Config.target_dir.mkdir()
    return Config()
