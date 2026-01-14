# Copyright (c) 2025 Trae AI. All rights reserved.

from enum import Enum
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class MediaType(Enum):
    MOVIE = "Movie"
    TV_SHOW = "TV Show"
    UNKNOWN = "Unknown"


class MediaFile(BaseModel):
    """
    Represents a single file on disk.
    """

    path: Path
    extension: str
    size: int = 0  # In bytes, though mock files are 0
    mtime: float = 0.0


class MediaItem(BaseModel):
    """
    Represents a logical media entry (e.g., a movie or a TV show).
    """

    name: str
    original_path: Path  # Root path of this item
    files: List[MediaFile] = Field(default_factory=list)
    media_type: MediaType = MediaType.UNKNOWN
    title_cn: Optional[str] = None
    title_en: Optional[str] = None
    tmdb_id: Optional[int] = None
    year: Optional[int] = None
    alias: Optional[str] = None
    search_status: str = "pending"  # pending, found, not_found, uncertain
    suggested_name: Optional[str] = None

    @property
    def earliest_mtime(self) -> float:
        if not self.files:
            return 0.0
        return min(f.mtime for f in self.files)
    season: Optional[int] = None
    episode: Optional[int] = None
