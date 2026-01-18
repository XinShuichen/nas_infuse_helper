# Copyright (c) 2025 Trae AI. All rights reserved.

import re
from typing import List
from .models import MediaItem, MediaType, MediaFile


class Classifier:
    """
    Classifies MediaItems into Movie or TV Show and extracts metadata.
    """

    def __init__(self, video_extensions: List[str]):
        self.video_extensions = {ext.lower() for ext in video_extensions}
        # Common patterns for TV episodes: S01E01, E01, EP01, 第01集, etc.
        self.episode_patterns = [
            re.compile(r"[Ss](\d+)[Ee](\d+)"),  # S01E01
            re.compile(r"[Ee][Pp]?(\d+)"),  # E01, EP01
            re.compile(r"第\s*(\d+)\s*[集话期]"),  # 第01集
            re.compile(r"\[(\d+)\]"),  # [01]
            re.compile(r"\s(\d{1,3})\s"),  # Space separated number
        ]

    def is_video(self, file: MediaFile) -> bool:
        return file.extension.lower() in self.video_extensions

    def classify(self, item: MediaItem) -> MediaItem:
        video_files = [f for f in item.files if self.is_video(f)]

        # Check for BDMV (Blu-ray)
        has_bdmv = any("BDMV" in str(f.path) for f in item.files)
        if has_bdmv:
            item.media_type = MediaType.MOVIE
            return item

        path_parts = list(reversed(item.original_path.parts))
        start_idx = 1 if item.original_path.is_file() else 0
        
        for part in path_parts[start_idx:]:
            if re.search(r'\b(Season|S)\s*\d+\b', part, re.IGNORECASE) or \
               re.search(r'第\s*\d+\s*[季部]', part):
                item.media_type = MediaType.TV_SHOW
                break

        if len(video_files) > 1:
            # Check if multiple files look like episodes
            episode_count = 0
            for f in video_files:
                for pattern in self.episode_patterns:
                    if pattern.search(f.path.name):
                        episode_count += 1
                        break

            if episode_count > 1:
                item.media_type = MediaType.TV_SHOW
            # If we already detected it as TV Show via folder, keep it as TV Show
            elif item.media_type == MediaType.TV_SHOW:
                pass
            else:
                # Could be a movie with extras or multiple parts
                item.media_type = MediaType.MOVIE
        elif len(video_files) == 1:
            # If not already detected as TV Show via folder, check file name
            if item.media_type != MediaType.TV_SHOW:
                f = video_files[0]
                is_episode = False
                for pattern in self.episode_patterns:
                    if pattern.search(f.path.name):
                        is_episode = True
                        break
                
                if is_episode:
                    item.media_type = MediaType.TV_SHOW
                else:
                    item.media_type = MediaType.MOVIE
        else:
            if item.media_type == MediaType.TV_SHOW:
                return item
            is_episode = False
            for f in item.files:
                for pattern in self.episode_patterns:
                    if pattern.search(f.path.name):
                        is_episode = True
                        break
                if is_episode:
                    break
            item.media_type = MediaType.TV_SHOW if is_episode else MediaType.MOVIE

        return item
