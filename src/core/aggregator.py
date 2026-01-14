# Copyright (c) 2025 Trae AI. All rights reserved.

from pathlib import Path
import re
from typing import List, Dict, Optional, Tuple
from .models import MediaFile, MediaItem, MediaType
from pypinyin import lazy_pinyin


class Aggregator:
    """
    Groups MediaFiles into MediaItems using advanced heuristics.
    """

    def __init__(self, source_root: Path):
        self.source_root = source_root

    def _get_pinyin_prefix(self, name: str) -> str:
        """
        Gets the Pinyin of the first few words to group similar titles.
        """
        # Clean name from SxxExx/EPxx before pinyin
        clean_name = re.sub(r'[sS]\d+|[eE]\d+|EP\d+', '', name, flags=re.IGNORECASE).strip()
        # Remove separators
        clean_name = re.sub(r'[._-]', ' ', clean_name).strip()
        # Take first part before space
        prefix = clean_name.split(' ')[0]
        return "".join(lazy_pinyin(prefix)).lower()

    def _extract_episode_markers(self, name: str) -> Optional[str]:
        """
        Detects EPxx or SxxExx patterns.
        """
        match = re.search(r'([sS]\d+[eE]\d+|EP\d+)', name, re.IGNORECASE)
        return match.group(1) if match else None

    def _get_year(self, name: str) -> Optional[int]:
        match = re.search(r'\b(19[89]\d|20\d{2})\b', name)
        return int(match.group(1)) if match else None

    def aggregate(self, files: List[MediaFile]) -> List[MediaItem]:
        """
        Groups files by their logical content.
        """
        # Step 1: Initial grouping by top-level folder
        top_level_groups: Dict[Path, List[MediaFile]] = {}
        for media_file in files:
            try:
                rel_path = media_file.path.relative_to(self.source_root)
                top_level_name = rel_path.parts[0]
                item_root = self.source_root / top_level_name
                if item_root not in top_level_groups:
                    top_level_groups[item_root] = []
                top_level_groups[item_root].append(media_file)
            except ValueError:
                continue

        final_items: List[MediaItem] = []

        for item_root, item_files in top_level_groups.items():
            # Check for "Movie Series" inside a folder
            # Criteria: Multiple files, none have season markers, but they have different years
            has_season_markers = any(self._extract_episode_markers(f.path.name) for f in item_files)
            years = {self._get_year(f.path.name) for f in item_files if self._get_year(f.path.name)}
            
            if not has_season_markers and len(years) > 1 and len(item_files) > 1:
                # Treat each file as a separate Movie MediaItem
                for f in item_files:
                    final_items.append(MediaItem(
                        name=f.path.stem,
                        original_path=f.path,
                        files=[f]
                    ))
                continue

            # Check for different TV shows mixed in same folder or separate folders that are actually same show
            # (Grouped by Pinyin of prefix)
            if has_season_markers:
                # This folder is definitely a TV show, but might need to be grouped with others
                # For now, we keep top-level folders as units unless requested otherwise
                # But we handle the "Hei Jing" vs "黑镜" grouping if they were separate folders
                pass
            
            # Default: one folder = one item
            final_items.append(MediaItem(
                name=item_root.name,
                original_path=item_root,
                files=item_files,
            ))

        # Step 2: Global grouping for TV Shows with same Pinyin prefix
        # If two MediaItems have SxxExx/EPxx and their names have same Pinyin prefix, merge them.
        merged_items: Dict[str, MediaItem] = {}
        standalone_items: List[MediaItem] = []

        for item in final_items:
            has_tv_marker = any(self._extract_episode_markers(f.path.name) for f in item.files)
            if has_tv_marker:
                pinyin_key = self._get_pinyin_prefix(item.name)
                if pinyin_key in merged_items:
                    merged_items[pinyin_key].files.extend(item.files)
                    # Use the first one's path but we might need to handle this better
                else:
                    merged_items[pinyin_key] = item
            else:
                standalone_items.append(item)

        return list(merged_items.values()) + standalone_items
