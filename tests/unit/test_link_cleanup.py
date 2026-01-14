# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.services.link_service import LinkService
from src.core.models import MediaItem, MediaType, MediaFile

@pytest.fixture
def link_service_setup(tmp_path):
    config = MagicMock()
    config.target_dir = tmp_path / "target"
    config.path_mapping = {}
    
    media_repo = MagicMock()
    symlink_repo = MagicMock()
    log_repo = MagicMock()
    
    service = LinkService(config, media_repo, symlink_repo, log_repo)
    return service, symlink_repo, tmp_path

def test_link_item_cleans_up_old_link(link_service_setup):
    service, symlink_repo, tmp_path = link_service_setup
    target_dir = tmp_path / "target"
    
    # 1. Setup
    source_path = Path("/source/file.mkv")
    
    # Simulate an OLD link existing at "Movies/file.mkv"
    old_link_path = target_dir / "Movies/file.mkv"
    old_link_path.parent.mkdir(parents=True)
    old_link_path.touch() # Create dummy file/link
    
    # SymlinkRepo returns this old path
    symlink_repo.get_by_source.return_value = str(old_link_path)
    
    # 2. New Mapping (moved to TV Shows)
    new_rel_path = Path("TV Shows/Show/file.mkv")
    full_new_path = target_dir / new_rel_path
    
    item = MediaItem(name="Test", original_path=source_path, files=[], media_type=MediaType.TV_SHOW)
    mappings = [(MediaFile(path=source_path, extension=".mkv", size=0, mtime=0), new_rel_path)]
    
    # 3. Execute
    with patch("os.symlink") as mock_symlink:
        service.link_item(item, mappings)
        
        # 4. Verify
        # Old link should be gone
        assert not old_link_path.exists()
        
        # New link creation attempted
        mock_symlink.assert_called_with(str(source_path), full_new_path)
        
        # Verify SymlinkRepo update
        symlink_repo.add.assert_called_with(source_path, full_new_path)
