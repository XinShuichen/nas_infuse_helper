# Copyright (c) 2025 Trae AI. All rights reserved.

import unittest
from pathlib import Path
from src.core.renamer import Renamer
from src.core.models import MediaItem, MediaType, MediaFile

class TestRenamerLogic(unittest.TestCase):
    def setUp(self):
        self.renamer = Renamer()

    def test_tv_show_renaming_with_english_title(self):
        # Setup MediaItem with English title
        item = MediaItem(
            name="Breaking.Bad.S01E01.mkv",
            original_path=Path("/downloads/Breaking.Bad"),
            media_type=MediaType.TV_SHOW,
            title_cn="绝命毒师",
            title_en="Breaking Bad",
            tmdb_id=1396,
            year=2008,
            search_status="found"
        )
        
        file = MediaFile(
            path=Path("/downloads/Breaking.Bad/Breaking.Bad.S01E01.mkv"),
            extension=".mkv"
        )
        
        suggested_path = self.renamer.get_suggested_path(item, file)
        
        # Expected: TV Shows/绝命毒师 (Breaking Bad) (2008) {tmdb-1396}/Season 1/Breaking Bad S01E01.mkv
        expected_filename = "Breaking Bad S01E01.mkv"
        self.assertEqual(suggested_path.name, expected_filename)
        self.assertIn("Season 1", str(suggested_path))

    def test_tv_show_renaming_without_english_title(self):
        # Setup MediaItem without English title
        item = MediaItem(
            name="Unknown.Show.S01E01.mkv",
            original_path=Path("/downloads/Unknown.Show"),
            media_type=MediaType.TV_SHOW,
            title_cn="未知剧集",
            # title_en is None
            tmdb_id=12345,
            year=2020,
            search_status="found"
        )
        
        file = MediaFile(
            path=Path("/downloads/Unknown.Show/Unknown.Show.S01E01.mkv"),
            extension=".mkv"
        )
        
        suggested_path = self.renamer.get_suggested_path(item, file)
        
        # Expected: TV Shows/未知剧集 (2020) {tmdb-12345}/Season 1/S01E01.mkv
        expected_filename = "S01E01.mkv"
        self.assertEqual(suggested_path.name, expected_filename)

    def test_tv_show_renaming_sanitize_english_title(self):
        # Setup MediaItem with English title containing illegal chars
        item = MediaItem(
            name="Show.With.Colon.S01E01.mkv",
            original_path=Path("/downloads/Show"),
            media_type=MediaType.TV_SHOW,
            title_cn="冒号剧集",
            title_en="Show: The Beginning",
            tmdb_id=999,
            year=2021,
            search_status="found"
        )
        
        file = MediaFile(
            path=Path("/downloads/Show/Show.S01E01.mkv"),
            extension=".mkv"
        )
        
        suggested_path = self.renamer.get_suggested_path(item, file)
        
        # Expected: Show - The Beginning S01E01.mkv
        expected_filename = "Show - The Beginning S01E01.mkv"
        self.assertEqual(suggested_path.name, expected_filename)

if __name__ == "__main__":
    unittest.main()
