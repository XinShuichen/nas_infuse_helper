# Copyright (c) 2025 Trae AI. All rights reserved.

import re
from pathlib import Path
from typing import Optional, Tuple
from .models import MediaItem, MediaType, MediaFile


class Renamer:
    """
    Suggests new names and paths for MediaItems and their files.
    """

    def __init__(self):
        self.tv_patterns = [
            re.compile(r"[Ss](\d+)[Ee](\d+)"),  # S01E01
            re.compile(r"EP?(\d+)", re.IGNORECASE),  # E01, EP01
            re.compile(r"第\s*(\d+)\s*[集话期]"),  # 第01集
            re.compile(r"\[(\d+)\]"),  # [01]
        ]
        self.season_patterns = [
            re.compile(r"Season\s*(\d+)", re.IGNORECASE),
            re.compile(r"S(\d+)", re.IGNORECASE),
        ]

    def sanitize_for_samba(self, name: str) -> str:
        """
        Sanitizes the filename by replacing illegal characters for Samba/Windows compatibility.
        """
        # Colon: replace with " - " if surrounded by spaces or text, but simple replacement is easier
        name = name.replace(": ", " - ")
        name = name.replace(":", "-")
        
        # Slash
        name = name.replace("/", "-")
        name = name.replace("\\", "-")
        
        # Others
        name = name.replace("?", "")
        name = name.replace("*", "")
        name = name.replace("<", "")
        name = name.replace(">", "")
        name = name.replace("\"", "")
        name = name.replace("|", "")
        
        # Remove control characters
        name = "".join(c for c in name if ord(c) >= 32)
        
        return name.strip()

    def clean_name(self, name: str) -> str:
        """
        Cleans up the name by removing common tags.
        """
        # Remove common brackets like [1080P], [BDRIP], etc.
        cleaned = re.sub(r"\[.*?\]", "", name)
        # Remove year like (2019) or .2019.
        cleaned = re.sub(r"[\(\.]\d{4}[\)\.]", " ", cleaned)
        # Remove common resolution and encoding tags
        tags = [
            r"1080[pi]",
            r"2160[pi]",
            r"720[pi]",
            r"4[kK]\s*超清",
            r"4[kK]",
            r"AVC",
            r"HEVC",
            r"H264",
            r"H265",
            r"x264",
            r"x265",
            r"BluRay",
            r"BDRIP",
            r"WEB-DL",
        ]
        for tag in tags:
            cleaned = re.sub(tag, " ", cleaned, flags=re.IGNORECASE)

        # Replace dots and underscores with spaces
        cleaned = cleaned.replace(".", " ").replace("_", " ").replace("-", " ")
        # Remove multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def extract_episode_info(self, filename: str) -> Tuple[Optional[int], Optional[int]]:
        season, episode = None, None

        # Try S01E01 first
        s_e_match = re.search(r"[Ss](\d+)[Ee](\d+)", filename)
        if s_e_match:
            return int(s_e_match.group(1)), int(s_e_match.group(2))

        # Try episode only
        for pattern in self.tv_patterns:
            match = pattern.search(filename)
            if match:
                # If only episode found, assume season 1 for now
                episode = int(match.group(1))
                season = 1
                break

        # Check if season is mentioned in the path
        for pattern in self.season_patterns:
            match = pattern.search(filename)
            if match:
                season = int(match.group(1))
                break

        return season, episode

    def get_suggested_path(self, item: MediaItem, file: MediaFile) -> Path:
        """
        Returns the suggested relative path for a file.
        """
        # Priority: Search results (Chinese + English + Year) > Original name
        if item.title_cn:
            display_name = item.title_cn
            if item.title_en and item.title_en != item.title_cn:
                display_name += f" ({item.title_en})"
            if item.year:
                display_name += f" ({item.year})"
            if item.tmdb_id:
                display_name += f" {{tmdb-{item.tmdb_id}}}"
            clean_item_name = self.sanitize_for_samba(display_name)
        else:
            clean_item_name = self.sanitize_for_samba(self.clean_name(item.name))

        if item.media_type == MediaType.MOVIE:
            # Movies/MovieName/OriginalFileName
            return Path("Movies") / clean_item_name / self.sanitize_for_samba(file.path.name)

        if item.media_type == MediaType.TV_SHOW:
            # Use item's season/episode if available (e.g. from manual assignment or previous classification)
            # Otherwise try to extract from filename
            season = item.season
            episode = item.episode
            
            if season is None or episode is None:
                extracted_season, extracted_episode = self.extract_episode_info(file.path.name)
                season = season or extracted_season
                episode = episode or extracted_episode

            # If not found in filename, check parent folder names
            if season is None or episode is None:
                parent_season, parent_episode = self.extract_episode_info(str(file.path.parent))
                season = season or parent_season or 1
                episode = episode or parent_episode

            season_str = f"Season {season if season else 1}"

            if episode is not None:
                # S01E01.ext
                s_e_part = f"S{season if season else 1:02d}E{episode:02d}"
                
                # Prepend English title if available
                if item.title_en:
                    clean_title_en = self.sanitize_for_samba(item.title_en)
                    new_filename = f"{clean_title_en} {s_e_part}{file.extension}"
                else:
                    new_filename = f"{s_e_part}{file.extension}"
                
                return Path("TV Shows") / clean_item_name / season_str / new_filename
            else:
                # Keep original name if episode cannot be determined
                return Path("TV Shows") / clean_item_name / season_str / self.sanitize_for_samba(file.path.name)

        return Path("Unknown") / self.sanitize_for_samba(file.path.name)
