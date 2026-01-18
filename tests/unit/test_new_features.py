
import pytest
from pathlib import Path
from src.core.models import MediaItem, MediaType, MediaFile
from src.core.renamer import Renamer
from src.core.searcher import Searcher
from src.core.classifier import Classifier
from src.services.match_service import MatchService
from src.core.aggregator import Aggregator
from unittest.mock import MagicMock

class TestNewFeatures:
    """
    Tests for recent features:
    1. TMDB ID extraction from path (various formats)
    2. TV Show detection from folder names
    3. BDMV Movie name deduction
    4. Subtitle file handling and renaming
    """

    def test_tmdb_id_extraction(self):
        searcher = Searcher("mock_key")
        searcher.search_all = MagicMock(return_value=[]) # Mock network

        cases = [
            ("/data/TV Show {tmdb-12345}/S01/E01.mp4", "tmdb-12345"),
            ("/data/Movie (tmdb-67890)/movie.mkv", "tmdb-67890"),
            ("/data/Show [tmdbid-112233]/ep1.mkv", "tmdb-112233"),
            ("/data/Another Show (tmdb-tv-998877)/s01e01.mkv", "tmdb-tv-998877")
        ]

        for path_str, expected_alias in cases:
            p = Path(path_str)
            item = MediaItem(name=p.name, original_path=p)
            item = searcher.search(item)
            assert item.alias == expected_alias, f"Failed for {path_str}"

    def test_tv_folder_detection(self):
        classifier = Classifier([".mp4", ".mkv"])

        cases = [
            ("/data/TV Show/Season 1/01.mp4", MediaType.TV_SHOW),
            ("/data/Another Show S01/ep1.mkv", MediaType.TV_SHOW),
            ("/data/Show/第1季/01.mp4", MediaType.TV_SHOW),
            ("/data/Movie (2022)/movie.mp4", MediaType.MOVIE), # Should NOT match
        ]

        for path_str, expected_type in cases:
            p = Path(path_str)
            # Create item as if it's a single file first (common failure case)
            item = MediaItem(
                name=p.name,
                original_path=p,
                files=[MediaFile(path=p, extension=p.suffix)]
            )
            item = classifier.classify(item)
            assert item.media_type == expected_type, f"Failed for {path_str}"

    def test_bdmv_name_deduction(self):
        searcher = Searcher("mock_key")
        searcher.search_all = MagicMock(return_value=[])

        cases = [
            ("/data/raw/The.Best.of.Youth.2003/BDMV/STREAM/00001.m2ts", "The.Best.of.Youth.2003"),
            ("/data/raw/Avatar.2009/Disc1/BDMV/STREAM/00001.m2ts", "Avatar.2009"),
            ("/data/raw/Titanic/Part2/BDMV/STREAM/00001.m2ts", "Titanic"),
        ]

        for path_str, expected_name in cases:
            p = Path(path_str)
            item = MediaItem(
                name=p.name,
                original_path=p,
                media_type=MediaType.MOVIE # Assume classifier already marked it MOVIE due to BDMV check
            )
            searcher.search(item)
            assert item.name == expected_name, f"Failed for {path_str}"

    def test_subtitle_renaming(self):
        renamer = Renamer()

        # Case 1: Movie Subtitle
        item_movie = MediaItem(
            name="Avatar",
            original_path=Path("/downloads/Avatar"),
            media_type=MediaType.MOVIE,
            title_cn="阿凡达",
            title_en="Avatar",
            year=2009,
            tmdb_id=19995
        )
        sub_file = MediaFile(path=Path("/downloads/Avatar/Avatar.2009.eng.srt"), extension=".srt")
        target = renamer.get_suggested_path(item_movie, sub_file)
        
        # Expectation: Same folder as movie, original filename
        assert str(target) == "Movies/阿凡达 (Avatar) (2009) {tmdb-19995}/Avatar.2009.eng.srt"

        # Case 2: TV Show Subtitle
        item_tv = MediaItem(
            name="Show",
            original_path=Path("/downloads/Show"),
            media_type=MediaType.TV_SHOW,
            title_cn="剧集",
            title_en="The Show",
            tmdb_id=12345
        )
        # File with S01E01
        tv_sub = MediaFile(path=Path("/downloads/Show/The.Show.S01E01.chs.ass"), extension=".ass")
        target_tv = renamer.get_suggested_path(item_tv, tv_sub)
        
        # Expectation: Renamed to match show pattern, preserving lang tag
        # S01E01 + .chs.ass
        assert "Season 1" in str(target_tv)
        assert target_tv.name == "The Show S01E01.chs.ass"

    def test_match_service_restores_media_type_from_db(self, media_repo, log_repo, mock_config):
        original_path = mock_config.source_dir / "foo.mkv"
        media_repo.save(
            {
                "original_path": str(original_path),
                "target_path": "Movies/Foo/Foo.mkv",
                "media_type": "TV Show",
                "title_cn": "测试剧集",
                "title_en": "Test Show",
                "tmdb_id": 123,
                "year": 2020,
                "alias": None,
                "search_status": "found",
                "last_scanned_at": 0,
            }
        )

        service = MatchService(mock_config, media_repo, log_repo)
        item = MediaItem(name="foo.mkv", original_path=original_path, media_type=MediaType.MOVIE)
        item = service.process_item(item)
        assert item.search_status == "found"
        assert item.media_type == MediaType.TV_SHOW

    def test_aggregator_groups_root_level_video_and_subtitle(self, tmp_path):
        source_root = tmp_path / "source"
        source_root.mkdir()

        video = source_root / "Movie.2020.mkv"
        subtitle = source_root / "Movie.2020.eng.srt"
        video.touch()
        subtitle.touch()

        aggregator = Aggregator(source_root)
        items = aggregator.aggregate(
            [
                MediaFile(path=video, extension=video.suffix.lower()),
                MediaFile(path=subtitle, extension=subtitle.suffix.lower()),
            ]
        )

        assert len(items) == 1
        assert items[0].name == "Movie.2020"
        assert {f.path.name for f in items[0].files} == {"Movie.2020.mkv", "Movie.2020.eng.srt"}
