# Copyright (c) 2025 Trae AI. All rights reserved.

import pytest
from unittest.mock import MagicMock, patch
from src.core.searcher import Searcher
from src.core.models import MediaType

@pytest.fixture
def searcher():
    return Searcher(api_key="dummy_key")

def test_search_all_with_tmdb_id_movie(searcher):
    """
    Test direct ID lookup for a movie (e.g. tmdb-12345).
    """
    # Mock the _get method to avoid real network calls
    with patch.object(searcher, '_get') as mock_get:
        # Setup mock responses
        # 1. First call: Get details in Chinese (zh-CN)
        mock_cn_response = {
            "id": 12345,
            "title": "测试电影",
            "overview": "这是简介",
            "poster_path": "/poster.jpg",
            "vote_count": 100,
            "release_date": "2023-01-01"
        }
        
        # 2. Second call: Get details in English (en-US) for title fallback
        mock_en_response = {
            "id": 12345,
            "title": "Test Movie"
        }
        
        mock_get.side_effect = [mock_cn_response, mock_en_response]
        
        # Execute
        results = searcher.search_all("tmdb-12345", MediaType.MOVIE)
        
        # Verify
        assert len(results) == 1
        candidate = results[0]
        assert candidate["tmdb_id"] == 12345
        assert candidate["title_cn"] == "测试电影"
        assert candidate["title_en"] == "Test Movie"
        assert candidate["year"] == 2023
        
        # Verify calls
        # Expected calls: 
        # 1. /movie/12345?language=zh-CN
        # 2. /movie/12345?language=en-US
        assert mock_get.call_count == 2
        
        call1_args = mock_get.call_args_list[0]
        assert "movie/12345" in call1_args[0][0]
        assert call1_args[0][1]["language"] == "zh-CN"

def test_search_all_with_tmdb_id_tv(searcher):
    """
    Test direct ID lookup for a TV show.
    """
    with patch.object(searcher, '_get') as mock_get:
        mock_cn_response = {
            "id": 66666,
            "name": "测试剧集",
            "first_air_date": "2022-05-05",
            "vote_count": 50
        }
        mock_en_response = {
            "id": 66666,
            "name": "Test Show"
        }
        
        mock_get.side_effect = [mock_cn_response, mock_en_response]
        
        results = searcher.search_all("tmdb-66666", MediaType.TV_SHOW)
        
        assert len(results) == 1
        candidate = results[0]
        assert candidate["title_cn"] == "测试剧集"
        assert candidate["title_en"] == "Test Show"
        assert candidate["year"] == 2022
        
        # Verify URL uses 'tv' endpoint
        call1_args = mock_get.call_args_list[0]
        assert "tv/66666" in call1_args[0][0]

def test_search_all_with_invalid_id_format(searcher):
    """
    Test that invalid formats are ignored or return empty.
    """
    with patch.object(searcher, '_get') as mock_get:
        # Invalid ID (not a number)
        # Should fall back to normal search or return empty?
        # Based on implementation: if tmdb- prefix is present but parsing fails, it prints error and returns [].
        # Wait, the code says:
        # if tmdb_id_str.isdigit(): ...
        # else: falls through to normal search? 
        # Ah, looking at code:
        # if name.lower().startswith("tmdb-"):
        #    try: ... if tmdb_id_str.isdigit(): ...
        #    except: ...
        # If isdigit() is False, it just continues to normal search logic?
        # NO, looking at my implementation in previous turn:
        # if tmdb_id_str.isdigit():
        #    ...
        #    return [candidate]
        # (Implicit else): Falls through to `search_term = self.clean_search_term(name)`
        
        # So "tmdb-abc" will be treated as a search term "tmdb abc".
        # So _get WILL be called with query="tmdb abc".
        
        # Let's verify that behavior, OR if we want to enforce strictly that tmdb- means ID lookup only.
        # Current implementation falls back.
        # Let's update test to expect fallback search.
        
        results = searcher.search_all("tmdb-abc", MediaType.MOVIE)
        
        # Since we didn't set return_value for mock_get, it returns MagicMock which is truthy?
        # Actually _get returns None by default if not mocked? No, MagicMock returns MagicMock.
        # And MagicMock.get("results") returns MagicMock.
        # So results will be a list of garbage candidates.
        
        # Let's assert that it tried to search normally.
        assert mock_get.called
        args = mock_get.call_args[0]
        # URL should be search/movie, not movie/ID
        assert "search/movie" in args[0]
        assert args[1]["query"] == "tmdb abc"

def test_search_all_with_id_not_found(searcher):
    """
    Test when TMDB returns 404 (mocked as None from _get).
    """
    with patch.object(searcher, '_get') as mock_get:
        mock_get.return_value = None
        
        results = searcher.search_all("tmdb-999999", MediaType.MOVIE)
        
        assert len(results) == 0
