# Copyright (c) 2025 Trae AI. All rights reserved.

import requests
import re
import time
from typing import Optional, List, Dict
from .models import MediaItem, MediaType


class Searcher:
    """
    Searches for official media titles using TMDB API with rate limiting support.
    """

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.last_request_time = 0
        self.request_count_in_window = 0
        self.window_start = time.time()

    def _handle_rate_limit(self, response: requests.Response):
        """
        Handles TMDB rate limiting based on response headers.
        """
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset_time = response.headers.get("X-RateLimit-Reset")

        if remaining is not None and int(remaining) <= 1:
            if reset_time:
                wait_time = float(reset_time) - time.time()
                if wait_time > 0:
                    print(f"Rate limit reached. Waiting for {wait_time:.2f} seconds...")
                    time.sleep(wait_time + 0.1)

    def clean_search_term(self, term: str) -> str:
        """
        Extracts a clean title from a raw filename for TMDB search.
        """
        # 1. Handle bracket Chinese: "[中文].英文" -> "中文"
        bracket_cn_match = re.match(r'^\[([\u4e00-\u9fa5]+)\]\.', term)
        if bracket_cn_match:
            return bracket_cn_match.group(1).strip()

        # 2. Remove leading bracket tags like [BDrip], [Sakurato]
        cleaned = re.sub(r'^\[.*?\]', '', term).strip()

        # 3. Handle bilingual titles: "中文.英文" -> "中文"
        # If starts with Chinese followed by dot and more text
        bilingual_match = re.match(r'^([\u4e00-\u9fa5]{2,})\.', cleaned)
        if bilingual_match:
            return bilingual_match.group(1).strip()

        # 2. Replace all separators with spaces for easier regex matching
        cleaned = re.sub(r'[._-]', ' ', cleaned).strip()
        
        # 3. Define technical and season tags that usually mark the end of the title
        # Includes: Resolution, Codec, Source, Season/Episode, Audio, Group tags, Chinese Season
        tech_patterns = [
            r'\b(19[89]\d|20\d{2})\b',  # Year
            r'\b[sS]\d+([-sS]\d+)?\b',   # Season (S01, S01-S05)
            r'\bSeason\s*\d+\b',         # Season 1
            r'第[一二三四五六七八九十\d]+[季部]', # 第1季, 第二季
            r'\b[eE]\d+\b',               # Episode (E01)
            r'\b\d{4}[pi]\b',            # Resolution (1080p, 2160p)
            r'\b[hH]\.?26[45]\b',        # Codec
            r'\b[xX]\.?26[45]\b',        # Codec
            r'\bHEVC|AVC|HDR|DV|DoVi\b',  # HDR/Codec
            r'\bBluRay|BDRIP|WEB-DL|WEB\b', # Source
            r'\bAtmos|TrueHD|DDP|DTS\b',  # Audio
            r'\bMax|NF|AMZN|iQIYI|Hami\b',    # Platform tags (Added Hami)
        ]
        
        # Combine patterns and find the earliest occurrence
        # Special case: If SxxExx is found, it's a strong indicator.
        # But 'Gintama.S01E29' -> 'Gintama' is handled by splitting at S01.
        # The issue might be that S01E29 is detected but maybe not 'S01-11'?
        # User provided: Gintama.S01E29...
        # S01 matches.
        
        combined_pattern = '|'.join(tech_patterns)
        match = re.search(combined_pattern, cleaned, flags=re.IGNORECASE)
        
        if match:
            # Take everything before the first technical tag
            cleaned = cleaned[:match.start()].strip()
        
        # 4. Final cleanup: remove multiple spaces and brackets
        cleaned = re.sub(r'\[.*?\]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # 5. Fallback: If only dots remain or very short, might need more cleanup
        # Specifically for "Gintama." -> "Gintama"
        cleaned = cleaned.rstrip(".")
        
        return cleaned

    def extract_season_from_name(self, name: str) -> Optional[int]:
        """
        Extracts season number from a string (Chinese or English).
        """
        # English patterns
        en_match = re.search(r'[sS](\d+)', name)
        if en_match:
            return int(en_match.group(1))
        
        en_match_2 = re.search(r'Season\s*(\d+)', name, re.IGNORECASE)
        if en_match_2:
            return int(en_match_2.group(1))

        # Chinese patterns
        cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        cn_match = re.search(r'第([一二三四五六七八九十\d]+)[季部]', name)
        if cn_match:
            val = cn_match.group(1)
            if val.isdigit():
                return int(val)
            return cn_map.get(val, 1)
        
        return None

    def _get(self, url: str, params: Dict, max_retries: int = 10) -> Optional[Dict]:
        """
        Wrapper for GET requests with rate limit handling and retries.
        """
        retry_count = 0
        while retry_count <= max_retries:
            try:
                response = requests.get(url, params=params, timeout=10)
                self._handle_rate_limit(response)
                
                if response.status_code == 429:
                    # Too many requests, retry once after waiting
                    retry_after = response.headers.get("Retry-After")
                    wait = int(retry_after) if retry_after else 1
                    time.sleep(wait)
                    continue # Retry immediately
                
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as e:
                # Do NOT retry on 404 Client Error
                if response.status_code == 404:
                    print(f"Request failed: 404 Not Found for url: {url}. No retry.")
                    return None
                
                retry_count += 1
                if retry_count > max_retries:
                    print(f"Request error for {url}: {e}")
                    print(f"Max retries ({max_retries}) exceeded.")
                    return None
                
                print(f"Request failed: {e}. Retrying ({retry_count}/{max_retries})...")
                wait_time = 2 ** min(retry_count, 5)
                time.sleep(wait_time)
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    print(f"Request error for {url}: {e}")
                    print(f"Max retries ({max_retries}) exceeded.")
                    return None
                
                print(f"Request failed: {e}. Retrying ({retry_count}/{max_retries})...")
                # Exponential backoff: 2^1, 2^2, 2^3... max 2^5 (32s)
                wait_time = 2 ** min(retry_count, 5)
                time.sleep(wait_time)
        return None

    def search(self, item: MediaItem) -> MediaItem:
        # 0. Check for Forced TMDB ID in file path (including parent folders)
        # Pattern: {tmdb-12345}, [tmdb-12345], (tmdb-12345)
        # Also supports tmdbid- prefix
        path_parts = list(reversed(item.original_path.parts))
        for part in path_parts:
            # Regex to match tmdb-12345 or tmdbid-12345 enclosed in {}, [], or ()
            # Group 1: Optional type (tv/movie)
            # Group 2: ID
            match = re.search(r'(?:\{|\[|\()(?:tmdb|tmdbid)-(?:(tv|movie)-)?(\d+)(?:\}|\]|\))', part, re.IGNORECASE)
            if match:
                type_prefix = match.group(1) # 'tv' or 'movie' or None
                tmdb_id_str = match.group(2)
                
                if type_prefix:
                    forced_alias = f"tmdb-{type_prefix.lower()}-{tmdb_id_str}"
                else:
                    forced_alias = f"tmdb-{tmdb_id_str}"
                
                print(f"Found Forced TMDB ID in path: '{part}' -> Using alias '{forced_alias}'")
                item.alias = forced_alias
                break

        if item.media_type == MediaType.MOVIE and "BDMV" in str(item.original_path):
            print(
                f"BDMV structure detected for {item.name}. Attempting to deduce Movie Name from path..."
            )
            parts = list(reversed(item.original_path.parts))
            bdmv_idx = -1
            try:
                bdmv_idx = parts.index("BDMV")
            except ValueError:
                bdmv_idx = -1

            if bdmv_idx != -1 and bdmv_idx + 1 < len(parts):
                candidate = parts[bdmv_idx + 1]
                if re.match(r"^(Disc|Disk|Part|CD)\s*\d+$", candidate, re.IGNORECASE):
                    if bdmv_idx + 2 < len(parts):
                        item.name = parts[bdmv_idx + 2]
                        print(f"Deduced Movie Name: {item.name}")
                else:
                    item.name = candidate
                    print(f"Deduced Movie Name: {item.name}")

        # Detect season if not already set
        if item.season is None:
            item.season = self.extract_season_from_name(item.name)

        # Use alias if available, otherwise use item name
        search_name = item.alias if item.alias else item.name
        results = self.search_all(search_name, item.media_type)
        
        # If failed and it looks like it has a dot after Chinese, try just the first part
        if not results and not item.alias:
            first_word_match = re.match(r'^([\u4e00-\u9fa5]{2,})', item.name)
            if first_word_match:
                fallback_name = first_word_match.group(1)
                print(f"--- [TMDB FALLBACK] Searching with first word: '{fallback_name}' ---")
                results = self.search_all(fallback_name, item.media_type)

        if results:
            # Pick the first result as default automatic match
            best_match = results[0]
            item.title_cn = best_match.get("title_cn")
            item.title_en = best_match.get("title_en")
            item.tmdb_id = best_match.get("tmdb_id")
            item.year = best_match.get("year")

            item.search_status = "found"
            # Lower confidence if multiple results and first one has few votes
            if len(results) > 1 and best_match.get("vote_count", 0) < 5:
                item.search_status = "uncertain"
        else:
            item.search_status = "not_found"

        return item

    def search_all(self, name: str, media_type: MediaType) -> List[Dict]:
        """
        Returns all possible candidates for a given name.
        Supports 'tmdb-ID' format for direct lookup.
        """
        if not self.api_key:
            return []

        tmdb_type = "movie" if media_type == MediaType.MOVIE else "tv"

        # Direct ID Lookup
        # Supports:
        # - tmdb-12345 (Uses requested media_type, falls back if 404)
        # - tmdb-tv-12345 (Forces TV Show lookup)
        # - tmdb-movie-12345 (Forces Movie lookup)
        if name.lower().startswith("tmdb-"):
            try:
                parts = name.split("-")
                forced_type = None
                
                # Check for forced type syntax: tmdb-tv-123 or tmdb-movie-123
                if len(parts) >= 3:
                    if parts[1].lower() == "tv":
                        forced_type = "tv"
                        tmdb_id_str = parts[2]
                    elif parts[1].lower() == "movie":
                        forced_type = "movie"
                        tmdb_id_str = parts[2]
                    else:
                        tmdb_id_str = parts[1]
                else:
                    tmdb_id_str = parts[1]

                if tmdb_id_str.isdigit():
                    tmdb_id = int(tmdb_id_str)
                    
                    # If forced type is set, use it. Otherwise use requested type.
                    current_tmdb_type = forced_type if forced_type else tmdb_type
                    
                    print(f"Direct TMDB ID Lookup: {tmdb_id} ({current_tmdb_type})")
                    
                    params = {"api_key": self.api_key, "language": "zh-CN"}
                    res = self._get(f"{self.BASE_URL}/{current_tmdb_type}/{tmdb_id}", params)
                    
                    # Fallback logic: 
                    # Only if NOT forced type, AND not found in requested type.
                    # If user forced "tmdb-tv-123", we do NOT fallback to movie.
                    if not res and not forced_type:
                        other_type = "tv" if current_tmdb_type == "movie" else "movie"
                        print(f"ID not found in {current_tmdb_type}, trying {other_type}...")
                        res = self._get(f"{self.BASE_URL}/{other_type}/{tmdb_id}", params)
                        if res:
                            current_tmdb_type = other_type # Switch type
                    
                    if not res:
                        return []
                        
                    candidate = {
                        "tmdb_id": res.get("id"),
                        "title_cn": res.get("title" if current_tmdb_type == "movie" else "name"),
                        "overview": res.get("overview"),
                        "poster_path": f"https://image.tmdb.org/t/p/w200{res.get('poster_path')}" if res.get('poster_path') else None,
                        "vote_count": res.get("vote_count"),
                        "media_type": "Movie" if current_tmdb_type == "movie" else "TV Show" # Return detected/forced type
                    }
                    
                    # Fetch English title
                    params_en = {"api_key": self.api_key, "language": "en-US"}
                    res_en = self._get(f"{self.BASE_URL}/{current_tmdb_type}/{tmdb_id}", params_en)
                    if res_en:
                        candidate["title_en"] = res_en.get("title" if current_tmdb_type == "movie" else "name")
                    
                    date_key = "release_date" if current_tmdb_type == "movie" else "first_air_date"
                    date_val = res.get(date_key, "")
                    if date_val:
                        candidate["year"] = int(date_val[:4])
                        
                    return [candidate]
            except Exception as e:
                print(f"Direct lookup failed: {e}")
                return []

        search_term = self.clean_search_term(name)
        
        # Log the exact search term
        print(f"Searching TMDB for: '{search_term}' (Original: '{name}')")
        
        year_match = re.search(r"(\d{4})", name)
        year = int(year_match.group(1)) if year_match else None

        tmdb_type = "movie" if media_type == MediaType.MOVIE else "tv"

        params = {
            "api_key": self.api_key,
            "query": search_term,
            "language": "zh-CN",
        }
        if year:
            params["year" if tmdb_type == "movie" else "first_air_date_year"] = year

        data = self._get(f"{self.BASE_URL}/search/{tmdb_type}", params)
        results = []

        if data:
            raw_results = data.get("results", [])
            if not raw_results and year:
                params.pop("year" if tmdb_type == "movie" else "first_air_date_year")
                data = self._get(f"{self.BASE_URL}/search/{tmdb_type}", params)
                if data:
                    raw_results = data.get("results", [])

            for res in raw_results:
                candidate = {
                    "tmdb_id": res.get("id"),
                    "title_cn": res.get("title" if tmdb_type == "movie" else "name"),
                    "overview": res.get("overview"),
                    "poster_path": f"https://image.tmdb.org/t/p/w200{res.get('poster_path')}" if res.get('poster_path') else None,
                    "vote_count": res.get("vote_count"),
                }
                
                # Fallback for English title from raw results
                original_title = res.get("original_title" if tmdb_type == "movie" else "original_name")
                if original_title and re.match(r'^[a-zA-Z0-9\s\-\:\.\!\?]+$', original_title):
                    candidate["title_en"] = original_title

                date_key = "release_date" if tmdb_type == "movie" else "first_air_date"
                date_val = res.get(date_key, "")
                if date_val:
                    candidate["year"] = int(date_val[:4])

                # Fetch English title details if not already satisfied by fallback or for better accuracy
                params_en = {"api_key": self.api_key, "language": "en-US"}
                res_en = self._get(f"{self.BASE_URL}/{tmdb_type}/{res.get('id')}", params_en)
                if res_en:
                    title_en = res_en.get("title" if tmdb_type == "movie" else "name")
                    if title_en:
                        candidate["title_en"] = title_en
                
                results.append(candidate)

        return results
