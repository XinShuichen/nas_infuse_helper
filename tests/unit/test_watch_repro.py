# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.services.watch_service import WatchService
from src.core.config import Config
from src.core.models import MediaFile

@pytest.fixture
def watch_env(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    config = MagicMock(spec=Config)
    config.source_dir = source
    config.video_extensions = [".mp4", ".mkv"]
    config.path_mapping = {}  # No mapping for this test
    config.verbose = True
    return config, source

def test_watch_service_auto_heals_directory_record_in_db(watch_env):
    """
    Reproduce the bug where DB has a directory path instead of a file path.
    Verify that WatchService detects this as a "deletion" of the directory
    AND an "addition" of the files inside it.
    
    The key is that ScanService (mocked here) needs to handle the addition correctly
    by saving FILES not DIRECTORIES (which was the fix in ScanService).
    
    Here we test that WatchService correctly identifies the situation.
    """
    config, source = watch_env
    
    # 1. Create a directory with a file on disk
    show_dir = source / "MyShow"
    show_dir.mkdir()
    episode = show_dir / "ep1.mp4"
    episode.touch()
    
    # 2. Simulate DB having the DIRECTORY path (The Bug State)
    # The DB thinks "MyShow" is the media item, not "ep1.mp4"
    bad_db_record = str(show_dir)
    
    media_repo = MagicMock()
    media_repo.get_all.return_value = [{"original_path": bad_db_record, "search_status": "pending"}]
    # Mock db_path_map to return the bad record
    
    scan_service = MagicMock()
    watcher = WatchService(config, scan_service, media_repo)
    
    # Execute Poll
    watcher._poll()
    
    # Verification
    
    # 1. WatchService should see "MyShow" (directory) as DELETED
    # because scan() only returns files, so "MyShow" is not in current_files.
    # AND WatchService's deletion logic (now fixed) should realize it's a directory
    # and mark it for removal.
    
    # The fix in WatchService was:
    # if path_obj.exists() and path_obj.is_dir():
    #     self.logger.warning(...)
    #     real_deletions.add(p) -> It SHOULD be added to deletions so it gets removed from DB!
    
    assert scan_service.handle_deletion.called
    # call_args_list items are tuples of (args, kwargs)
    # args[0] is the first positional arg (the path string)
    deleted_args = [call.args[0] for call in scan_service.handle_deletion.call_args_list]
    assert bad_db_record in deleted_args
    
    # 2. WatchService should see "ep1.mp4" as NEW
    assert scan_service.process_paths.called
    new_files_args = scan_service.process_paths.call_args[0][0] # List[MediaFile]
    new_paths = [str(f.path) for f in new_files_args]
    assert str(episode) in new_paths

def test_watch_service_ignores_false_deletion_of_directory_if_it_does_not_exist(watch_env):
    """
    If DB has a directory that truly doesn't exist anymore, it should be deleted.
    """
    config, source = watch_env
    
    # DB has a path that was a directory, but now is gone from disk
    missing_dir = source / "GoneShow"
    # Do NOT create it on disk
    
    media_repo = MagicMock()
    media_repo.get_all.return_value = [{"original_path": str(missing_dir), "search_status": "pending"}]
    
    scan_service = MagicMock()
    watcher = WatchService(config, scan_service, media_repo)
    
    watcher._poll()
    
    # Should be deleted
    scan_service.handle_deletion.assert_called_with(str(missing_dir))

def test_watch_service_ignores_false_deletion_if_exists_but_filtered(watch_env):
    """
    If DB has a file, and it exists on disk, but scan() missed it (e.g. temporary glitch or filter),
    WatchService should NOT delete it if it physically exists.
    Wait, the current logic says:
    if path_obj.exists() and path_obj.is_file():
         # Exists and IS a file? Then why is it in deleted_normalized?
         # Because it's not in disk_paths.
         pass -> Implicitly NOT added to real_deletions.
    """
    config, source = watch_env
    
    # File exists on disk
    existing_file = source / "movie.mp4"
    existing_file.touch()
    
    # File is in DB
    media_repo = MagicMock()
    media_repo.get_all.return_value = [{"original_path": str(existing_file), "search_status": "found"}]
    
    # But for some reason, current_files (scan result) is EMPTY
    # We can simulate this by mocking rglobl or just filtering config extensions to mismatch
    config.video_extensions = [".mkv"] # File is .mp4, so scan() will ignore it
    
    scan_service = MagicMock()
    watcher = WatchService(config, scan_service, media_repo)
    
    watcher._poll()
    
    # Should NOT be deleted because it physically exists
    scan_service.handle_deletion.assert_not_called()
