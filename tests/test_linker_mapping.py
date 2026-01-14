# Copyright (c) 2025 Trae AI. All rights reserved.

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import os
import shutil
from src.core.linker import Linker

class TestLinkerMapping(unittest.TestCase):
    def setUp(self):
        self.target_dir = Path("tests/temp_target")
        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)
        self.target_dir.mkdir(parents=True)
        
        self.db_manager = MagicMock()
        self.path_mapping = {"/datanas": "/volume1/PT-DATA"}
        self.linker = Linker(self.target_dir, self.db_manager, self.path_mapping)

    def tearDown(self):
        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)

    @patch("os.symlink")
    def test_link_file_with_mapping(self, mock_symlink):
        source_path = Path("/datanas/Movies/TestMovie/movie.mp4")
        relative_target_path = Path("Movies/TestMovie/movie.mp4")
        
        self.linker.link_file(source_path, relative_target_path, "Movie")
        
        # Verify os.symlink was called with the mapped path
        expected_source = "/volume1/PT-DATA/Movies/TestMovie/movie.mp4"
        expected_target = self.target_dir / relative_target_path
        
        mock_symlink.assert_called_with(expected_source, expected_target)

    @patch("os.symlink")
    def test_link_file_without_mapping_match(self, mock_symlink):
        source_path = Path("/other/Movies/TestMovie/movie.mp4")
        relative_target_path = Path("Movies/TestMovie/movie.mp4")
        
        self.linker.link_file(source_path, relative_target_path, "Movie")
        
        # Verify os.symlink was called with the original path
        expected_source = str(source_path)
        expected_target = self.target_dir / relative_target_path
        
        mock_symlink.assert_called_with(expected_source, expected_target)

if __name__ == "__main__":
    unittest.main()
